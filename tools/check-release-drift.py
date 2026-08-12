#!/usr/bin/env python3
"""Check current kernel.org releases against the selected patch in each series."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any
import urllib.request
from urllib.parse import urlparse

from patch_selection import (
    VersionError,
    select_patch,
    series_of as selected_series_of,
    version_key,
)


RELEASES_URL = "https://www.kernel.org/releases.json"
ACTIVE_MONIKERS = {"mainline", "stable", "longterm"}


class CheckError(RuntimeError):
    """An operational failure, rather than patch drift."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    env_tarballs = os.environ.get("CJKTTY_TARBALLS")
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--releases-file",
        type=Path,
        help="read releases.json from this path instead of kernel.org",
    )
    source.add_argument(
        "--releases-url",
        default=RELEASES_URL,
        help=f"release feed URL (default: {RELEASES_URL})",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="patch repository root (default: parent of tools)",
    )
    parser.add_argument(
        "--tarball-dir",
        type=Path,
        default=Path(env_tarballs) if env_tarballs else None,
        help="kernel tarball cache (default: CJKTTY_TARBALLS or scratch directory)",
    )
    parser.add_argument(
        "--scratch-dir",
        type=Path,
        default=Path(os.environ.get("CJKTTY_LAB", tempfile.gettempdir())),
        help="parent for temporary extracted trees (default: CJKTTY_LAB or system temp)",
    )
    parser.add_argument("--report", type=Path, help="also write the full Markdown report")
    parser.add_argument(
        "--issue-report",
        type=Path,
        help="write a Markdown body containing only drifted series",
    )
    parser.add_argument("--json", type=Path, help="write machine-readable results")
    return parser.parse_args()


def version_parts(version: str) -> tuple[int, int, int, int, int]:
    # Drift and patch selection must agree on version order or support reports diverge.
    try:
        return version_key(version)
    except VersionError as error:
        raise CheckError(str(error)) from error


def series_of(version: str) -> str:
    try:
        return selected_series_of(version)
    except VersionError as error:
        raise CheckError(str(error)) from error


def read_feed(path: Path | None, url: str) -> tuple[dict[str, Any], str]:
    if path is not None:
        try:
            return json.loads(path.read_text()), str(path)
        except (OSError, json.JSONDecodeError) as error:
            raise CheckError(f"cannot read release feed {path}: {error}") from error

    request = urllib.request.Request(url, headers={"User-Agent": "cjktty-release-drift"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response), url
    except (OSError, json.JSONDecodeError) as error:
        raise CheckError(f"cannot read release feed {url}: {error}") from error


def current_releases(feed: dict[str, Any]) -> dict[str, dict[str, Any]]:
    releases = feed.get("releases")
    if not isinstance(releases, list):
        raise CheckError("release feed has no releases array")

    current: dict[str, dict[str, Any]] = {}
    for release in releases:
        if not isinstance(release, dict):
            continue
        moniker = release.get("moniker")
        version = release.get("version")
        source = release.get("source")
        if (
            moniker not in ACTIVE_MONIKERS
            or release.get("iseol") is True
            or not isinstance(version, str)
            or not isinstance(source, str)
        ):
            continue
        series = series_of(version)
        previous = current.get(series)
        if previous is None or version_parts(version) > version_parts(previous["version"]):
            current[series] = release
    return current


def download_tarball(source: str, tarball_dir: Path) -> Path:
    name = Path(urlparse(source).path).name
    if not name.startswith("linux-") or ".tar." not in name:
        raise CheckError(f"release source is not a kernel tarball: {source}")
    tarball = tarball_dir / name
    if tarball.is_file():
        return tarball

    # The feed advertises an -rc under pub/linux/kernel/v*/testing, which 404s;
    # fetch-kernel.sh owns the one place that knows where each kind really lives.
    fetcher = Path(__file__).resolve().parent / "fetch-kernel.sh"
    version = name.removeprefix("linux-").split(".tar.", 1)[0]
    result = subprocess.run(
        [str(fetcher), version, str(tarball_dir)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise CheckError(f"cannot fetch linux-{version}: {result.stderr.strip()}")
    return Path(result.stdout.strip())


def apply_status(
    release: dict[str, Any], patch_path: Path, tarball_dir: Path, scratch_dir: Path
) -> tuple[str, str]:
    tarball = download_tarball(release["source"], tarball_dir)
    work = Path(tempfile.mkdtemp(prefix="release-drift.", dir=scratch_dir))
    tree = work / "linux"
    tree.mkdir()
    try:
        extracted = subprocess.run(
            ["tar", "-xf", str(tarball), "-C", str(tree), "--strip-components=1"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if extracted.returncode != 0:
            detail = extracted.stdout.strip()[-1000:]
            raise CheckError(f"cannot extract {tarball}: {detail}")

        with patch_path.open("rb") as patch_input:
            applied = subprocess.run(
                [
                    "patch",
                    "-d",
                    str(tree),
                    "-p1",
                    "--fuzz=0",
                    "--dry-run",
                    "--silent",
                    "--batch",
                    "--forward",
                ],
                stdin=patch_input,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        if applied.returncode == 0:
            return "applies", ""
        return "drifted", applied.stdout.strip()[-1000:]
    except OSError as error:
        raise CheckError(str(error)) from error
    finally:
        shutil.rmtree(work)


def markdown_report(results: list[dict[str, Any]], source: str) -> str:
    lines = [
        "# Kernel release patch status",
        "",
        f"Release feed: `{source}`",
        "",
        (
            "Watched series are the active, non-EOL kernel.org mainline, stable, and "
            "longterm series for which this repository has a monolithic patch. The "
            "patch selected for each release is checked; archived series "
            "and split `cjktty-code-*` patches are not checked."
        ),
        "",
        "| Series | Channel | Current release | Selected patch | Apply status |",
        "|---|---|---|---|---|",
    ]
    for result in results:
        status = {
            "applies": "APPLIES",
            "drifted": "DRIFTED",
            "error": "ERROR",
        }[result["status"]]
        lines.append(
            f"| {result['series']} | {result['moniker']} | {result['release']} | "
            f"`{result['patch']}` | {status} |"
        )

    applies = sum(result["status"] == "applies" for result in results)
    drifted = sum(result["status"] == "drifted" for result in results)
    errors = sum(result["status"] == "error" for result in results)
    lines.extend(
        [
            "",
            f"Summary: {applies} apply, {drifted} drifted, {errors} errors.",
            "",
            (
                "This is an application-only check using `patch -p1 --fuzz=0 "
                "--dry-run`. Applying is not the same as building the kernel or "
                "rendering CJK on a booted console."
            ),
        ]
    )
    error_results = [result for result in results if result["status"] == "error"]
    if error_results:
        lines.extend(["", "## Operational errors", ""])
        for result in error_results:
            detail = result["detail"].replace("\n", " ")
            lines.append(f"- {result['series']} ({result['release']}): {detail}")
    return "\n".join(lines) + "\n"


def issue_report(results: list[dict[str, Any]]) -> str:
    drifted = [result for result in results if result["status"] == "drifted"]
    lines = ["<!-- cjktty-release-drift -->", "# Kernel patch drift", ""]
    if drifted:
        lines.extend(
            [
                "These active kernel series no longer accept their newest patch:",
                "",
                "| Series | Channel | Current release | Patch | Workflow result |",
                "|---|---|---|---|---|",
            ]
        )
        for result in drifted:
            lines.append(
                f"| {result['series']} | {result['moniker']} | {result['release']} | "
                f"`{result['patch']}` | failure |"
            )
    else:
        lines.append("No watched kernel series is currently drifted.")
    lines.extend(
        [
            "",
            (
                "The check uses the active, non-EOL mainline, stable, and longterm "
                "entries in [kernel.org's released-versions feed]"
                "(https://www.kernel.org/releases.json). It checks the newest "
                "eligible monolithic patch carried for each matching series."
            ),
            "",
            (
                "This only runs `patch -p1 --fuzz=0 --dry-run`. Applying is not the "
                "same as building the kernel or rendering CJK on a booted console."
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def write_text(path: Path | None, content: str) -> None:
    if path is not None:
        path.write_text(content)


def main() -> int:
    args = parse_args()
    repo = args.repo.resolve()
    scratch_dir = args.scratch_dir.resolve()
    tarball_dir = (args.tarball_dir or scratch_dir / "tarballs").resolve()
    if not repo.is_dir():
        raise CheckError(f"repository does not exist: {repo}")
    scratch_dir.mkdir(parents=True, exist_ok=True)
    tarball_dir.mkdir(parents=True, exist_ok=True)

    feed, feed_source = read_feed(args.releases_file, args.releases_url)
    releases = current_releases(feed)
    patches: dict[str, Path] = {}
    for series, release in releases.items():
        try:
            patch = select_patch(repo, release["version"])
        except VersionError as error:
            raise CheckError(str(error)) from error
        if patch is not None:
            patches[series] = patch
    watched = sorted(patches, key=version_parts, reverse=True)
    if not watched:
        raise CheckError("no active kernel.org series has a monolithic repository patch")

    results: list[dict[str, Any]] = []
    for index, series in enumerate(watched, 1):
        release = releases[series]
        patch_path = patches[series]
        relative_patch = patch_path.relative_to(repo).as_posix()
        print(
            f"[{index}/{len(watched)}] {series}: {relative_patch} -> {release['version']}",
            file=sys.stderr,
            flush=True,
        )
        try:
            status, detail = apply_status(release, patch_path, tarball_dir, scratch_dir)
        except CheckError as error:
            status, detail = "error", str(error)
        results.append(
            {
                "series": series,
                "moniker": release["moniker"],
                "release": release["version"],
                "source": release["source"],
                "patch": relative_patch,
                "status": status,
                "rc": release["moniker"] == "mainline" and "-rc" in release["version"],
                "detail": detail,
            }
        )

    error_count = sum(result["status"] == "error" for result in results)
    drift_count = sum(result["status"] == "drifted" for result in results)
    rc_drift_count = sum(
        result["status"] == "drifted" and result["rc"] for result in results
    )
    exit_code = 2 if error_count else 1 if drift_count else 0
    payload = {
        "feed": feed_source,
        "selection": (
            "active non-EOL mainline, stable, and longterm series with "
            "monolithic patches"
        ),
        "results": results,
        "summary": {
            "watched_count": len(results),
            "apply_count": sum(result["status"] == "applies" for result in results),
            "drift_count": drift_count,
            "blocking_drift_count": drift_count,
            "rc_drift_count": rc_drift_count,
            "error_count": error_count,
            "exit_code": exit_code,
        },
    }
    report = markdown_report(results, feed_source)
    print(report, end="")
    write_text(args.report, report)
    write_text(args.issue_report, issue_report(results))
    if args.json is not None:
        args.json.write_text(json.dumps(payload, indent=2) + "\n")
    return exit_code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)

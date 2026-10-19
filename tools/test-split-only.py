#!/usr/bin/env python3
"""Exercise the split-only rule from 7.3 on against a fixture repository."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
from typing import Any, Callable

from support_data import VerificationError, read_verification


TOOLS = Path(__file__).resolve().parent
FONT = "cjktty-font-unifont-15.1.04.patch"
DATA = "cjktty-add-cjk32x32-font-data.patch"
SOURCE = "https://cdn.kernel.org/pub/linux/kernel/v7.x/linux-{}.tar.xz"
KCONFIG = "config FONT_8x16\n"
FONT_STANZA = """\
diff --git a/lib/fonts/font_cjk_16x16.h b/lib/fonts/font_cjk_16x16.h
new file mode 100644
--- /dev/null
+++ b/lib/fonts/font_cjk_16x16.h
@@ -0,0 +1 @@
+font
"""


def code_stanza(old: str = "FONT_8x16") -> str:
    return f"""\
--- a/lib/fonts/Kconfig
+++ b/lib/fonts/Kconfig
@@ -1 +1 @@
-config {old}
+config FONT_CJK_16x16
"""


def make_repo(root: Path, code_73: str = code_stanza()) -> Path:
    repo = root / "repo"
    (repo / "v7.x").mkdir(parents=True)
    (repo / FONT).write_text(FONT_STANZA)
    (repo / DATA).write_text(FONT_STANZA)
    (repo / "v7.x/cjktty-7.2.patch").write_text(code_stanza() + FONT_STANZA)
    (repo / "v7.x/cjktty-7.3-rc1.patch").write_text(code_stanza() + FONT_STANZA)
    (repo / "v7.x/cjktty-code-7.3-rc1.patch").write_text(code_stanza())
    (repo / "v7.x/cjktty-code-7.3.patch").write_text(code_73)
    return repo


def digest(repo: Path, *paths: str) -> dict[str, str]:
    return {path: hashlib.sha256((repo / path).read_bytes()).hexdigest() for path in paths}


def combined(repo: Path, kernel: str, stage: str, patch: str) -> dict[str, Any]:
    return {"kernel": kernel, "stage": stage, "date": "2026-10-20", "digests": digest(repo, patch)}


def split(repo: Path, kernel: str, stage: str, code: str) -> dict[str, Any]:
    return {
        "kernel": kernel,
        "stage": stage,
        "date": "2026-10-20",
        "form": "split",
        "font_patch": FONT,
        "code_patch": code,
        "digests": digest(repo, FONT, code),
    }


def full_records(repo: Path) -> list[dict[str, Any]]:
    return [
        combined(repo, "7.2.11", "stage-1", "v7.x/cjktty-7.2.patch"),
        combined(repo, "7.3-rc7", "stage-1", "v7.x/cjktty-7.3-rc1.patch"),
        split(repo, "7.3-rc7", "stage-1", "v7.x/cjktty-code-7.3-rc1.patch"),
        split(repo, "7.3", "stage-1", "v7.x/cjktty-code-7.3.patch"),
        split(repo, "7.3", "stage-2", "v7.x/cjktty-code-7.3.patch"),
    ]


def feed(*releases: tuple[str, str]) -> dict[str, Any]:
    return {
        "releases": [
            {"moniker": moniker, "version": version, "source": SOURCE.format(version), "iseol": False}
            for moniker, version in releases
        ]
    }


def run(*command: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", *map(str, command)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def selection_cases(root: Path) -> list[tuple[str, bool, str]]:
    repo = make_repo(root)
    expected = {
        # Without the rule 7.3 is served by the combined 7.3-rc1 patch.
        "7.3": [repo / FONT, repo / "v7.x/cjktty-code-7.3.patch"],
        "7.3.2": [repo / FONT, repo / "v7.x/cjktty-code-7.3.patch"],
        "7.3-rc7": [repo / "v7.x/cjktty-7.3-rc1.patch"],
        "7.2.11": [repo / "v7.x/cjktty-7.2.patch"],
    }
    results = []
    for kernel, patches in expected.items():
        result = run(TOOLS / "patch_selection.py", repo, kernel)
        want = "".join(f"{patch}\n" for patch in patches)
        results.append(
            (
                f"selection: {kernel} -> {[patch.name for patch in patches]}",
                result.returncode == 0 and result.stdout == want,
                f"exit {result.returncode}, stdout={result.stdout!r}",
            )
        )
    (repo / "cjktty-font-unifont-16.0.patch").write_text(FONT_STANZA)
    result = run(TOOLS / "patch_selection.py", repo, "7.3")
    results.append(
        (
            "selection: two font patches exit 2",
            result.returncode == 2 and not result.stdout,
            f"exit {result.returncode}, stdout={result.stdout!r}",
        )
    )
    return results


def verification_cases(root: Path) -> list[tuple[str, bool, str]]:
    repo = make_repo(root)
    cases: list[tuple[str, list[dict[str, Any]], str | None]] = [
        ("split stage-1 alone serves 7.3", full_records(repo), None),
        (
            "combined record for 7.3 is refused",
            [combined(repo, "7.3", "stage-1", "v7.x/cjktty-7.3-rc1.patch")],
            "verification for split-only 7.3 has a combined record",
        ),
        (
            "7.3 without split stage-1 is refused",
            [split(repo, "7.3", "stage-2", "v7.x/cjktty-code-7.3.patch")],
            "verification for 7.3 lacks split stage-1",
        ),
        (
            "7.2.11 still needs combined stage-1",
            [split(repo, "7.2.11", "stage-1", "v7.x/cjktty-code-7.3-rc1.patch")],
            "verification for 7.2.11 lacks stage-1",
        ),
    ]
    results = []
    for label, records, error in cases:
        path = root / "verification.json"
        path.write_text(json.dumps(records))
        try:
            read_verification(path)
            actual = None
        except VerificationError as raised:
            actual = str(raised)
        results.append((f"verification: {label}", actual == error, f"got {actual!r}"))
    return results


def write_tarball(directory: Path, version: str) -> None:
    with tarfile.open(directory / f"linux-{version}.tar.xz", "w:xz") as archive:
        data = KCONFIG.encode()
        member = tarfile.TarInfo(f"linux-{version}/lib/fonts/Kconfig")
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))


def drift_cases(root: Path) -> list[tuple[str, bool, str]]:
    results = []
    for label, code_73, status, exit_code in (
        ("font and code patch apply", code_stanza(), "applies", 0),
        ("rejecting code patch drifts", code_stanza("NOT_THERE"), "drifted", 1),
    ):
        case = root / label.replace(" ", "-")
        case.mkdir()
        repo = make_repo(case, code_73)
        write_tarball(case, "7.3")
        (case / "releases.json").write_text(json.dumps(feed(("mainline", "7.3"))))
        result = run(
            TOOLS / "check-release-drift.py",
            "--repo", repo,
            "--releases-file", case / "releases.json",
            "--tarball-dir", case,
            "--scratch-dir", case,
            "--json", case / "drift.json",
        )
        try:
            entry = json.loads((case / "drift.json").read_text())["results"][0]
        except (OSError, KeyError, IndexError, json.JSONDecodeError):
            entry = {}
        results.append(
            (
                f"drift: {label}",
                result.returncode == exit_code
                and entry.get("patches") == [FONT, "v7.x/cjktty-code-7.3.patch"]
                and entry.get("status") == status,
                f"exit {result.returncode}, entry={entry!r}, stderr={result.stderr[-300:]!r}",
            )
        )
    return results


def matrix(repo: Path, records: Path, *paths: str) -> dict[str, Any]:
    result = run(TOOLS / "ci-matrix.py", "--repo", repo, "--verification-file", records, *paths)
    if result.returncode != 0:
        return {"error": result.stderr.strip()}
    payload: dict[str, Any] = json.loads(result.stdout)
    return payload


def published_cases(root: Path) -> list[tuple[str, bool, str]]:
    repo = make_repo(root)
    records = root / "verification.json"
    records.write_text(json.dumps(full_records(repo)))
    releases = root / "releases.json"
    releases.write_text(json.dumps(feed(("mainline", "7.3"), ("stable", "7.2.11"))))
    generated = run(
        TOOLS / "gen-supported.py",
        "--repo", repo,
        "--releases-file", releases,
        "--verification-file", records,
    )
    try:
        supported = (repo / "SUPPORTED.md").read_text()
    except OSError:
        supported = ""
    row = "| 7.3 (mainline) | 7.3 |  | `v7.x/cjktty-code-7.3.patch` | Split ✓ | Split ✓ |  |"
    results = [
        (
            "SUPPORTED.md: 7.3 has no combined patch",
            generated.returncode == 0 and row in supported.splitlines(),
            f"exit {generated.returncode}, stderr={generated.stderr!r}, output={supported!r}",
        )
    ]

    served = [FONT, "v7.x/cjktty-code-7.3.patch"]
    checks: list[tuple[str, tuple[str, ...], Callable[[dict[str, Any]], bool]]] = [
        (
            "--all builds 7.3 from the split patches",
            ("--all",),
            lambda result: [job["patches"] for job in result["boot"]["include"]]
            == [served, ["v7.x/cjktty-7.2.patch"]],
        ),
        (
            "a tool change boots 7.3 split",
            ("tools/test-patch.sh",),
            lambda result: [job["name"] for job in result["boot"]["include"]]
            == ["Build and boot Linux 7.3 split patches"],
        ),
        (
            "CJK32 data patch stacks on the split patches",
            (DATA,),
            lambda result: result["apply"]["include"][0]["patches"] == [*served, DATA]
            and result["boot"]["include"][0]["patches"] == served,
        ),
    ]
    for label, paths, check in checks:
        result = matrix(repo, records, *paths)
        try:
            passed = check(result)
        except (KeyError, IndexError):
            passed = False
        results.append((f"CI matrix: {label}", passed, json.dumps(result)))
    return results


def main() -> int:
    failures = 0
    total = 0
    with tempfile.TemporaryDirectory(prefix="split-only.") as scratch:
        root = Path(scratch)
        groups: list[Callable[[Path], list[tuple[str, bool, str]]]] = [
            selection_cases,
            verification_cases,
            drift_cases,
            published_cases,
        ]
        for index, group in enumerate(groups):
            directory = root / str(index)
            directory.mkdir()
            for label, passed, detail in group(directory):
                total += 1
                if passed:
                    print(f"PASS: {label}")
                else:
                    print(f"FAIL: {label}: {detail}")
                    failures += 1
    print(f"split-only: {total - failures} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

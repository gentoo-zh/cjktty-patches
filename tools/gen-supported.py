#!/usr/bin/env python3
"""Generate the verified kernel support matrix."""

from __future__ import annotations

import argparse
from collections import defaultdict
import difflib
from pathlib import Path
import runpy
import sys
from typing import Any

from patch_selection import VersionError, select_patch, series_of, version_key
from support_data import (
    SplitForm,
    Verification,
    VerificationError,
    read_verification,
    stale,
    validated_split_forms,
)


TOOLS = Path(__file__).resolve().parent
RELEASE_DRIFT = runpy.run_path(str(TOOLS / "check-release-drift.py"))
RELEASES_URL = RELEASE_DRIFT["RELEASES_URL"]
FeedError = RELEASE_DRIFT["CheckError"]
read_feed = RELEASE_DRIFT["read_feed"]
current_releases = RELEASE_DRIFT["current_releases"]
STAGES = {
    "kasan": "KASAN clean",
    "kmemleak": "kmemleak clean",
    "lockdep": "lockdep clean",
    "grub": "GRUB",
    "installkernel": "installkernel",
    "dracut-initramfs": "dracut initramfs",
}
STAGE_ORDER = tuple(STAGES)
STAGE_GROUPS = (
    (("kasan", "kmemleak", "lockdep"), "KASAN, kmemleak and lockdep clean"),
    (
        ("grub", "installkernel", "dracut-initramfs"),
        "GRUB, installkernel and dracut initramfs",
    ),
)


class GeneratorError(RuntimeError):
    """The support matrix inputs are incomplete or malformed."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
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
    parser.add_argument("--check", action="store_true", help="fail if output is stale")
    parser.add_argument(
        "--repo",
        type=Path,
        default=TOOLS.parent,
        help="patch repository root (default: parent of tools)",
    )
    parser.add_argument(
        "--verification-file",
        type=Path,
        default=TOOLS / "supported-verification.json",
        help="checked-in verification records",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="output path (default: SUPPORTED.md under the repository root)",
    )
    return parser.parse_args()


def format_extra_stages(stages: set[str]) -> str:
    remaining = stages.copy()
    labels: list[str] = []
    for grouped_stages, label in STAGE_GROUPS:
        if set(grouped_stages) <= remaining:
            remaining.difference_update(grouped_stages)
            labels.append(label)
    for stage in STAGE_ORDER:
        if stage in remaining:
            labels.append(STAGES[stage])
    return "; ".join(labels)


def stage_mark(records: list[Verification], stage: str) -> str:
    forms = {record.form for record in records if record.stage == stage}
    marks = ["Combined \u2713"] if "combined" in forms else []
    if "split" in forms:
        marks.append("Split \u2713")
    return "<br>".join(marks)


def notes_for_series(
    series_records: dict[str, list[Verification]], current: str
) -> str:
    notes: list[str] = []
    for kernel in sorted(series_records, key=version_key, reverse=True):
        stages = {
            record.stage
            for record in series_records[kernel]
            if record.form == "combined" and record.stage not in {"stage-1", "stage-2"}
        }
        extra = format_extra_stages(stages)
        if not extra:
            continue
        notes.append(extra if kernel == current else f"{extra} on {kernel}")
    for kernel_records in series_records.values():
        for record in kernel_records:
            if record.note and record.note not in notes:
                notes.append(record.note)
    return "<br>".join(notes)


def split_header(forms: dict[str, SplitForm]) -> str:
    fonts = {form.font_patch for form in forms.values()}
    if not fonts:
        return "Split code patch"
    if len(fonts) != 1:
        raise GeneratorError("active split forms use different font patches")
    return f"Split code patch (with `{fonts.pop()}`)"


def generate(
    repo: Path,
    feed: dict[str, Any],
    records: dict[str, list[Verification]],
) -> str:
    releases = current_releases(feed)
    records_by_series: dict[str, dict[str, list[Verification]]] = defaultdict(dict)
    for kernel, verification_records in records.items():
        records_by_series[series_of(kernel)][kernel] = verification_records
    forms = validated_split_forms(repo, records)
    active_forms = {
        release["version"]: forms[release["version"]]
        for release in releases.values()
        if release["version"] in forms
    }

    lines = [
        "# Supported kernels",
        "",
        (
            "| Kernel.org series | Version tested | Combined patch | "
            f"{split_header(active_forms)} | Stage 1 (apply, build, render) | "
            "Stage 2 (full system) | Notes |"
        ),
        "|---|---|---|---|---|---|---|",
    ]
    used_dates: set[str] = set()
    for series in sorted(releases, key=version_key, reverse=True):
        release = releases[series]
        kernel = release["version"]
        kernel_records = records.get(kernel)
        if kernel_records is None:
            raise GeneratorError(
                f"no verification record for {release['moniker']} {release['version']}"
            )
        patch = select_patch(repo, kernel)
        if patch is None:
            raise GeneratorError(f"no patch serves verified kernel {kernel}")
        try:
            relative_patch = patch.relative_to(repo).as_posix()
        except ValueError as error:
            raise GeneratorError(f"selected patch is outside {repo}: {patch}") from error
        form = active_forms.get(kernel)
        code_patch = f"`{form.code_patch}`" if form is not None else ""
        for checked_kernel in records_by_series[series].values():
            used_dates.update(record.verified for record in checked_kernel)
        lines.append(
            f"| {series} ({release['moniker']}) | {kernel} | `{relative_patch}` | "
            f"{code_patch} | {stage_mark(kernel_records, 'stage-1')} | "
            f"{stage_mark(kernel_records, 'stage-2')} | "
            f"{notes_for_series(records_by_series[series], kernel)} |"
        )
    if len(used_dates) == 1:
        date_line = f"Verification date: {used_dates.pop()}."
    else:
        date_line = f"Verification dates: {', '.join(sorted(used_dates))}."
    lines.extend(
        [
            "",
            date_line,
            "",
            (
                "Everything else in `v3.x/` through `v7.x/` is kept for the `SRC_URI` "
                "of released ebuilds and is not maintained."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    repo = args.repo.resolve()
    output = (args.output or repo / "SUPPORTED.md").resolve()
    records = read_verification(args.verification_file.resolve())
    outdated = stale(records, repo)
    if outdated:
        # A measurement made against different bytes is not evidence for these.
        for record, reason in outdated:
            print(
                f"error: {record.kernel} {record.form} {record.stage}: {reason}",
                file=sys.stderr,
            )
        return 1
    feed, _ = read_feed(args.releases_file, args.releases_url)
    content = generate(repo, feed, records)

    if args.check:
        try:
            current = output.read_text()
        except OSError as error:
            print(f"error: cannot read {output}: {error}", file=sys.stderr)
            return 1
        if current != content:
            diff = difflib.unified_diff(
                current.splitlines(keepends=True),
                content.splitlines(keepends=True),
                fromfile=str(output),
                tofile="generated SUPPORTED.md",
            )
            sys.stdout.writelines(diff)
            return 1
        return 0

    output.write_text(content)
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FeedError, GeneratorError, OSError, VerificationError, VersionError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)

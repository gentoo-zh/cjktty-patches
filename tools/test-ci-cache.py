#!/usr/bin/env python3
"""Check that CI caches the tarball path selected by fetch-kernel.sh."""

from __future__ import annotations

from pathlib import Path
import subprocess


REPO = Path(__file__).resolve().parent.parent
FETCHER = REPO / "tools" / "fetch-kernel.sh"
WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"
CACHE_DIR = Path("/nonexistent-cjktty-cache")


def resolved_name(version: str) -> str:
    result = subprocess.run(
        [str(FETCHER), "--print-path", version, str(CACHE_DIR)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0 or result.stderr:
        raise RuntimeError(
            f"fetch-kernel.sh --print-path {version} exited {result.returncode}: "
            f"{result.stderr.strip()}"
        )
    return Path(result.stdout.strip()).name


def main() -> int:
    failures = 0
    cases = (
        ("release", "7.1.8", "linux-7.1.8.tar.xz"),
        ("release candidate", "7.2-rc7", "linux-7.2-rc7.tar.gz"),
    )
    for label, version, expected in cases:
        actual = resolved_name(version)
        if actual == expected:
            print(f"PASS: {label} resolves to {actual}")
        else:
            print(f"FAIL: {label} resolves to {actual}, expected {expected}")
            failures += 1

    workflow = WORKFLOW.read_text()
    contracts = (
        ('tools/fetch-kernel.sh --print-path "$KERNEL_VERSION" "$CJKTTY_TARBALLS"', 3),
        ('path: ${{ steps.tarball.outputs.path }}', 3),
        (
            'key: linux-tarball-${{ runner.os }}-${{ steps.tarball.outputs.name }}',
            3,
        ),
    )
    for text, expected_count in contracts:
        count = workflow.count(text)
        if count == expected_count:
            print(f"PASS: CI cache contract appears in all {count} kernel jobs")
        else:
            print(
                f"FAIL: CI cache contract {text!r} appears {count} times, "
                f"expected {expected_count}"
            )
            failures += 1

    print(f"CI kernel cache: {len(cases) + len(contracts) - failures} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

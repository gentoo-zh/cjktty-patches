#!/usr/bin/env python3
"""Exercise patch selection against repository filenames."""

from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "tools" / "patch_selection.py"
CASES = (
    ("later 6.12 point release", "6.12.103", "cjktty-6.12.102.patch"),
    ("exact point release", "6.12.63", "cjktty-6.12.63.patch"),
    ("later 7.1 point release", "7.1.8", "cjktty-7.1.7.patch"),
    ("bare series patch", "6.18.44", "cjktty-6.18.patch"),
    ("release candidate", "7.2-rc7", "cjktty-7.2.patch"),
    ("latest 5.10 point patch", "5.10.264", "cjktty-5.10.264.patch"),
    ("numeric string-order trap", "6.12.200", "cjktty-6.12.102.patch"),
)


def run_selector(version: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPT), str(REPO), version],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def main() -> int:
    failures = 0
    for label, kernel, expected in CASES:
        result = run_selector(kernel)
        series_dir = f"v{kernel.split('.', 1)[0]}.x"
        expected_output = f"{REPO / series_dir / expected}\n"
        if result.returncode == 0 and result.stdout == expected_output and not result.stderr:
            print(f"PASS: {label}: {kernel} -> {expected}")
        else:
            print(
                f"FAIL: {label}: {kernel}: expected stdout={expected_output!r}, "
                f"got stdout={result.stdout!r}; exit {result.returncode}, "
                f"stderr={result.stderr!r}"
            )
            failures += 1

    relative = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), ".", "6.12.103"],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if (
        relative.returncode == 0
        and relative.stdout == "v6.x/cjktty-6.12.102.patch\n"
        and not relative.stderr
    ):
        print("PASS: relative repository prints a relative patch path")
    else:
        print(
            f"FAIL: relative repository: exit {relative.returncode}, "
            f"stdout={relative.stdout!r}, stderr={relative.stderr!r}"
        )
        failures += 1

    for kernel in ("4.99.1", "nonsense", "6.12"):
        result = run_selector(kernel)
        if result.returncode == 1 and not result.stdout and not result.stderr:
            print(f"PASS: no selection: {kernel} exits 1")
        else:
            print(
                f"FAIL: no selection: {kernel}: exit {result.returncode}, "
                f"stdout={result.stdout!r}, stderr={result.stderr!r}"
            )
            failures += 1

    usage = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), str(REPO)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if usage.returncode == 2 and "<repository> <kernel-version>" in usage.stderr:
        print("PASS: missing version exits 2 with usage")
    else:
        print(
            f"FAIL: missing version: exit {usage.returncode}, "
            f"stdout={usage.stdout!r}, stderr={usage.stderr!r}"
        )
        failures += 1

    total = len(CASES) + 5
    print(f"patch selection: {total - failures} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

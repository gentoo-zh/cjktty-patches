#!/usr/bin/env python3
"""Exercise patch selection against repository filenames."""

from pathlib import Path
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "tools" / "patch_selection.py"
CASES = (
    ("later 6.12 point release", "6.12.103", "cjktty-6.12.102.patch"),
    ("exact point release", "6.12.63", "cjktty-6.12.63.patch"),
    ("later 7.1 point release", "7.1.8", "cjktty-7.1.7.patch"),
    ("bare series patch", "6.18.44", "cjktty-6.18.patch"),
    ("release candidate", "7.2-rc7", "cjktty-7.2-rc7.patch"),
    ("latest 5.10 point patch", "5.10.264", "cjktty-5.10.264.patch"),
    # 6.12.70 stays correct as 6.12 gains patches: string order would put
    # "6.12.104" below "6.12.70" and pick it, numeric order stops at 6.12.63.
    ("numeric string-order trap", "6.12.70", "cjktty-6.12.63.patch"),
)


# 9.0.06 sorts last as a string; only numeric order reaches 18.0.01.
FONT_RELEASES = ("9.0.06", "15.1.04", "18.0.01")


def run_selector(version: str, repo: Path = REPO) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPT), str(repo), version],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def font_repo(root: Path, fonts: tuple[str, ...]) -> Path:
    (root / "v7.x").mkdir()
    (root / "v7.x" / "cjktty-code-7.3.patch").touch()
    for name in fonts:
        (root / name).touch()
    return root


def font_cases() -> int:
    """The newest font patch serves a split kernel; a name without a version stops selection."""
    failures = 0
    names = tuple(f"cjktty-font-unifont-{release}.patch" for release in FONT_RELEASES)
    with tempfile.TemporaryDirectory() as scratch:
        repo = font_repo(Path(scratch), names)
        result = run_selector("7.3", repo)
        expected = f"{repo / names[-1]}\n{repo / 'v7.x' / 'cjktty-code-7.3.patch'}\n"
        if result.returncode == 0 and result.stdout == expected and not result.stderr:
            print(f"PASS: newest font patch: 7.3 -> {names[-1]}")
        else:
            print(
                f"FAIL: newest font patch: expected stdout={expected!r}, "
                f"got stdout={result.stdout!r}; exit {result.returncode}, "
                f"stderr={result.stderr!r}"
            )
            failures += 1

    for label, fonts in (
        ("malformed font version", (names[-1], "cjktty-font-unifont-18.0.patch")),
        ("font patch without a version", (names[-1], "cjktty-font-unifont-new.patch")),
        ("no font patch", ()),
    ):
        with tempfile.TemporaryDirectory() as scratch:
            result = run_selector("7.3", font_repo(Path(scratch), fonts))
        if result.returncode == 2 and not result.stdout and "error:" in result.stderr:
            print(f"PASS: {label} exits 2")
        else:
            print(
                f"FAIL: {label}: exit {result.returncode}, "
                f"stdout={result.stdout!r}, stderr={result.stderr!r}"
            )
            failures += 1
    return failures


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

    failures += font_cases()

    total = len(CASES) + 9
    print(f"patch selection: {total - failures} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

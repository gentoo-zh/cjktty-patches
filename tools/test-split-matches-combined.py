#!/usr/bin/env python3
"""Every split code patch must be what splitting its combined patch produces.

A split-only code patch has no combined counterpart and must carry no font stanza.
"""

from __future__ import annotations

from pathlib import Path
import runpy
import subprocess
import sys
import tempfile

from patch_selection import split_only

REPO = Path(__file__).resolve().parent.parent
FONT_PATCH = REPO / "cjktty-font-unifont-15.1.04.patch"
SPLITTER = REPO / "tools" / "split-patch.py"
SPLIT_MODULE = runpy.run_path(str(SPLITTER))
PARSE_STANZAS = SPLIT_MODULE["parse_stanzas"]
FONT_PATH = SPLIT_MODULE["FONT_PATH"]


def added_files(patch: Path) -> dict[str, bytes]:
    """Return the files created by a font-only patch, independent of diff headers."""
    stanzas = PARSE_STANZAS(patch.read_bytes().splitlines(keepends=True))
    return {
        path: b"".join(
            line[1:]
            for line in stanza.splitlines(keepends=True)
            if line.startswith(b"+") and not line.startswith(b"+++ ")
        )
        for path, stanza in stanzas.items()
    }


def version_of(code_patch: Path) -> str:
    return code_patch.name.removeprefix("cjktty-code-").removesuffix(".patch")


def combined_for(code_patch: Path) -> Path:
    return code_patch.parent / f"cjktty-{version_of(code_patch)}.patch"


def split(source: Path, scratch: str) -> tuple[Path, Path]:
    font = Path(scratch) / "font.patch"
    code = Path(scratch) / "code.patch"
    subprocess.run(
        [sys.executable, str(SPLITTER), str(source), str(font), str(code)],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    return font, code


def check_split_only(code_patch: Path, combined: Path) -> int:
    if combined.is_file():
        print(f"FAIL: split-only {code_patch.name} has a combined {combined.name}")
        return 1
    stanzas = PARSE_STANZAS(code_patch.read_bytes().splitlines(keepends=True))
    fonts = [path for path in stanzas if FONT_PATH.fullmatch(path)]
    if fonts or not stanzas:
        print(f"FAIL: split-only {code_patch.name} carries font stanzas {fonts}")
        return 1
    print(f"PASS: split-only {code_patch.name} carries no font stanza")
    return 0


def main() -> int:
    failures = 0
    checked = 0
    expected_font_files = added_files(FONT_PATCH)
    for code_patch in sorted(REPO.glob("v[0-9]*.x/cjktty-code-*.patch")):
        combined = combined_for(code_patch)
        if split_only(version_of(code_patch)):
            checked += 1
            failures += check_split_only(code_patch, combined)
            continue
        if not combined.is_file():
            print(f"FAIL: {code_patch.name} has no combined counterpart")
            failures += 1
            continue
        with tempfile.TemporaryDirectory() as scratch:
            font, code = split(combined, scratch)
            checked += 2
            if added_files(font) != expected_font_files:
                print(
                    f"FAIL: {FONT_PATCH.name} differs from the font half of "
                    f"{combined.name}"
                )
                failures += 1
            else:
                print(f"PASS: {FONT_PATCH.name} matches the font half of {combined.name}")
            if code.read_bytes() != code_patch.read_bytes():
                # A fix landed in the combined patch and the split form was not
                # regenerated, so the two forms install different kernels.
                print(f"FAIL: {code_patch.name} differs from splitting {combined.name}")
                failures += 1
            else:
                print(f"PASS: {code_patch.name} matches {combined.name}")
    print(f"split/combined agreement: {checked - failures} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

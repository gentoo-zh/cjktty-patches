#!/usr/bin/env python3
"""Every split code patch must be what splitting its combined patch produces."""

from __future__ import annotations

from pathlib import Path
import runpy
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parent.parent
FONT_PATCH = REPO / "cjktty-font-unifont-15.1.04.patch"
SPLITTER = REPO / "tools" / "split-patch.py"
PARSE_STANZAS = runpy.run_path(str(SPLITTER))["parse_stanzas"]


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


def combined_for(code_patch: Path) -> Path:
    version = code_patch.name.removeprefix("cjktty-code-").removesuffix(".patch")
    return code_patch.parent / f"cjktty-{version}.patch"


def main() -> int:
    failures = 0
    checked = 0
    expected_font_files = added_files(FONT_PATCH)
    for code_patch in sorted(REPO.glob("v[0-9]*.x/cjktty-code-*.patch")):
        combined = combined_for(code_patch)
        if not combined.is_file():
            print(f"FAIL: {code_patch.name} has no combined counterpart")
            failures += 1
            continue
        with tempfile.TemporaryDirectory() as scratch:
            font = Path(scratch) / "font.patch"
            code = Path(scratch) / "code.patch"
            subprocess.run(
                [sys.executable, str(SPLITTER), str(combined), str(font), str(code)],
                check=True,
                stdout=subprocess.DEVNULL,
            )
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

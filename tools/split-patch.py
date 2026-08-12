#!/usr/bin/env python3
"""Split a cjktty patch into reusable font data and kernel code patches."""

from __future__ import annotations

import argparse
import os
import re
import tempfile
from pathlib import Path


FONT_PATH = re.compile(r"lib/fonts/font_cjk_[0-9]+x[0-9]+\.h\Z")
DIFF_HEADER = re.compile(
    rb"diff --git a/([^\t \r\n]+) b/([^\t \r\n]+)\r?\n?\Z"
)
OLD_HEADER = re.compile(rb"--- a/([^\t\r\n]+)(?:\t.*)?\r?\n?\Z")


class InvalidPatch(Exception):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "route font_cjk_<width>x<height>.h stanzas to a font patch and "
            "all other stanzas to a code patch"
        )
    )
    parser.add_argument("source_patch")
    parser.add_argument("font_patch")
    parser.add_argument("code_patch")
    return parser.parse_args()


def header_path(line: bytes, pattern: re.Pattern[bytes], kind: bytes) -> str | None:
    match = pattern.fullmatch(line)
    if not match:
        if line.startswith(kind):
            raise InvalidPatch(f"cannot parse header: {line.rstrip()!r}")
        return None
    return match.group(1).decode("utf-8")


def diff_path(line: bytes) -> str | None:
    match = DIFF_HEADER.fullmatch(line)
    if not match:
        if line.startswith(b"diff --git a/"):
            raise InvalidPatch(f"cannot parse git header: {line.rstrip()!r}")
        return None
    old_path = match.group(1).decode("utf-8")
    new_path = match.group(2).decode("utf-8")
    if old_path != new_path:
        raise InvalidPatch(f"renamed path is not supported: {old_path} -> {new_path}")
    return old_path


def old_path(line: bytes) -> str | None:
    return header_path(line, OLD_HEADER, b"--- a/")


def discover_paths(lines: list[bytes]) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for line in lines:
        for path in (diff_path(line), old_path(line)):
            if path is not None and path not in seen:
                paths.append(path)
                seen.add(path)
    if not paths:
        raise InvalidPatch("patch has no file headers")
    return paths


def parse_stanzas(lines: list[bytes]) -> dict[str, bytes]:
    stanzas: dict[str, bytes] = {}
    current_path: str | None = None
    current_lines: list[bytes] = []
    saw_old_header = False

    def finish() -> None:
        nonlocal current_path, current_lines
        if current_path is None:
            return
        if current_path in stanzas:
            raise InvalidPatch(f"path has more than one stanza: {current_path}")
        stanzas[current_path] = b"".join(current_lines)
        current_path = None
        current_lines = []

    for line in lines:
        git_path = diff_path(line)
        source_path = old_path(line)

        if git_path is not None:
            finish()
            current_path = git_path
            saw_old_header = False
        elif source_path is not None:
            if current_path != source_path or saw_old_header:
                finish()
                current_path = source_path
            saw_old_header = True
        elif current_path is None:
            if line.strip():
                raise InvalidPatch("content appears before the first file header")
            continue

        current_lines.append(line)

    finish()
    return stanzas


def write_atomic(path: Path, content: bytes) -> None:
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(content)
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main() -> None:
    args = parse_args()
    source = Path(args.source_patch).absolute()
    font_output = Path(args.font_patch).absolute()
    code_output = Path(args.code_patch).absolute()

    if font_output == code_output:
        raise InvalidPatch("font and code outputs must differ")
    if source in (font_output, code_output):
        raise InvalidPatch("an output must not replace the source patch")
    for output in (font_output, code_output):
        if not output.parent.is_dir():
            raise InvalidPatch(f"output directory does not exist: {output.parent}")

    lines = source.read_bytes().splitlines(keepends=True)
    paths = discover_paths(lines)
    stanzas = parse_stanzas(lines)

    missing = [path for path in paths if path not in stanzas]
    unexpected = [path for path in stanzas if path not in paths]
    if missing or unexpected:
        raise InvalidPatch(
            f"file list and parsed stanzas differ: missing={missing}, unexpected={unexpected}"
        )

    font_paths = [path for path in paths if FONT_PATH.fullmatch(path)]
    code_paths = [path for path in paths if not FONT_PATH.fullmatch(path)]
    if not font_paths or not code_paths:
        raise InvalidPatch("split must produce at least one font and one code stanza")

    write_atomic(font_output, b"".join(stanzas[path] for path in font_paths))
    write_atomic(code_output, b"".join(stanzas[path] for path in code_paths))
    print(f"font: {font_output} ({len(font_paths)} files)")
    print(f"code: {code_output} ({len(code_paths)} files)")


if __name__ == "__main__":
    try:
        main()
    except (InvalidPatch, OSError, UnicodeError) as error:
        raise SystemExit(f"split-patch.py: {error}")

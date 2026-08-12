#!/usr/bin/env python3
"""Generate cjktty BMP font data from GNU Unifont hex files."""

import argparse
from itertools import zip_longest
from pathlib import Path
import re
import struct
import sys


BMP_LIMIT = 0x10000
BASE_GLYPHS = 256
BYTE = re.compile(r"\b0x([0-9a-fA-F]{2})\b")
HEX_LINE = re.compile(r"([0-9a-fA-F]{4,6}):([0-9a-fA-F]+)")
SPDX = {16: "GPL-2.0", 32: "OFL-1.1"}
HEADER = {
    16: (
        "/* Base glyphs are from Linux font_8x16.c. */",
        "/* Remaining glyphs are derived from GNU Unifont 15.1.04. */",
        "/*",
        " * Copyright \N{COPYRIGHT SIGN} 1998-2022 Roman Czyborra, Paul Hardy,",
        " * Qianqian Fang, Andrew Miller, Johnnie Weaver, David Corbett,",
        " * Nils Moskopp, Rebecca Bettencourt, et al.",
        " */",
    ),
    32: (
        "/* Base glyphs are from Terminus Font 4.49.1 via Linux font_ter16x32.c. */",
        "/* Remaining glyphs are derived from GNU Unifont 15.1.04. */",
        "/*",
        " * Copyright \N{COPYRIGHT SIGN} 1998-2022 Roman Czyborra, Paul Hardy,",
        " * Qianqian Fang, Andrew Miller, Johnnie Weaver, David Corbett,",
        " * Nils Moskopp, Rebecca Bettencourt, et al.",
        " * Copyright (C) 2020 Dimitar Toshkov Zhekov,",
        ' * with Reserved Font Name "Terminus Font".',
        " */",
    ),
}
PSF2_MAGIC = 0x864AB572
PSF2_HEADER_SIZE = 32


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="generate fixed-width cjktty font data from a Unifont .hex file"
    )
    parser.add_argument("hex_file", type=Path, help="GNU Unifont .hex file")
    parser.add_argument(
        "--size", type=int, choices=(16, 32), required=True, help="output glyph size"
    )
    parser.add_argument(
        "--base-font",
        type=Path,
        required=True,
        help="Linux font_8x16.c or font_ter16x32.c for U+0000..U+00FF",
    )
    parser.add_argument(
        "--compare",
        type=Path,
        metavar="FILE",
        help="compare data bytes with a generated header or cjktty patch",
    )
    parser.add_argument(
        "--output",
        type=Path,
        metavar="FILE",
        help="write the generated font instead of standard output",
    )
    parser.add_argument(
        "--format",
        choices=("header", "psf2"),
        default="header",
        help="output a C header (default) or a loadable PSF2 font",
    )
    return parser.parse_args()


def strip_c_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.DOTALL)


def read_base_font(path: Path, expected_bytes: int) -> bytes:
    text = path.read_text(encoding="utf-8")
    match = re.search(
        r"static\s+const\s+struct\s+font_data\s+fontdata_[^{]+\{(.*?)\}\s*};",
        text,
        flags=re.DOTALL,
    )
    if not match:
        raise ValueError(f"{path}: no Linux font_data initializer found")
    data = bytes(int(value, 16) for value in BYTE.findall(strip_c_comments(match.group(1))))
    if len(data) != expected_bytes:
        raise ValueError(
            f"{path}: expected {expected_bytes} base font bytes, found {len(data)}"
        )
    return data


def read_unifont(path: Path) -> dict[int, bytes]:
    glyphs = {}
    for lineno, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        match = HEX_LINE.fullmatch(line)
        if not match:
            raise ValueError(f"{path}:{lineno}: malformed Unifont hex line")
        codepoint = int(match.group(1), 16)
        payload = match.group(2)
        if len(payload) not in (32, 64):
            raise ValueError(
                f"{path}:{lineno}: expected a halfwidth or fullwidth 16-row glyph"
            )
        if codepoint >= BMP_LIMIT:
            continue
        if codepoint in glyphs:
            raise ValueError(f"{path}:{lineno}: duplicate U+{codepoint:04X}")
        glyphs[codepoint] = bytes.fromhex(payload)
    return glyphs


def split_16x16(raw: bytes) -> bytes:
    if len(raw) == 16:
        return raw + bytes(16)
    return raw[::2] + raw[1::2]


def double_byte(value: int) -> bytes:
    expanded = 0
    for bit in range(8):
        if value & (0x80 >> bit):
            expanded |= 0xC000 >> (bit * 2)
    return expanded.to_bytes(2, "big")


def split_32x32(raw: bytes) -> bytes:
    if len(raw) == 16:
        left = b"".join(double_byte(value) * 2 for value in raw)
        return left + bytes(64)

    rows = [
        double_byte(raw[offset]) + double_byte(raw[offset + 1])
        for offset in range(0, len(raw), 2)
    ]
    left = b"".join(row[:2] * 2 for row in rows)
    right = b"".join(row[2:] * 2 for row in rows)
    return left + right


def generate(hex_path: Path, base_path: Path, size: int) -> bytes:
    bytes_per_codepoint = size * size // 8
    base_bytes = BASE_GLYPHS * bytes_per_codepoint // 2
    base = read_base_font(base_path, base_bytes)
    glyphs = read_unifont(hex_path)
    convert = split_16x16 if size == 16 else split_32x32

    data = bytearray(base)
    data.extend(bytes(base_bytes))
    for codepoint in range(BASE_GLYPHS, BMP_LIMIT):
        raw = glyphs.get(codepoint)
        data.extend(bytes(bytes_per_codepoint) if raw is None else convert(raw))
    return bytes(data)


def format_header(data: bytes, size: int) -> str:
    lines = [f"/* SPDX-License-Identifier: {SPDX[size]} */", *HEADER[size]]
    for offset in range(0, len(data), 16):
        values = ",".join(f"0x{value:02x}" for value in data[offset : offset + 16])
        lines.append(values + ",")
    return "\n".join(lines) + "\n"


def format_psf2(data: bytes, size: int) -> bytes:
    width = size // 2
    height = size
    charsize = (width + 7) // 8 * height
    glyphs = BMP_LIMIT * 2
    if len(data) != glyphs * charsize:
        raise ValueError("generated data does not fit the cjktty PSF2 layout")

    header = struct.pack(
        "<8I",
        PSF2_MAGIC,
        0,
        PSF2_HEADER_SIZE,
        0,
        glyphs,
        charsize,
        height,
        width,
    )
    return header + data


def read_reference(path: Path, size: int) -> bytes:
    text = path.read_text(encoding="utf-8")
    marker = f"+++ b/lib/fonts/font_cjk_{size}x{size}.h"
    if marker in text:
        text = text.split(marker, 1)[1]
        text = re.split(r"^(?:diff --git|--- a/)", text, maxsplit=1, flags=re.MULTILINE)[0]
        prefix = "+0x"
    else:
        prefix = "0x"

    values: list[int] = []
    for line in text.splitlines():
        if line.startswith(prefix):
            values.extend(int(value, 16) for value in BYTE.findall(line))
    if not values:
        raise ValueError(f"{path}: no font data bytes found")
    return bytes(values)


def codepoint_ranges(codepoints: list[int]) -> str:
    ranges = []
    start = previous = codepoints[0]
    for codepoint in codepoints[1:]:
        if codepoint == previous + 1:
            previous = codepoint
            continue
        ranges.append((start, previous))
        start = previous = codepoint
    ranges.append((start, previous))
    return " ".join(
        f"U+{start:04X}" if start == end else f"U+{start:04X}-U+{end:04X}"
        for start, end in ranges
    )


def compare(data: bytes, reference: bytes, size: int) -> bool:
    bytes_per_codepoint = size * size // 8
    limit = max(len(data), len(reference))
    differing_bytes = sum(
        generated != expected
        for generated, expected in zip_longest(data, reference, fillvalue=-1)
    )
    codepoints = [
        codepoint
        for codepoint in range((limit + bytes_per_codepoint - 1) // bytes_per_codepoint)
        if data[
            codepoint * bytes_per_codepoint : (codepoint + 1) * bytes_per_codepoint
        ]
        != reference[
            codepoint * bytes_per_codepoint : (codepoint + 1) * bytes_per_codepoint
        ]
    ]

    identical = not differing_bytes
    print(f"generated bytes: {len(data)}")
    print(f"reference bytes: {len(reference)}")
    print(f"byte-identical: {'yes' if identical else 'no'}")
    if codepoints:
        print(f"differing bytes: {differing_bytes}")
        print(f"differing codepoints: {len(codepoints)}")
        print(codepoint_ranges(codepoints))
    return identical


def main() -> int:
    args = parse_args()
    try:
        data = generate(args.hex_file, args.base_font, args.size)
        if args.format == "psf2":
            if args.compare:
                raise ValueError("--compare only accepts C header output")
            output = format_psf2(data, args.size)
            if args.output:
                args.output.write_bytes(output)
            else:
                sys.stdout.buffer.write(output)
        elif args.output:
            args.output.write_text(format_header(data, args.size), encoding="utf-8")
        elif not args.compare:
            sys.stdout.write(format_header(data, args.size))

        if args.compare:
            reference = read_reference(args.compare, args.size)
            return 0 if compare(data, reference, args.size) else 1
    except (OSError, ValueError) as error:
        print(f"gen-font.py: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

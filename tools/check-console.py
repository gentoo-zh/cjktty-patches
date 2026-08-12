"""Decide from a console screenshot whether the CJK glyphs really rendered.

The patch does not change vc_font, so no ioctl can answer this: the console
still reports the 256-glyph base font while cjktty draws CJK from its own
buffer. What separates a working kernel from a broken one is on screen: each
glyph must match the bitmap compiled into the patched kernel.

The test prints from a cleared screen, so the CJK lines sit at known rows.

A rotated console moves those rows and rotates each glyph clockwise. Rotation
runs fbcon_rotate_font_utf, so `--rotated` requires the rotated source bitmaps at
their expected coordinates.

The cell size follows the base console font, not the CJK font: 8x16 by default,
16x32 when the kernel was built for the 32x32 CJK font with the 8x16 base off.
Sampling a 16x32 screen with 8x16 cells lands between glyphs and reports a
blank cell on a working kernel.

Usage: check-console.py [--rotated] [--cell WxH] <screenshot.ppm>
"""

from __future__ import annotations

import sys
from pathlib import Path

DEFAULT_CELL = (8, 16)
#: init.c writes a title line first, then Simplified on the next row.
CJK_ROW = 1
#: "Simplified:  " is thirteen columns; the CJK text starts after it.
FIRST_COLUMN = 13
#: A CJK glyph is two cells wide.
GLYPH_CELLS = 2
#: One rotated line of the test text lights this many subpixels; half of it is
#: still unmistakably a line of text and not a stray cursor.
ROTATED_MIN_INK = 1000
#: "rotated:  " occupies ten cells before the CJK text.
ROTATED_PREFIX_CELLS = 10
#: QEMU screendump writes the console's 0xaa foreground, while a black
#: background remains zero. This threshold tolerates colour conversion without
#: allowing dark background values to become glyph pixels.
INK_THRESHOLD = 0x40
#: GNU Unifont 15.1.04 bitmaps for the fixed test text, in display order.
EXPECTED_GLYPHS = (
    (0x4E2D, bytes.fromhex("01000100010001003FF8210821082108210821083FF821080100010001000100")),
    (0x6587, bytes.fromhex("020001000100FFFE10101010082008200440028001000280044008203018C006")),
    (0x63A7, bytes.fromhex("10401020102013FEFA02149411081A043000D1FC102010201020102057FE2000")),
    (0x5236, bytes.fromhex("0404240424043FA444240424FFE4042404243FA424A424A42684250404140408")),
    (0x53F0, bytes.fromhex("0200020004000820101020087FFC200400001FF010101010101010101FF01010")),
    (0x663E, bytes.fromhex("00001FF0101010101FF0101010101FF0044044442444144814500440FFFE0000")),
    (0x793A, bytes.fromhex("00003FF80000000000000000FFFE010001001110110821044102810205000200")),
    (0x6D4B, bytes.fromhex("000427C414441454855445544554155415542554E55421042284224424140808")),
    (0x8BD5, bytes.fromhex("002820241024102007FE0020F02017E0112011101110151019CA170A02060002")),
)


class CheckFailed(Exception):
    pass


def read_ppm(path: Path) -> tuple[int, int, bytes]:
    data = path.read_bytes()
    fields: list[bytes] = []
    at = 0
    while len(fields) < 4:
        while at < len(data) and data[at : at + 1].isspace():
            at += 1
        if data[at : at + 1] == b"#":
            at = data.index(b"\n", at) + 1
            continue
        end = at
        while end < len(data) and not data[end : end + 1].isspace():
            end += 1
        fields.append(data[at:end])
        at = end
    if fields[0] != b"P6":
        raise CheckFailed(f"{path} is not a binary PPM")
    if fields[3] != b"255":
        raise CheckFailed(f"{path} does not use 8-bit RGB samples")
    width = int(fields[1])
    height = int(fields[2])
    pixels = data[at + 1 :]
    if width < 1 or height < 1 or len(pixels) != width * height * 3:
        raise CheckFailed(f"{path} has invalid dimensions or pixel data")
    return width, height, pixels


def glyph(
    pixels: bytes,
    width: int,
    height: int,
    row: int,
    column: int,
    cell: tuple[int, int],
) -> tuple[bool, ...]:
    cell_width, cell_height = cell
    return pixel_mask(
        pixels,
        width,
        height,
        column * cell_width,
        row * cell_height,
        GLYPH_CELLS * cell_width,
        cell_height,
    )


def ink(block: tuple[bool, ...]) -> int:
    return sum(block)


def pixel_mask(
    pixels: bytes,
    width: int,
    height: int,
    left: int,
    top: int,
    block_width: int,
    block_height: int,
) -> tuple[bool, ...]:
    if left < 0 or top < 0 or left + block_width > width or top + block_height > height:
        raise CheckFailed("the expected CJK cells fall outside the screenshot")
    return tuple(
        max(pixels[(y * width + x) * 3 : (y * width + x + 1) * 3]) > INK_THRESHOLD
        for y in range(top, top + block_height)
        for x in range(left, left + block_width)
    )


def expected_mask(bitmap: bytes, cell: tuple[int, int], rotated: bool) -> tuple[bool, ...]:
    cell_width, cell_height = cell
    if cell_width % 8 or cell_height % 16 or cell_width // 8 != cell_height // 16:
        raise CheckFailed(f"unsupported console cell {cell_width}x{cell_height}")
    scale = cell_width // 8
    source = [
        [
            bool(int.from_bytes(bitmap[y * 2 : y * 2 + 2], "big") & (1 << (15 - x)))
            for x in range(16)
        ]
        for y in range(16)
    ]
    expanded = [
        [pixel for pixel in row for _ in range(scale)]
        for row in source
        for _ in range(scale)
    ]
    if rotated:
        expanded = [list(row) for row in zip(*expanded[::-1])]
    return tuple(pixel for row in expanded for pixel in row)


def rotated_glyph(
    pixels: bytes,
    width: int,
    height: int,
    index: int,
    cell: tuple[int, int],
) -> tuple[bool, ...]:
    cell_width, cell_height = cell
    left = width - cell_height
    top = (ROTATED_PREFIX_CELLS + index * GLYPH_CELLS) * cell_width
    bottom = top + GLYPH_CELLS * cell_width
    if left < 0 or bottom > height:
        raise CheckFailed("the rotated CJK cells fall outside the screenshot")

    return pixel_mask(pixels, width, height, left, top, cell_height, bottom - top)


def check_glyphs(
    pixels: bytes,
    width: int,
    height: int,
    cell: tuple[int, int],
    rotated: bool,
) -> tuple[int, int]:
    counts: list[int] = []
    for index, (codepoint, bitmap) in enumerate(EXPECTED_GLYPHS):
        if rotated:
            actual = rotated_glyph(pixels, width, height, index, cell)
        else:
            actual = glyph(
                pixels,
                width,
                height,
                CJK_ROW,
                FIRST_COLUMN + index * GLYPH_CELLS,
                cell,
            )
        expected = expected_mask(bitmap, cell, rotated)
        if actual != expected:
            differing = sum(left != right for left, right in zip(actual, expected))
            raise CheckFailed(
                f"U+{codepoint:04X} differs from the expected Unifont bitmap "
                f"at {differing} pixels"
            )
        counts.append(ink(actual))
    return counts[0], counts[1]


def lit_box(pixels: bytes, width: int, height: int) -> tuple[int, int, int, int]:
    xs: list[int] = []
    ys: list[int] = []
    for y in range(height):
        row = pixels[y * width * 3 : (y + 1) * width * 3]
        for x in range(width):
            if max(row[x * 3 : x * 3 + 3]) > INK_THRESHOLD:
                xs.append(x)
                ys.append(y)
    if not xs:
        raise CheckFailed("the screen is blank; rotation painted nothing")
    return min(xs), min(ys), max(xs), max(ys)


def check_rotated(path: Path, cell: tuple[int, int] = DEFAULT_CELL) -> str:
    width, height, pixels = read_ppm(path)
    lit = sum(value > INK_THRESHOLD for value in pixels)
    if lit < ROTATED_MIN_INK:
        raise CheckFailed(
            f"the rotated console drew {lit} lit subpixels, under {ROTATED_MIN_INK}; "
            "rotation painted nothing"
        )
    first_ink, second_ink = check_glyphs(pixels, width, height, cell, True)
    left, top, right, bottom = lit_box(pixels, width, height)
    box_width = right - left + 1
    box_height = bottom - top + 1
    # A line of text is long along the reading direction. Rotated by 90 degrees
    # it stands taller than it is wide, which an unrotated line can never do.
    if box_height <= box_width:
        raise CheckFailed(
            f"the drawn text is {box_width} by {box_height} pixels, wider than tall; "
            "the console did not rotate"
        )
    return (
        f"{len(EXPECTED_GLYPHS)} rotated CJK glyphs match the expected Unifont "
        f"bitmaps ({first_ink} and {second_ink} lit pixels in the first two); "
        f"the line is {box_width} by {box_height} pixels"
    )


def check(path: Path, cell: tuple[int, int] = DEFAULT_CELL) -> str:
    width, height, pixels = read_ppm(path)
    cell_height = cell[1]
    if height < (CJK_ROW + 1) * cell_height:
        raise CheckFailed(f"{path} is only {height} pixels tall")

    first_ink, second_ink = check_glyphs(pixels, width, height, cell, False)
    return (
        f"{len(EXPECTED_GLYPHS)} CJK glyphs match the expected Unifont bitmaps "
        f"({first_ink} and {second_ink} lit pixels in the first two)"
    )


def parse_cell(text: str) -> tuple[int, int]:
    try:
        width, height = (int(part) for part in text.lower().split("x", 1))
    except ValueError:
        raise SystemExit(f"--cell wants WxH, not {text!r}")
    if width < 1 or height < 1:
        raise SystemExit(f"--cell wants positive numbers, not {text!r}")
    return width, height


if __name__ == "__main__":
    arguments = sys.argv[1:]
    rotated = "--rotated" in arguments
    if rotated:
        arguments.remove("--rotated")
    cell = DEFAULT_CELL
    if "--cell" in arguments:
        at = arguments.index("--cell")
        if at + 1 >= len(arguments):
            raise SystemExit("--cell wants a WxH argument")
        cell = parse_cell(arguments[at + 1])
        del arguments[at : at + 2]
    if len(arguments) != 1:
        raise SystemExit(
            "usage: check-console.py [--rotated] [--cell WxH] <screenshot.ppm>"
        )
    try:
        if rotated:
            print(check_rotated(Path(arguments[0]), cell))
        else:
            print(check(Path(arguments[0]), cell))
    except CheckFailed as error:
        raise SystemExit(f"console check failed: {error}")

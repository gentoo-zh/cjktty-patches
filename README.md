[English](README.md) | [简体中文](README.zh-CN.md) | [正體中文](README.zh-TW.md)

# cjktty-patches

cjktty-patches is a framebuffer-console CJK rendering patch collection used by
`gentoo-zh/overlay` for Gentoo kernels and selected CachyOS and XanMod kernels.

The patches are based on
[gentoo-zh/linux-cjktty](https://github.com/gentoo-zh/linux-cjktty);
[CHANGELOG.md](CHANGELOG.md) records the fixes added by this repository.

- Linux 5.10 renamed kernel configuration option `CONFIG_FONT_16x16_CJK` to `CONFIG_FONT_CJK_16x16`.
- The 32x32 font-data patch provides a larger font for high-resolution screens.
- The built-in CJK bitmap data requires 8x16 or 16x32 base-font geometry;
  other base-font sizes may render characters incorrectly.
- The current CJK bitmap data is derived from [GNU Unifont](https://savannah.gnu.org/projects/unifont) 15.1.04. The 32x32 halfwidth range comes from [Terminus Font](http://terminus-font.sourceforge.net) via the mainline kernel's `font_ter16x32.c`.

## Updates

**Font data and code are separate patches: all eight kernels share one 12 MB font patch, and each kernel has a 33–44 KB code patch.**

### 2026.8.20 / 5.10.265, 5.15.216, 6.1.183, 6.6.152, 6.12.104, 6.18.45, 7.1.9

- Add patches for the point releases above.
- Upstream clamps the cursor glyph index to `vc_font.charcount` in `bit_cursor()`, so seven branches rejected the hunk. `font_bits()` gains the bound the 6.1, 5.15 and 5.10 patches already carry.

### 2026.8.17 / 7.2

- Add patches for Linux 7.2, carrying the bytes the 7.2-rc7 patch already had.
- The combined form is planned to end with Linux 7.3.

### 2026.8.12 / 5.10.264, 5.15.215, 6.1.182, 6.6.151, 6.12.103, 6.18.44, 7.1.8, 7.2-rc7

- When the primary cell held a marker, `screen_glyph()` returned the private-plane codepoint. The selection test `(screen_glyph(...) & 0xff) == 0xfe` therefore compared that codepoint's low byte and copied a CJK character twice unless the low byte happened to be `0xfe`. The new `is_cjk_continuation()` reads the raw primary word and compares `glyph & (vc_hi_font_mask | 0xff)` with `0xfe`.
- Glyph `0x1fe` was tested before `vc_hi_font_mask` restored bit 8, so it was mistaken for a continuation cell. `is_cjk_continuation()` now compares the complete glyph value including the high-font bit.
- The `continue` after assigning the marker skipped the value upstream retains in the second cell: a space through 6.12 and `U+200B` from 6.18. As a result, `/dev/vcsu` returned the codepoint in both cells of a CJK glyph. The Unicode screen now keeps the upstream value, and only the private plane receives the codepoint.
- On Linux 5.10 through 6.12, an in-range unimap result bypassed the marker assignment inside the glyph-not-found branch, so one half of a glyph could come from a loaded font and the other from the built-in CJK font. The marker assignment no longer depends on that branch.
- `utf8_pos()` reads the second word of its argument, but `con_putc()` supplies one `u16` from 6.6 onward and supplied a zero second word before that. The software cursor over a CJK cell therefore drew from the wrong font-table entry. `add_softcursor()` and `hide_softcursor()` now pass both cells through `con_putcs()`.
- The auxiliary rotated buffer is built only for a loaded font, leaving `fd_size_utf` at zero for the built-in font. Every lookup then fell back to the main rotated buffer's `0xff` or `0xfe` entry, so a rotated console drew the marker entry instead of the corresponding CJK half. `font_bits()` now bounds the offset against the buffer it indexes.
- The auxiliary rotation helper's `-ENOENT` or `-ENOMEM` was discarded, and its cache key had already been updated so the operation could not retry. A failed auxiliary rotation therefore reported success. The status is now returned and propagated, and fbcon falls back to unrotated rendering.
- The private plane moved inside `vc_uniscr_scroll()`, while `SCROLL_PAN_REDRAW` subsequently passed the pre-scroll rows to the console driver. Scrolling therefore paired a primary row with the wrong private row. The private move now occurs after that callback.
- A write updated only the target cell, so writing a character through `/dev/vcs` or `/dev/vcsa` left half of the old glyph beside the new character. `vcs_scr_writew()` now invalidates the touched private cell and its marker partner and redraws both, while leaving the private plane unchanged for an attribute-only write.
- Linux 6.1's unique `is_double_width()` table did not match the Unifont 15.1.04 used to generate the arrays. It marked 21 narrow glyphs as wide and missed 16 wide glyphs, so U+2648 consumed a blank second cell and U+2605 lost its right half. The table is now rebuilt from the same font as the arrays.
- The console buffer was validated against `KMALLOC_MAX_SIZE` and then allocated at twice that size, so a geometry accepted by the check could not be allocated with `CONFIG_FONT_CJK` enabled. The limit now matches the allocation size.
- `c_utf` is a `u16`, while the descriptor's `charcount` is `65536 * 2`, so `c_utf >= font->charcount` never rejected a glyph. Any descriptor-based bound has the same problem, so the condition was removed without a replacement.
- Each patch had 17 to 21 `IS_ENABLED(CONFIG_FONT_CJK)` conditions inside `#ifdef CONFIG_FONT_CJK`, where they could not be false. The rotated-buffer allocation flags also differed between 5.x and 6.x without a kernel requirement. The redundant conditions are removed and the allocation flags are now consistent.
- Add patches for all eight kernels listed by kernel.org on 2026-08-11.
- Rebuild the 5.10, 5.15 and 6.1 fonts from Unifont 15.1.04, so all eight kernels now draw the same glyphs.
- Ship a split form for every maintained kernel: one shared font patch and a 33–44 KB code patch, against a 12 MB combined file.
- Name the font source in `font_cjk_16x16.c` and `font_cjk_32x32.c`.

- Preallocate the rotated 32x32 buffer with `kvmalloc_array` on 7.1.x, which otherwise drew two glyphs and reported success.
- Build no CJK font objects when both CJK font options are off.
- Default `CONFIG_FONT_CJK_32x32` off. Earlier patches carried no 32x32 font data, so `font_cjk_32x32.h` was empty, while the option had defaulted to on since it arrived in 2021; the build therefore compiled 8 MiB of zeros into the kernel and reported success.
- Order the 5.10 `font_cjk_32x32` descriptor like every other patch, so the 32x32 data patch applies there at all.
- Advance `clear` with `dst` and `src` when scrolling, so the second `memset` clears the Unicode plane instead of overwriting the erase character.
- Skip the cell after a CJK glyph according to the glyph's `0xfe` marker rather than any codepoint above U+0080; the previous test lost the character beside a narrow glyph.
- Redraw a highlighted CJK cell through `con_putcs`, since Linux 6.6 narrowed the `fbcon_putc` argument to one `u16`.
- Set `FB_CUR_SETIMAGE` on the rotated cursor paths, which a hardware cursor backend needs to pick up a new bitmap.
- Describe both font options in four lines of help, and state what each costs.
- Move the Unicode plane with the primary plane. Inserting cells into a line holding CJK lost the first glyph and left a stray character at the end; `vc_uniscr_insert()`, `vc_uniscr_delete()`, `vc_uniscr_clear_line()`, `vc_uniscr_clear_lines()`, and `vc_uniscr_scroll()` cover `CSI @`, `CSI P`, insert mode, clears, and the alternate screen.
- Address the Unicode plane from `vc_screenbuf` rather than `vc_pos`, so the plane points into allocated memory instead of memory held by the console driver.

### 2026.8.8 / 6.12.102, 6.18, 7.1.7

- Add patches for linux 6.12.102 and 6.18.
- Update for linux 7.1.7.
- Free the CJK font buffers with `kvfree`, and release `fontbuffer_utf`, which was never freed.
- Fix the builds of 6.12.63, 6.16 and 6.17.8.

Complete release history is recorded in [CHANGELOG.md](CHANGELOG.md).

## Usage

[SUPPORTED.md](SUPPORTED.md) names the tested patch for each maintained kernel.
From the kernel source root, with the patch repository at
`../cjktty-patches`, run:

```sh
patch -p1 --fuzz=0 < ../cjktty-patches/v6.x/cjktty-6.18.patch
```

The split form is one shared font patch and one code patch per kernel, and
produces a byte-identical source tree:

```sh
patch -p1 --fuzz=0 < ../cjktty-patches/cjktty-font-unifont-15.1.04.patch
patch -p1 --fuzz=0 < ../cjktty-patches/v6.x/cjktty-code-6.18.patch
```

The combined form is planned to end with Linux 7.3, after which only the split
form is published.

Enable all following kernel options:

- `CONFIG_FONTS=y`
- `CONFIG_FONT_CJK_16x16=y`
- `CONFIG_FRAMEBUFFER_CONSOLE=y`

The 32x32 font also requires the data patch:

```sh
patch -p1 --fuzz=0 < ../cjktty-patches/cjktty-add-cjk32x32-font-data.patch
```

After applying the data patch, enable `CONFIG_FONT_CJK_32x32=y`. The option
defaults off.

A framebuffer console is required; `vgacon` cannot display CJK.

## History

| Years | Where |
|---|---|
| 2011–2020 | [gentoo-zh/linux-cjktty](https://github.com/gentoo-zh/linux-cjktty), by microcai, one branch per kernel |
| 2020–2024 | [zhmars/cjktty-patches](https://github.com/zhmars/cjktty-patches), extracted into a patch collection |
| 2022– | [bigshans/cjktty-patches](https://github.com/bigshans/cjktty-patches), still maintained; source of the current fork |

## License

Except for the 32x32 font data, the patch collection is licensed under
[GPL-2.0-only](LICENSE). The 32x32 font data is licensed under OFL-1.1;
`LICENSE` contains both complete license texts and the font copyright notices.

## Credits

- [youbest](http://blog.chinaunix.net/uid/436750.html) for [original univt patches](https://github.com/zhmars/univt-patches/tree/master/v2.6)
- [microcai](https://github.com/microcai) and [gentoo-zh/linux-cjktty](https://github.com/gentoo-zh/linux-cjktty) for original cjktty patches
- [AOSC-Dev/aosc-os-abbs](https://github.com/AOSC-Dev/aosc-os-abbs) for some univt's modifications
- [Unifont](https://savannah.gnu.org/projects/unifont) for font data
- [Terminus Font](http://terminus-font.sourceforge.net) for font data

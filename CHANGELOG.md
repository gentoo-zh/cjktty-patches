# Changes

## 2026.8.17 / 7.2

- Add patches for Linux 7.2. The 7.2-rc7 patch applies to 7.2 unchanged, so the
  new files carry the same bytes under the release name and a 7.2 tree no longer
  applies a file named after a release candidate.
- The combined form is planned to end with Linux 7.3. From that series the shared
  font patch and the per-kernel code patch become the only published form.

## 2026.8.12 / 5.10.264, 5.15.215, 6.1.182, 6.6.151, 6.12.103, 6.18.44, 7.1.8, 7.2-rc7

- When the primary cell held a marker, `screen_glyph()` returned the private-plane
  codepoint. The selection test `(screen_glyph(...) & 0xff) == 0xfe` therefore
  compared that codepoint's low byte and copied a CJK character twice unless the low
  byte happened to be `0xfe`. The new
  `is_cjk_continuation()` reads the raw primary word and compares
  `glyph & (vc_hi_font_mask | 0xff)` with `0xfe`.
- Glyph `0x1fe` was tested before `vc_hi_font_mask` restored bit 8, so it was
  mistaken for a continuation cell. `is_cjk_continuation()` now compares the
  complete glyph value including the high-font bit.
- The `continue` after assigning the marker skipped the value upstream retains in
  the second cell: a space through 6.12 and `U+200B` from 6.18. As a result,
  `/dev/vcsu` returned the codepoint in both cells of a CJK glyph. The Unicode
  screen now keeps the upstream value, and only the private plane receives the codepoint.
- On Linux 5.10 through 6.12, an in-range unimap result bypassed the marker
  assignment inside the glyph-not-found branch, so one half of a glyph could come
  from a loaded font and the other from the built-in CJK font. The marker assignment
  no longer depends on that branch.
- `utf8_pos()` reads the second word of its argument, but `con_putc()` supplies
  one `u16` from 6.6 onward and supplied a zero second word before that. The software
  cursor over a CJK cell therefore drew from the wrong font-table entry.
  `add_softcursor()` and `hide_softcursor()` now pass both cells through `con_putcs()`.
- The auxiliary rotated buffer is built only for a loaded font, leaving
  `fd_size_utf` at zero for the built-in font. Every lookup then fell back to the
  main rotated buffer's `0xff` or `0xfe` entry, so a rotated console drew the
  marker entry instead of the corresponding CJK half. `font_bits()` now bounds the
  offset against the buffer it indexes.
- The auxiliary rotation helper's `-ENOENT` or `-ENOMEM` was discarded, and its
  cache key had already been updated so the operation could not retry. A failed
  auxiliary rotation therefore reported success. The status is now returned and
  propagated, and fbcon falls back to unrotated rendering.
- The private plane moved inside `vc_uniscr_scroll()`, while
  `SCROLL_PAN_REDRAW` subsequently passed the pre-scroll rows to the console driver.
  Scrolling therefore paired a primary row with the wrong private row. The private
  move now occurs after that callback.
- A write updated only the target cell, so writing a character through `/dev/vcs`
  or `/dev/vcsa` left half of the old glyph beside the new character.
  `vcs_scr_writew()` now invalidates the touched private cell and its marker partner
  and redraws both, while leaving the private plane unchanged for an attribute-only write.
- Linux 6.1's unique `is_double_width()` table did not match the Unifont 15.1.04
  used to generate the arrays. It marked 21 narrow glyphs as wide and missed 16 wide
  glyphs, so U+2648 consumed a blank second cell and U+2605 lost its right half. The
  table is now rebuilt from the same font as the arrays.
- The console buffer was validated against `KMALLOC_MAX_SIZE` and then allocated at
  twice that size, so a geometry accepted by the check could not be allocated with
  `CONFIG_FONT_CJK` enabled. The limit now matches the allocation size.
- `c_utf` is a `u16`, while the descriptor's `charcount` is `65536 * 2`, so
  `c_utf >= font->charcount` never rejected a glyph. Any descriptor-based bound has
  the same problem, so the condition was removed without a replacement.
- Each patch had 17 to 21 `IS_ENABLED(CONFIG_FONT_CJK)` conditions inside
  `#ifdef CONFIG_FONT_CJK`, where they could not be false. The rotated-buffer
  allocation flags also differed between 5.x and 6.x without a kernel requirement.
  The redundant conditions are removed and the allocation flags are now consistent.

- Add patches for all eight kernels listed by kernel.org on 2026-08-11.
- Rebuild the 5.10, 5.15 and 6.1 fonts from Unifont 15.1.04, so all eight
  kernels now draw the same glyphs.
- Ship a split form for every maintained kernel: one shared font patch and a
  33–44 KB code patch, against a 12 MB combined file.
- Name the font source in `font_cjk_16x16.c` and `font_cjk_32x32.c`.

- Preallocate the rotated 32x32 buffer with `kvmalloc_array` on 7.1.x, which
  otherwise drew two glyphs and reported success.
- Build no CJK font objects when both CJK font options are off.
- Default `CONFIG_FONT_CJK_32x32` off. Earlier patches carried no 32x32 font data, so `font_cjk_32x32.h` was empty, while the option had defaulted to on since it arrived in 2021; the build therefore compiled 8 MiB of zeros into the kernel and reported success.
- Order the 5.10 `font_cjk_32x32` descriptor like every other patch, so the 32x32 data patch
  applies there at all.
- Advance `clear` with `dst` and `src` when scrolling, so the second `memset`
  clears the Unicode plane instead of overwriting the erase character.
- Skip the cell after a CJK glyph according to the glyph's `0xfe` marker rather than any
  codepoint above U+0080; the previous test lost the character beside a narrow glyph.
- Redraw a highlighted CJK cell through `con_putcs`, since Linux 6.6 narrowed
  the `fbcon_putc` argument to one `u16`.
- Set `FB_CUR_SETIMAGE` on the rotated cursor paths, which a hardware cursor
  backend needs to pick up a new bitmap.
- Describe both font options in four lines of help, and state what each costs.
- Move the Unicode plane with the primary plane. Inserting cells into a line holding CJK
  lost the first glyph and left a stray character at the end;
  `vc_uniscr_insert()`, `vc_uniscr_delete()`, `vc_uniscr_clear_line()`,
  `vc_uniscr_clear_lines()`, and `vc_uniscr_scroll()` cover `CSI @`, `CSI P`,
  insert mode, clears, and the alternate screen.
- Address the Unicode plane from `vc_screenbuf` rather than `vc_pos`, so the plane
  points into allocated memory instead of memory held by the console driver.

## 2026.8.8 / 6.12.102, 6.18, 7.1.7

- Add patches for linux 6.12.102 and 6.18.
- Update for linux 7.1.7.
- Free the CJK font buffers with `kvfree`, and release `fontbuffer_utf`, which
  was never freed.
- Fix the builds of 6.12.63, 6.16 and 6.17.8.

## 2026.7.27 / 7.1.2

- Fix `CONFIG_FRAMEBUFFER_CONSOLE_ROTATION` lost.

## 2026.6.17 / 7.1

- Update for linux 7.1

## 2026.4.14 / 7.0

- Update for linux 7.0

## 2026.2.14 / 6.19

- Update for linux 6.19

## 2025.8.2 / 6.16

- Update for linux 6.16

## 2024.5.15 / 6.9

- Update for linux-6.9.y

## 2023.10.30 / 6.6

- Resync for linux-6.6.y
- Update font data to Unifont 15.1.04
- Update double width tables to Unicode 15.1.0

## 2023.06.26 / 6.4

- Resync for linux-6.4.y
- Update font data to Unifont 15.0.06

## 2023.04.24 / 6.3

- Resync for linux-6.3.y
- Rename scroll variables `t`, `b`, `s`, and `d` to `top`, `bottom`, `src`, and
  `dst`, and cache the row count in `con_scroll()` (upstream)
  - [torvalds/linux@424c82a](https://github.com/torvalds/linux/commit/424c82af26b1b8ca6c0be06987a4e6d18c9a92dd)
  - [torvalds/linux@bf8baa0](https://github.com/torvalds/linux/commit/bf8baa00668dbc4fcfca5ac49ae8a3059c795e4e)

## 2022.10.03 / 6.0

- Resync for linux-6.0.y
- Update font data to Unifont 15.0.01
- Update double width tables to Unicode 15.0.0
- Minor cleanups

## 2022.08.01 / 5.19

- Resync for linux-5.19.y
- Update font data to Unifont 14.0.04
- Update double width tables to Unicode 14.0.0
- Fix cutoff issue for double width glyphs from Unifont (e.g.`①  ②  ③ `)
- Avoid unnecessary check of characters width
- Remove workaround from [gentoo-zh/linux-cjktty@6caf83a](https://github.com/gentoo-zh/linux-cjktty/commit/6caf83a638886220d1e1880c92e8b18243c3965a)

## 2022.05.23 / 5.18

- Resync for linux-5.18.y
- Fix build warnings with GCC 12 (`-Wbidi-chars=unpaired`)

## 2022.03.21 / 5.17

- Resync for linux-5.17.y
- Update font data to Unifont 14.0.02
- Revert scroll acceleration code (upstream)
  - [torvalds/linux@1148836](https://github.com/torvalds/linux/commit/1148836fd3226c20de841084aba24184d4fbbe77)

## 2022.01.10 / 5.16

- Resync for linux-5.16.y
- Remove scroll acceleration code (upstream)
  - [torvalds/linux@b3ec8cd](https://github.com/torvalds/linux/commit/b3ec8cdf457e5e63d396fe1346cc788cf7c1b578)

## 2021.09.17 / 5.14.5

- Update font data to Unifont 14.0.01
- Replace original 16x16 font with Unifont for better unicode support

## 2021.02.22 / 5.11

- Resync for linux-5.11.y
- Update CJK 32x32 font data to Unifont 13.0.06
- Reduce checkpatch.pl complaints
- Remove charcount changes after upstream implemented `charcount`
  - [torvalds/linux@4ee5730](https://github.com/torvalds/linux/commit/4ee573086bd88ff3060dda07873bf755d332e9ba)
  - [torvalds/linux@a1ac250](https://github.com/torvalds/linux/commit/a1ac250a82a5e97db71f14101ff7468291a6aaef)

## 2020.12.14 / 5.10

- Resync for linux-5.10.y
- Update glyphs for some Chinese punctuation marks
- Support display rotation
- Support `setfont`. cjktty expects 8x16 or 16x32 cell geometry; other sizes may display incorrectly
- Fix display for some single width characters
- Fix line wrap for double width characters (<https://github.com/zhmars/cjktty-patches/issues/1>)
- Workaround from [gentoo-zh/linux-cjktty@6caf83a](https://github.com/gentoo-zh/linux-cjktty/commit/6caf83a638886220d1e1880c92e8b18243c3965a)
- Support 32x32 font size for high resolution screens (experimental, make sure the font data patch is applied)

## 2020.09.18 / 5.8.10

- Resync for linux-5.8.10
- Remove soft scrollback code (upstream)
  - [torvalds/linux@5014547](https://github.com/torvalds/linux/commit/50145474f6ef4a9c19205b173da6264a644c7489)

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

### 2026.10.20 / 7.3

- Add `v7.x/cjktty-code-7.3.patch` for Linux 7.3, carrying the bytes the 7.3-rc1
  code patch already had. Linux 7.3 is published in split form only: apply
  `cjktty-font-unifont-15.1.04.patch`, then the code patch. The combined form ended
  with Linux 7.2, so there is no `cjktty-7.3.patch`.

### 2026.10.17 / 5.10.272, 5.15.223, 6.1.190, 6.6.159, 6.12.113, 6.18.57, 7.2.11, 7.3-rc7

- Record 5.10.272, 5.15.223, 6.1.190, 6.6.159, 6.12.113, 6.18.57 and 7.2.11 against
  the patches they already use. 6.12.113 changed `drivers/tty/vt/vt.c` and 6.18.57
  changed `fbcon.c`, both outside the patched hunks.

### 2026.10.12 / 6.18.56, 7.2.10, 7.3-rc7

- Record 6.18.56, 7.2.10 and 7.3-rc7 against the patches they already use.
  Each changed `drivers/tty/vt/vt.c` and `selection.c` only outside the patched hunks.

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

The combined form ended with Linux 7.2. From Linux 7.3 on, only the split form
is published.

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

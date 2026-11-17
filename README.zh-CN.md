[English](README.md) | [简体中文](README.zh-CN.md) | [正體中文](README.zh-TW.md)

# cjktty-patches

cjktty-patches 是一组 framebuffer console CJK 渲染补丁，主要为 Gentoo 维护。`gentoo-zh/overlay` 将其用于该仓库中的 Gentoo 内核，以及 CachyOS、XanMod 与 Liquorix 内核。

补丁以 kernel.org 的源代码为基准制作。基于 kernel.org mainline、stable 或 longterm 版本构建的其他内核通常也能应用这些补丁，前提是这些内核未改动补丁修改的控制台源代码，即 `drivers/tty/vt/`、`drivers/video/fbdev/core/`、`lib/fonts/` 以及 `include/linux/` 下的相关头文件。

补丁基于 [gentoo-zh/linux-cjktty](https://github.com/gentoo-zh/linux-cjktty)；本仓库追加的修复记录在 [CHANGELOG.md](CHANGELOG.md)。

- Linux 5.10 将内核配置选项 `CONFIG_FONT_16x16_CJK` 重命名为 `CONFIG_FONT_CJK_16x16`。
- 32x32 字体数据补丁为高分辨率屏幕提供较大的字体。
- 内置 CJK 点阵数据要求基础字体尺寸为 8x16 或 16x32；其他基础字体尺寸可能导致字符显示错误。
- `cjktty-font-unifont-18.0.01.patch` 的 16x16 CJK 点阵数据衍生自 [GNU Unifont](https://savannah.gnu.org/projects/unifont) 18.0.01；合并补丁与 32x32 数据衍生自 Unifont 15.1.04。32x32 数据的半角字符范围取自 [Terminus Font](http://terminus-font.sourceforge.net)，并通过主线内核的 `font_ter16x32.c` 引入。

## 更新

**字体数据与源代码分别存放在不同补丁中：八个内核共用一份 12 MB 字体补丁，每个内核各有一份 33–44 KB 源代码补丁。**

### 2026.11.17 / 5.10.274, 5.15.225, 6.1.192, 6.6.162, 6.12.118, 6.18.64, 7.3.5, 7.4-rc3

- 记录 6.12.118、6.18.64 与 7.3.5，全部沿用原有补丁。6.12.118 与 6.18.64 修改了 `drivers/video/fbdev/core/fbcon_rotate.c`，`par->fontbuffer` 为 NULL 时 `fbcon_rotate_font()` 会重新生成旋转字体；改动不在补丁的 hunk 内。
- 以 `cjktty-font-unifont-18.0.01.patch` 加上这些源代码补丁，以及 6.12.117 与 6.18.63 的合并补丁，都通过了两个测试阶段，因此 `SUPPORTED.md` 改为列出 2026-11-17 的版本。

### 2026.11.16 / 5.10.274, 5.15.225, 6.1.192, 6.6.162, 6.12.117, 6.18.63, 7.3.4, 7.4-rc3

- 新增 `v7.x/cjktty-code-7.4-rc3.patch`，由 `cjktty-code-7.3.4.patch` 移植而来。7.4 以 `fbcon_cursor_glyph()` 取代 `fbcon_fill_cursor_mask()`，而补丁在 `fbcon.h` 中的 `font_bits()` 声明紧邻旧的函数原型，该 hunk 因此改用新的上下文。其余 hunk 均未改动：CJK 光标代码修改的是光标图像，不是 7.4 改写的光标掩码。
- 以 `cjktty-font-unifont-18.0.01.patch` 加上新的源代码补丁，通过了两个测试阶段。
- 5.10.274、5.15.225、6.1.192、6.6.162、6.12.117、6.18.63 与 7.3.4 以 `cjktty-font-unifont-18.0.01.patch` 加上原有的源代码补丁通过了两个测试阶段，因此 `SUPPORTED.md` 改为列出 2026-11-16 的版本。

### 2026.11.15 / 5.10.272, 5.15.223, 6.1.190, 6.6.160, 6.12.114, 6.18.58, 7.2.12, 7.3

- 新增 `cjktty-font-unifont-18.0.01.patch`，以 GNU Unifont 18.0.01 重新生成 16x16 字体数据。拆分形式改为先应用这份字体补丁，再应用源代码补丁。与 15.1.04 相比有 1,004 个 BMP 字形不同：韩文字母 447 个、阿拉伯文 162 个、注音符号 75 个、CJK 表意文字 84 个，其他文字 236 个。
- `cjktty-font-unifont-15.1.04.patch` 的内容保持不变，因为已发布的 ebuild 按文件名获取这份补丁。合并补丁与 32x32 数据补丁仍使用 Unifont 15.1.04 的数据。
- 上列每个内核以新字体补丁加上各自的源代码补丁，通过了两个测试阶段。

完整的版本记录见 [CHANGELOG.md](CHANGELOG.md)。

## 使用

[SUPPORTED.md](SUPPORTED.md) 列出每个维护中内核对应的已测试补丁。在内核源码根目录执行以下命令；补丁仓库路径为 `../cjktty-patches`：

```sh
patch -p1 --fuzz=0 < ../cjktty-patches/v6.x/cjktty-6.18.patch
```

拆分形式是一份共用字体补丁加上每个内核一份代码补丁：

```sh
patch -p1 --fuzz=0 < ../cjktty-patches/cjktty-font-unifont-18.0.01.patch
patch -p1 --fuzz=0 < ../cjktty-patches/v6.x/cjktty-code-6.18.patch
```

以 `cjktty-font-unifont-15.1.04.patch` 替换 18.0.01 字体补丁时，拆分形式得到的源代码树与合并补丁逐字节相同。

合并形式已在 Linux 7.2 终止，自 Linux 7.3 起只发布拆分形式。

启用以下所有内核配置选项：

- `CONFIG_FONTS=y`
- `CONFIG_FONT_CJK_16x16=y`
- `CONFIG_FRAMEBUFFER_CONSOLE=y`

32x32 字体还需要数据补丁：

```sh
patch -p1 --fuzz=0 < ../cjktty-patches/cjktty-add-cjk32x32-font-data.patch
```

应用数据补丁后启用 `CONFIG_FONT_CJK_32x32=y`。该选项默认关闭。

必须使用 framebuffer console；`vgacon` 无法显示 CJK。

## 历史

| 年份 | 位置 |
|---|---|
| 2011–2020 | [gentoo-zh/linux-cjktty](https://github.com/gentoo-zh/linux-cjktty)，由 microcai 维护，每个内核版本各有一个分支 |
| 2020–2024 | [zhmars/cjktty-patches](https://github.com/zhmars/cjktty-patches)，抽取为补丁集合 |
| 2022– | [bigshans/cjktty-patches](https://github.com/bigshans/cjktty-patches)，仍在维护；本仓库由此派生 |

## 许可证

除 32x32 字体数据外，补丁集合采用 [GPL-2.0-only](LICENSE)。32x32 字体数据采用 OFL-1.1；`LICENSE` 包含两种许可证的全文和字体版权声明。

## 致谢

- [youbest](http://blog.chinaunix.net/uid/436750.html) 提供[原始 univt 补丁](https://github.com/zhmars/univt-patches/tree/master/v2.6)
- [microcai](https://github.com/microcai) 和 [gentoo-zh/linux-cjktty](https://github.com/gentoo-zh/linux-cjktty) 提供原始 cjktty 补丁
- [AOSC-Dev/aosc-os-abbs](https://github.com/AOSC-Dev/aosc-os-abbs) 提供部分 univt 修改
- [Unifont](https://savannah.gnu.org/projects/unifont) 提供字体数据
- [Terminus Font](http://terminus-font.sourceforge.net) 提供字体数据

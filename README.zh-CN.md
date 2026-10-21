[English](README.md) | [简体中文](README.zh-CN.md) | [正體中文](README.zh-TW.md)

# cjktty-patches

cjktty-patches 是一组 framebuffer console CJK 渲染补丁，供 `gentoo-zh/overlay` 中的 Gentoo 内核及部分 CachyOS、XanMod 内核使用。

补丁基于 [gentoo-zh/linux-cjktty](https://github.com/gentoo-zh/linux-cjktty)；本仓库追加的修复记录在 [CHANGELOG.md](CHANGELOG.md)。

- Linux 5.10 将内核配置选项 `CONFIG_FONT_16x16_CJK` 重命名为 `CONFIG_FONT_CJK_16x16`。
- 32x32 字体数据补丁为高分辨率屏幕提供较大的字体。
- 内置 CJK 点阵数据要求基础字体尺寸为 8x16 或 16x32；其他基础字体尺寸可能导致字符显示错误。
- 当前的 CJK 点阵字体数据衍生自 [GNU Unifont](https://savannah.gnu.org/projects/unifont) 15.1.04。32x32 数据的半角字符范围取自 [Terminus Font](http://terminus-font.sourceforge.net)，并通过主线内核的 `font_ter16x32.c` 引入。

## 更新

**字体数据与源代码分别存放在不同补丁中：八个内核共用一份 12 MB 字体补丁，每个内核各有一份 33–44 KB 源代码补丁。**

### 2026.10.22 / 5.10.272, 5.15.223, 6.1.190, 6.6.160, 6.12.114, 6.18.58, 7.2.12, 7.3

- 记录 6.6.160、6.12.114、6.18.58 与 7.2.12，全部沿用原有补丁。6.6.160 修改了 `drivers/tty/vt/vt.c` 与 `fbcon.c`，6.12.114 修改了 `fbcon.c`，改动都不在补丁的 hunk 内。

### 2026.10.20 / 7.3

- 新增 Linux 7.3 的 `v7.x/cjktty-code-7.3.patch`，内容与 7.3-rc1 的源代码补丁相同。Linux 7.3 只发布拆分形式：先应用 `cjktty-font-unifont-15.1.04.patch`，再应用源代码补丁。合并形式已在 Linux 7.2 终止，因此不提供 `cjktty-7.3.patch`。

### 2026.10.17 / 5.10.272, 5.15.223, 6.1.190, 6.6.159, 6.12.113, 6.18.57, 7.2.11, 7.3-rc7

- 记录 5.10.272、5.15.223、6.1.190、6.6.159、6.12.113、6.18.57 与 7.2.11，全部沿用原有补丁。6.12.113 修改了 `drivers/tty/vt/vt.c`，6.18.57 修改了 `fbcon.c`，改动都不在补丁的 hunk 内。

完整的版本记录见 [CHANGELOG.md](CHANGELOG.md)。

## 使用

[SUPPORTED.md](SUPPORTED.md) 列出每个维护中内核对应的已测试补丁。在内核源码根目录执行以下命令；补丁仓库路径为 `../cjktty-patches`：

```sh
patch -p1 --fuzz=0 < ../cjktty-patches/v6.x/cjktty-6.18.patch
```

拆分形式是一份共用字体补丁加上每个内核一份代码补丁，得到的源代码树逐字节相同：

```sh
patch -p1 --fuzz=0 < ../cjktty-patches/cjktty-font-unifont-15.1.04.patch
patch -p1 --fuzz=0 < ../cjktty-patches/v6.x/cjktty-code-6.18.patch
```

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

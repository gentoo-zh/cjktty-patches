[简体中文](README.md) | [English](README.en.md) | [正體中文](README.zh-TW.md) | [日本語](README.ja.md) | [한국어](README.ko.md)

# cjktty-patches

cjktty-patches 是一组 framebuffer console CJK 渲染补丁，供 `gentoo-zh/overlay` 中的 Gentoo 内核及部分 CachyOS、XanMod 内核使用。

补丁基于 [gentoo-zh/linux-cjktty](https://github.com/gentoo-zh/linux-cjktty)；本仓库追加的修复记录在 [CHANGELOG.zh-CN.md](CHANGELOG.zh-CN.md)。

- Linux 5.10 将内核配置选项 `CONFIG_FONT_16x16_CJK` 重命名为 `CONFIG_FONT_CJK_16x16`。
- 32x32 字体数据补丁为高分辨率屏幕提供较大的字体。
- 内置 CJK 点阵数据要求基础字体尺寸为 8x16 或 16x32；其他基础字体尺寸可能导致字符显示错误。
- 当前的 CJK 点阵字体数据衍生自 [GNU Unifont](https://savannah.gnu.org/projects/unifont) 15.1.04。32x32 数据的半角字符范围取自 [Terminus Font](http://terminus-font.sourceforge.net)，并通过主线内核的 `font_ter16x32.c` 引入。

## 更新

**字体数据与源代码分别存放在不同补丁中：八个内核共用一份 12 MB 字体补丁，每个内核各有一份 33–44 KB 源代码补丁。**

### 2026.8.12 / 5.10.264, 5.15.215, 6.1.182, 6.6.151, 6.12.103, 6.18.44, 7.1.8, 7.2-rc7

- `screen_glyph()` 在主单元格含标记时改为返回私有平面的码位。选取检查 `(screen_glyph(...) & 0xff) == 0xfe` 因此比较该码位的低字节，低字节并非 `0xfe` 的 CJK 字符会复制两次。新增的 `is_cjk_continuation()` 直接读取主平面的原始字，并将 `glyph & (vc_hi_font_mask | 0xff)` 与 `0xfe` 比较。
- 字形 `0x1fe` 在 `vc_hi_font_mask` 恢复第 8 位之前接受判断，所以曾被误认为续接单元格；`is_cjk_continuation()` 改为比较包含高字体位的完整字形值。
- 设置标记后的 `continue` 跳过了上游为第二个单元格保留的值：截至 6.12 为空格，从 6.18 起为 `U+200B`。`/dev/vcsu` 因此曾在 CJK 字形的两个单元格中都返回该码位；Unicode 屏幕现保留上游值，码位只写入私有平面。
- Linux 5.10 至 6.12 在 unimap 返回范围内字形时会绕过位于“未找到字形”分支内的标记赋值，所以一个字形的一半可能来自已加载字体，另一半来自内置 CJK 字体；标记赋值现不再受该分支限制。
- `utf8_pos()` 读取参数的第二个字，而 `con_putc()` 从 6.6 起只提供一个 `u16`，更早版本提供的第二个字为零，导致 CJK 单元格上的软件光标从错误的字体表条目绘制；`add_softcursor()` 和 `hide_softcursor()` 现通过 `con_putcs()` 传入两个单元格。
- 辅助旋转缓冲区只为已加载字体建立，导致 `fd_size_utf` 为零。所有查找因此都回退到主旋转缓冲区的 `0xff` 或 `0xfe` 条目，使用内置字体时，旋转后的控制台会绘制标记条目而非 CJK 的对应半边；`font_bits()` 现按照实际索引的缓冲区限制偏移量。
- 辅助函数的 `-ENOENT` 或 `-ENOMEM` 被丢弃，且缓存键已更新而无法重试，所以辅助旋转失败时曾报告成功；状态现会返回并向上传递，使 fbcon 回退到未旋转绘制。
- 私有平面在 `vc_uniscr_scroll()` 内移动，而 `SCROLL_PAN_REDRAW` 随后仍把滚动前的行传给控制台驱动，导致主平面的一行与错误的私有平面行配对；私有平面现改为在该回调后移动。
- 写入只更新了目标单元格，所以通过 `/dev/vcs` 或 `/dev/vcsa` 写入字符后，旧字形的一半会留在新字符旁；`vcs_scr_writew()` 现使触及的私有单元格及其标记配对单元格失效并重绘两者，写入仅含属性时则不改动私有平面。
- Linux 6.1 独有的 `is_double_width()` 表与生成数组的 Unifont 15.1.04 不一致。该表误将 21 个窄字形标为宽字形并漏掉 16 个宽字形，导致 U+2648 占用一个空白的第二单元格，而 U+2605 丢失右半边；该表现由生成数组所用的同一字体重建。
- 控制台缓冲区按 `KMALLOC_MAX_SIZE` 验证，却按该大小的两倍分配，所以启用 `CONFIG_FONT_CJK` 后，检查接受的控制台尺寸无法分配；上限现与实际分配大小一致。
- `c_utf` 为 `u16`，但描述符的 `charcount` 为 `65536 * 2`，所以 `c_utf >= font->charcount` 从未拒绝任何字形。任何基于该描述符的边界检查都有相同问题，因此直接删除了这个条件。
- 每份补丁中有 17 至 21 个 `IS_ENABLED(CONFIG_FONT_CJK)` 条件位于 `#ifdef CONFIG_FONT_CJK` 内部，因而不可能为假。旋转缓冲区的分配标志也在 5.x 与 6.x 之间无故不同；现已删除这些冗余条件，并统一分配标志。
- 为 kernel.org 在 2026-08-11 列出的八个内核添加补丁。
- 使用 Unifont 15.1.04 重新构建 5.10、5.15 和 6.1 的字体，使八个内核绘制相同的字形。
- 为每个维护中的内核提供拆分形式：一份共用字体补丁和一份 33–44 KB 的源代码补丁，对应原有的 12 MB 合并文件。
- 在 `font_cjk_16x16.c` 和 `font_cjk_32x32.c` 中注明字体来源。

- 在 7.1.x 上使用 `kvmalloc_array` 预先分配旋转后的 32x32 缓冲区；否则系统只绘制两个字形，却仍报告成功。
- 两个 CJK 字体选项均关闭时，Makefile 不再生成 CJK 字体对象。
- 将 `CONFIG_FONT_CJK_32x32` 设为默认关闭。基础补丁中的 `font_cjk_32x32.h` 为空，而这个选项自 2021 年加入以来一直默认开启，所以构建会把 8 MiB 的全零数据编入内核并报告成功。
- 按照其他补丁的顺序排列 5.10 的 `font_cjk_32x32` 描述符，使 32x32 数据补丁能够应用到 5.10。
- 滚动时让 `clear` 随 `dst` 和 `src` 一同前移，使第二次 `memset` 清除 Unicode 平面，而不是覆盖擦除字符。
- 根据 CJK 字形的 `0xfe` 标记跳过其后的单元格，不再根据高于 U+0080 的任意码位判断；旧判断会丢失窄字符旁的字符。
- 通过 `con_putcs` 重绘高亮的 CJK 单元格，因为从 6.6 起，`fbcon_putc` 已将参数缩窄为一个 `u16`。
- 在旋转光标路径中设置 `FB_CUR_SETIMAGE`，使硬件光标后端能够取得新的位图。
- 使用四行帮助文本说明两个字体选项，并注明各自的开销。
- 让 Unicode 平面随主平面一同移动。在含 CJK 的行中插入单元格会丢失该行第一个字形，并在行尾留下无关字符；`vc_uniscr_insert()`、`vc_uniscr_delete()`、`vc_uniscr_clear_line()`、`vc_uniscr_clear_lines()` 和 `vc_uniscr_scroll()` 共同覆盖 `CSI @`、`CSI P`、插入模式、清除与备用屏幕。
- Unicode 平面改为从 `vc_screenbuf` 定址，而不是 `vc_pos`，使平面地址指向分配的内存，而非控制台驱动持有的内存。

### 2026.8.8 / 6.12.102, 6.18, 7.1.7

- 添加适用于 linux 6.12.102 和 6.18 的补丁。
- 更新至 linux 7.1.7。
- 使用 `kvfree` 释放 CJK 字体缓冲区，并释放此前从未释放的 `fontbuffer_utf`。
- 修复 6.12.63、6.16 和 6.17.8 的构建。

完整的版本记录见 [CHANGELOG.zh-CN.md](CHANGELOG.zh-CN.md)。

## 使用

[SUPPORTED.md](SUPPORTED.md) 列出每个维护中内核对应的已测试补丁。在内核源码根目录执行以下命令；补丁仓库路径为 `../cjktty-patches`：

```sh
patch -p1 --fuzz=0 < ../cjktty-patches/v6.x/cjktty-6.18.patch
```

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

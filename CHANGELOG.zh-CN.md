[简体中文](CHANGELOG.zh-CN.md) | [English](CHANGELOG.md) | [正體中文](CHANGELOG.zh-TW.md) | [日本語](CHANGELOG.ja.md) | [한국어](CHANGELOG.ko.md)

# 变更记录

## 2026.8.12 / 5.10.264, 5.15.215, 6.1.182, 6.6.151, 6.12.103, 6.18.44, 7.1.8, 7.2-rc7

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

## 2026.8.8 / 6.12.102, 6.18, 7.1.7

- 添加适用于 linux 6.12.102 和 6.18 的补丁。
- 更新至 linux 7.1.7。
- 使用 `kvfree` 释放 CJK 字体缓冲区，并释放此前从未释放的 `fontbuffer_utf`。
- 修复 6.12.63、6.16 和 6.17.8 的构建。

## 2026.7.27 / 7.1.2

- 修复 `CONFIG_FRAMEBUFFER_CONSOLE_ROTATION` 丢失的问题。

## 2026.6.17 / 7.1

- 更新至 linux 7.1。

## 2026.4.14 / 7.0

- 更新至 linux 7.0。

## 2026.2.14 / 6.19

- 更新至 linux 6.19。

## 2025.8.2 / 6.16

- 更新至 linux 6.16。

## 2024.5.15 / 6.9

- 重新同步至 linux-6.9.y。

## 2023.10.30 / 6.6

- 重新同步至 linux-6.6.y。
- 将字体数据更新至 Unifont 15.1.04。
- 将双宽字符表更新至 Unicode 15.1.0。

## 2023.06.26 / 6.4

- 重新同步至 linux-6.4.y。
- 将字体数据更新至 Unifont 15.0.06。

## 2023.04.24 / 6.3

- 重新同步至 linux-6.3.y。
- 将滚动变量 `t`、`b`、`s` 和 `d` 重命名为 `top`、`bottom`、`src` 和 `dst`，并在 `con_scroll()` 中缓存行数（上游）。
  - [torvalds/linux@424c82a](https://github.com/torvalds/linux/commit/424c82af26b1b8ca6c0be06987a4e6d18c9a92dd)
  - [torvalds/linux@bf8baa0](https://github.com/torvalds/linux/commit/bf8baa00668dbc4fcfca5ac49ae8a3059c795e4e)

## 2022.10.03 / 6.0

- 重新同步至 linux-6.0.y。
- 将字体数据更新至 Unifont 15.0.01。
- 将双宽字符表更新至 Unicode 15.0.0。
- 进行小幅清理。

## 2022.08.01 / 5.19

- 重新同步至 linux-5.19.y。
- 将字体数据更新至 Unifont 14.0.04。
- 将双宽字符表更新至 Unicode 14.0.0。
- 修复 Unifont 双宽字形被截断的问题（例如 `①  ②  ③ `）。
- 避免不必要的字符宽度检查。
- 移除来自 [gentoo-zh/linux-cjktty@6caf83a](https://github.com/gentoo-zh/linux-cjktty/commit/6caf83a638886220d1e1880c92e8b18243c3965a) 的临时解决方案。

## 2022.05.23 / 5.18

- 重新同步至 linux-5.18.y。
- 修复 GCC 12 的构建警告（`-Wbidi-chars=unpaired`）。

## 2022.03.21 / 5.17

- 重新同步至 linux-5.17.y。
- 将字体数据更新至 Unifont 14.0.02。
- 撤销滚动加速代码（上游）。
  - [torvalds/linux@1148836](https://github.com/torvalds/linux/commit/1148836fd3226c20de841084aba24184d4fbbe77)

## 2022.01.10 / 5.16

- 重新同步至 linux-5.16.y。
- 移除滚动加速代码（上游）。
  - [torvalds/linux@b3ec8cd](https://github.com/torvalds/linux/commit/b3ec8cdf457e5e63d396fe1346cc788cf7c1b578)

## 2021.09.17 / 5.14.5

- 将字体数据更新至 Unifont 14.0.01。
- 使用 Unifont 替换原有 16x16 字体，以改善 Unicode 支持。

## 2021.02.22 / 5.11

- 重新同步至 linux-5.11.y。
- 将 CJK 32x32 字体数据更新至 Unifont 13.0.06。
- 减少 checkpatch.pl 报告的问题。
- 上游已实现 charcount，因此移除相关改动。
  - [torvalds/linux@4ee5730](https://github.com/torvalds/linux/commit/4ee573086bd88ff3060dda07873bf755d332e9ba)
  - [torvalds/linux@a1ac250](https://github.com/torvalds/linux/commit/a1ac250a82a5e97db71f14101ff7468291a6aaef)

## 2020.12.14 / 5.10

- 重新同步至 linux-5.10.y。
- 更新部分中文标点符号的字形。
- 支持显示旋转。
- 支持 `setfont`。cjktty 预期使用 8x16 或 16x32 单元格，其他尺寸可能无法正确显示。
- 修复部分单宽字符的显示。
- 修复双宽字符的换行（<https://github.com/zhmars/cjktty-patches/issues/1>）。
- 应用来自 [gentoo-zh/linux-cjktty@6caf83a](https://github.com/gentoo-zh/linux-cjktty/commit/6caf83a638886220d1e1880c92e8b18243c3965a) 的临时解决方案。
- 支持高分辨率屏幕使用 32x32 字体尺寸。此功能为实验性功能，必须确保已应用字体数据补丁。

## 2020.09.18 / 5.8.10

- 重新同步至 linux-5.8.10。
- 移除 soft scrollback 代码（上游）。
  - [torvalds/linux@5014547](https://github.com/torvalds/linux/commit/50145474f6ef4a9c19205b173da6264a644c7489)

[English](README.md) | [简体中文](README.zh-CN.md) | [正體中文](README.zh-TW.md)

# cjktty-patches

cjktty-patches 是一組 framebuffer console CJK 渲染補丁，主要為 Gentoo 維護。`gentoo-zh/overlay` 將其用於該倉庫中的 Gentoo 核心，以及 CachyOS、XanMod 與 Liquorix 核心。

補丁以 kernel.org 的原始碼為基準製作。以 kernel.org mainline、stable 或 longterm 版本建置的其他核心通常也能套用這些補丁，前提是這些核心未改動補丁修改的主控台原始碼，即 `drivers/tty/vt/`、`drivers/video/fbdev/core/`、`lib/fonts/` 以及 `include/linux/` 下的相關標頭檔。

補丁以 [gentoo-zh/linux-cjktty](https://github.com/gentoo-zh/linux-cjktty) 為基礎；本倉庫新增的修正記錄於 [CHANGELOG.md](CHANGELOG.md)。

- Linux 5.10 將核心設定選項 `CONFIG_FONT_16x16_CJK` 重新命名為 `CONFIG_FONT_CJK_16x16`。
- 32x32 字型資料補丁為高解析度螢幕提供較大的字型。
- 內建 CJK 點陣資料要求基礎字型尺寸為 8x16 或 16x32；其他基礎字型尺寸可能導致字元顯示錯誤。
- 目前的 CJK 點陣字型資料衍生自 [GNU Unifont](https://savannah.gnu.org/projects/unifont) 15.1.04。32x32 資料的半形字元範圍取自 [Terminus Font](http://terminus-font.sourceforge.net)，並經由主線核心的 `font_ter16x32.c` 引入。

## 更新

**字型資料與原始碼分別存放在不同補丁中：八個核心共用一份 12 MB 字型補丁，每個核心各有一份 33–44 KB 原始碼補丁。**

### 2026.11.11 / 5.10.274, 5.15.225, 6.1.192, 6.6.162, 6.12.117, 6.18.63, 7.3.4

- 新增 `v6.x/cjktty-6.12.117.patch` 與 `v6.x/cjktty-6.18.63.patch` 及對應的原始碼補丁。這兩個版本在 `bitblit.c` 中新增 `#include "fbcon_rotate.h"`，補丁第一個 hunk 的上下文因此改變；其餘 hunk 均未改動。
- 新增 `v7.x/cjktty-code-7.3.4.patch`。7.3.4 將旋轉字型的狀態移入 `struct fbcon_rotated`，並由 `fbcon_do_set_font()` 重建該狀態、釋放被取代的緩衝區。CJK 緩衝區欄位因此移入該結構，更換字型時也一併釋放 CJK 緩衝區；補丁以 `kvmalloc_array()` 配置這兩個緩衝區，所以釋放時使用 `kvfree()`。
- 記錄 5.10.274、5.15.225、6.1.192 與 6.6.162，全部沿用原有補丁。6.1.191 修改了 `drivers/tty/vt/vt.c` 與 `fbcon.c`，改動都不在補丁的 hunk 內。
- `SUPPORTED.md` 仍列出 2026-10-22 的版本，因為 kernel.org 現已列出 7.4-rc2，而目前沒有補丁適用於該版本。

### 2026.10.22 / 5.10.272, 5.15.223, 6.1.190, 6.6.160, 6.12.114, 6.18.58, 7.2.12, 7.3

- 記錄 6.6.160、6.12.114、6.18.58 與 7.2.12，全部沿用原有補丁。6.6.160 修改了 `drivers/tty/vt/vt.c` 與 `fbcon.c`，6.12.114 修改了 `fbcon.c`，改動都不在補丁的 hunk 內。

### 2026.10.20 / 7.3

- 新增 Linux 7.3 的 `v7.x/cjktty-code-7.3.patch`，內容與 7.3-rc1 的原始碼補丁相同。Linux 7.3 只發布拆分形式：先套用 `cjktty-font-unifont-15.1.04.patch`，再套用原始碼補丁。合併形式已在 Linux 7.2 終止，因此不提供 `cjktty-7.3.patch`。

完整的版本記錄見 [CHANGELOG.md](CHANGELOG.md)。

## 使用

[SUPPORTED.md](SUPPORTED.md) 列出每個維護中核心對應的已測試補丁。在核心原始碼根目錄執行以下命令；補丁倉庫路徑為 `../cjktty-patches`：

```sh
patch -p1 --fuzz=0 < ../cjktty-patches/v6.x/cjktty-6.18.patch
```

拆分形式是一份共用字型補丁加上每個核心一份程式碼補丁，得到的原始碼樹逐位元組相同：

```sh
patch -p1 --fuzz=0 < ../cjktty-patches/cjktty-font-unifont-15.1.04.patch
patch -p1 --fuzz=0 < ../cjktty-patches/v6.x/cjktty-code-6.18.patch
```

合併形式已在 Linux 7.2 終止，自 Linux 7.3 起只發布拆分形式。

啟用以下所有核心設定選項：

- `CONFIG_FONTS=y`
- `CONFIG_FONT_CJK_16x16=y`
- `CONFIG_FRAMEBUFFER_CONSOLE=y`

32x32 字型還需要資料補丁：

```sh
patch -p1 --fuzz=0 < ../cjktty-patches/cjktty-add-cjk32x32-font-data.patch
```

套用資料補丁後啟用 `CONFIG_FONT_CJK_32x32=y`。該選項預設關閉。

必須使用 framebuffer console；`vgacon` 無法顯示 CJK。

## 歷史

| 年份 | 位置 |
|---|---|
| 2011–2020 | [gentoo-zh/linux-cjktty](https://github.com/gentoo-zh/linux-cjktty)，由 microcai 維護，每個核心版本各有一個分支 |
| 2020–2024 | [zhmars/cjktty-patches](https://github.com/zhmars/cjktty-patches)，抽取為補丁集合 |
| 2022– | [bigshans/cjktty-patches](https://github.com/bigshans/cjktty-patches)，仍在維護；本倉庫由此分叉而來 |

## 授權

除 32x32 字型資料外，補丁集合採用 [GPL-2.0-only](LICENSE)。32x32 字型資料採用 OFL-1.1；`LICENSE` 包含兩種授權條款全文與字型著作權聲明。

## 致謝

- [youbest](http://blog.chinaunix.net/uid/436750.html) 提供[原始 univt 補丁](https://github.com/zhmars/univt-patches/tree/master/v2.6)
- [microcai](https://github.com/microcai) 與 [gentoo-zh/linux-cjktty](https://github.com/gentoo-zh/linux-cjktty) 提供原始 cjktty 補丁
- [AOSC-Dev/aosc-os-abbs](https://github.com/AOSC-Dev/aosc-os-abbs) 提供部分 univt 修改
- [Unifont](https://savannah.gnu.org/projects/unifont) 提供字型資料
- [Terminus Font](http://terminus-font.sourceforge.net) 提供字型資料

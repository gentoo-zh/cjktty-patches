[English](README.md) | [简体中文](README.zh-CN.md) | [正體中文](README.zh-TW.md)

# cjktty-patches

cjktty-patches 是一組 framebuffer console CJK 渲染補丁，供 `gentoo-zh/overlay` 中的 Gentoo 核心及部分 CachyOS、XanMod 核心使用。

補丁以 [gentoo-zh/linux-cjktty](https://github.com/gentoo-zh/linux-cjktty) 為基礎；本倉庫新增的修正記錄於 [CHANGELOG.md](CHANGELOG.md)。

- Linux 5.10 將核心設定選項 `CONFIG_FONT_16x16_CJK` 重新命名為 `CONFIG_FONT_CJK_16x16`。
- 32x32 字型資料補丁為高解析度螢幕提供較大的字型。
- 內建 CJK 點陣資料要求基礎字型尺寸為 8x16 或 16x32；其他基礎字型尺寸可能導致字元顯示錯誤。
- 目前的 CJK 點陣字型資料衍生自 [GNU Unifont](https://savannah.gnu.org/projects/unifont) 15.1.04。32x32 資料的半形字元範圍取自 [Terminus Font](http://terminus-font.sourceforge.net)，並經由主線核心的 `font_ter16x32.c` 引入。

## 更新

**字型資料與原始碼分別存放在不同補丁中：八個核心共用一份 12 MB 字型補丁，每個核心各有一份 33–44 KB 原始碼補丁。**

### 2026.10.20 / 7.3

- 新增 Linux 7.3 的 `v7.x/cjktty-code-7.3.patch`，內容與 7.3-rc1 的原始碼補丁相同。Linux 7.3 只發布拆分形式：先套用 `cjktty-font-unifont-15.1.04.patch`，再套用原始碼補丁。合併形式已在 Linux 7.2 終止，因此不提供 `cjktty-7.3.patch`。

### 2026.10.17 / 5.10.272, 5.15.223, 6.1.190, 6.6.159, 6.12.113, 6.18.57, 7.2.11, 7.3-rc7

- 記錄 5.10.272、5.15.223、6.1.190、6.6.159、6.12.113、6.18.57 與 7.2.11，全部沿用原有補丁。6.12.113 修改了 `drivers/tty/vt/vt.c`，6.18.57 修改了 `fbcon.c`，改動都不在補丁的 hunk 內。

### 2026.10.12 / 6.18.56, 7.2.10, 7.3-rc7

- 記錄 6.18.56、7.2.10 與 7.3-rc7，全部沿用原有補丁。這三個版本修改了 `drivers/tty/vt/vt.c` 與 `selection.c`，但改動都不在補丁的 hunk 內。

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

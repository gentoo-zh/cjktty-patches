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

### 2026.8.29 / 5.10.268, 5.15.219, 6.1.186, 6.6.155, 6.12.107, 6.18.48, 7.1.12, 7.2.2

- 記錄 2026-08-28 這批點版本，全部沿用原有補丁。上游沒有改動 cjktty 觸及的任何檔案，所以沒有補丁需要更新。

### 2026.8.28 / 5.10.267, 5.15.218, 6.1.185, 6.6.154, 6.12.106, 6.18.47, 7.1.11, 7.2.1

- 記錄 2026-08-27 這批點版本，全部沿用原有補丁。上游只在 7.1.11 動到 `fbcon.c`，而且只移除兩行 `EXPORT_SYMBOL`，其餘 cjktty 觸及的檔案一個都沒改，所以沒有補丁需要更新。

### 2026.8.24 / 6.1.184, 5.15.217

- 增加上述兩個點版本的補丁。同批其餘五個版本沿用原有補丁，因為上游沒有改動 cjktty 觸及的任何檔案。
- 上游在 2026-08-23 把 `struct fbcon_ops` 改名為 `struct fbcon_par` 回溯至 6.1 與 5.15，fbcon 前端因此拒絕這兩份補丁。6.1 的補丁改用 6.12.104 的 fbcon 區段；5.15 的樹結構相差過大，改為對被拒絕的 hunk 套用同一項改名。

### 2026.8.20 / 5.10.265, 5.15.216, 6.1.183, 6.6.152, 6.12.104, 6.18.45, 7.1.9

- 增加上述點版本的補丁。
- 上游在 `bit_cursor()` 中把游標字形索引限制在 `vc_font.charcount` 以內，七條分支因此拒絕該 hunk。`font_bits()` 新增邊界檢查，與 6.1、5.15、5.10 補丁中已有的一致。

### 2026.8.17 / 7.2

- 增加 Linux 7.2 的補丁，內容與 7.2-rc7 的補丁相同。
- 合併形式預計在 Linux 7.3 終止。

### 2026.8.12 / 5.10.264, 5.15.215, 6.1.182, 6.6.151, 6.12.103, 6.18.44, 7.1.8, 7.2-rc7

- `screen_glyph()` 在主儲存格含標記時改為回傳私有平面的碼位。選取檢查 `(screen_glyph(...) & 0xff) == 0xfe` 因此比較該碼位的低位元組，低位元組並非 `0xfe` 的 CJK 字元會複製兩次。新增的 `is_cjk_continuation()` 直接讀取主平面的原始字，並將 `glyph & (vc_hi_font_mask | 0xff)` 與 `0xfe` 比較。
- 字形 `0x1fe` 在 `vc_hi_font_mask` 恢復第 8 位之前接受判斷，所以曾被誤認為續接儲存格；`is_cjk_continuation()` 改為比較包含高字型位元的完整字形值。
- 設定標記後的 `continue` 跳過了上游為第二個儲存格保留的值：截至 6.12 為空格，從 6.18 起為 `U+200B`。`/dev/vcsu` 因此曾在 CJK 字形的兩個儲存格中都回傳該碼位；Unicode 畫面現保留上游值，碼位只寫入私有平面。
- Linux 5.10 至 6.12 在 unimap 回傳範圍內字形時會繞過位於「未找到字形」分支內的標記指派，所以一個字形的一半可能來自已載入字型，另一半來自內建 CJK 字型；標記指派現不再受該分支限制。
- `utf8_pos()` 讀取參數的第二個字，而 `con_putc()` 從 6.6 起只提供一個 `u16`，更早版本提供的第二個字為零，導致 CJK 儲存格上的軟體游標從錯誤的字型表條目繪製；`add_softcursor()` 與 `hide_softcursor()` 現透過 `con_putcs()` 傳入兩個儲存格。
- 輔助旋轉緩衝區只為已載入字型建立，導致 `fd_size_utf` 為零。所有查找因此都退回主旋轉緩衝區的 `0xff` 或 `0xfe` 條目，使用內建字型時，旋轉後的主控台會繪製標記條目而非 CJK 的對應半邊；`font_bits()` 現按照實際索引的緩衝區限制偏移量。
- 輔助函式的 `-ENOENT` 或 `-ENOMEM` 被捨棄，且快取鍵已更新而無法重試。輔助旋轉失敗時因此曾回報成功；狀態現會回傳並向上傳遞，使 fbcon 退回未旋轉繪製。
- 私有平面在 `vc_uniscr_scroll()` 內移動，而 `SCROLL_PAN_REDRAW` 隨後仍把捲動前的列傳給主控台驅動程式，導致主平面的一列與錯誤的私有平面列配對；私有平面現改為在該回呼後移動。
- 寫入只更新了目標儲存格。透過 `/dev/vcs` 或 `/dev/vcsa` 寫入字元後，舊字形的一半因此會留在新字元旁；`vcs_scr_writew()` 現使觸及的私有儲存格及其標記配對儲存格失效並重新繪製兩者，寫入僅含屬性時則不改動私有平面。
- Linux 6.1 獨有的 `is_double_width()` 表格與產生陣列的 Unifont 15.1.04 不一致。該表格誤將 21 個窄字形標為寬字形並漏掉 16 個寬字形，導致 U+2648 佔用一個空白的第二儲存格，而 U+2605 遺失右半邊；該表格現由產生陣列所用的同一字型重建。
- 主控台緩衝區按 `KMALLOC_MAX_SIZE` 驗證，卻按該大小的兩倍配置，所以啟用 `CONFIG_FONT_CJK` 後，檢查接受的主控台尺寸無法配置；上限現與實際配置大小一致。
- `c_utf` 為 `u16`，但描述子的 `charcount` 為 `65536 * 2`，所以 `c_utf >= font->charcount` 從未拒絕任何字形。任何基於該描述子的邊界檢查都有相同問題，因此直接刪除了這個條件。
- 每份補丁中有 17 至 21 個 `IS_ENABLED(CONFIG_FONT_CJK)` 條件位於 `#ifdef CONFIG_FONT_CJK` 內部，因而不可能為假。旋轉緩衝區的配置旗標也在 5.x 與 6.x 之間無故不同；現已刪除這些冗餘條件，並統一配置旗標。
- 為 kernel.org 在 2026-08-11 列出的八個核心新增補丁。
- 使用 Unifont 15.1.04 重新建置 5.10、5.15 與 6.1 的字型，使八個核心繪製相同的字形。
- 為每個維護中的核心提供拆分形式：一份共用字型補丁和一份 33–44 KB 的原始碼補丁，對應原有的 12 MB 合併檔案。
- 在 `font_cjk_16x16.c` 與 `font_cjk_32x32.c` 中註明字型來源。

- 在 7.1.x 上使用 `kvmalloc_array` 預先配置旋轉後的 32x32 緩衝區；否則系統只繪製兩個字形，卻仍回報成功。
- 兩個 CJK 字型選項均關閉時，Makefile 不再產生 CJK 字型物件。
- 將 `CONFIG_FONT_CJK_32x32` 設為預設關閉。以往補丁不帶 32x32 字模，所以 `font_cjk_32x32.h` 為空，但這個選項自 2021 年加入以來一直預設開啟，建置會把 8 MiB 的全零資料編入核心並回報成功。
- 按照其他補丁的順序排列 5.10 的 `font_cjk_32x32` 描述子，使 32x32 資料補丁能夠套用到 5.10。
- 捲動時讓 `clear` 隨 `dst` 與 `src` 一同前移，使第二次 `memset` 清除 Unicode 平面，而不是覆寫清除字元。
- 根據 CJK 字形的 `0xfe` 標記跳過其後的儲存格，不再根據高於 U+0080 的任意碼位判斷；舊判斷會遺失窄字元旁的字元。
- 透過 `con_putcs` 重新繪製反白的 CJK 儲存格，因為從 6.6 起，`fbcon_putc` 已將參數縮窄為一個 `u16`。
- 在旋轉游標路徑中設定 `FB_CUR_SETIMAGE`，使硬體游標後端能夠取得新的點陣圖。
- 使用四行說明文字解釋兩個字型選項，並註明各自的成本。
- 讓 Unicode 側平面隨主平面一同搬移。在含 CJK 的行中插入儲存格會遺失第一個字形，並在行尾留下多餘字元；`vc_uniscr_insert()`、`vc_uniscr_delete()`、`vc_uniscr_clear_line()`、`vc_uniscr_clear_lines()` 與 `vc_uniscr_scroll()` 共同涵蓋 `CSI @`、`CSI P`、插入模式、清除操作與替代畫面。
- Unicode 側平面改由 `vc_screenbuf` 而非 `vc_pos` 定址，使平面位址指向配置的記憶體，而非主控台驅動程式持有的記憶體。

### 2026.8.8 / 6.12.102, 6.18, 7.1.7

- 新增適用於 linux 6.12.102 與 6.18 的補丁。
- 更新至 linux 7.1.7。
- 使用 `kvfree` 釋放 CJK 字型緩衝區，並釋放先前從未釋放的 `fontbuffer_utf`。
- 修正 6.12.63、6.16 與 6.17.8 的建置。

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

合併形式預計在 Linux 7.3 終止，此後只發布拆分形式。

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

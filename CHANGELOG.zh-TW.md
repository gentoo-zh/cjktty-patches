[简体中文](CHANGELOG.zh-CN.md) | [English](CHANGELOG.md) | [正體中文](CHANGELOG.zh-TW.md) | [日本語](CHANGELOG.ja.md) | [한국어](CHANGELOG.ko.md)

# 變更記錄

## 2026.8.12 / 5.10.264, 5.15.215, 6.1.182, 6.6.151, 6.12.103, 6.18.44, 7.1.8, 7.2-rc7

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
- 將 `CONFIG_FONT_CJK_32x32` 設為預設關閉。基礎補丁中的 `font_cjk_32x32.h` 為空，而這個選項自 2021 年加入以來一直預設開啟，所以建置會把 8 MiB 的全零資料編入核心並回報成功。
- 按照其他補丁的順序排列 5.10 的 `font_cjk_32x32` 描述子，使 32x32 資料補丁能夠套用到 5.10。
- 捲動時讓 `clear` 隨 `dst` 與 `src` 一同前移，使第二次 `memset` 清除 Unicode 平面，而不是覆寫清除字元。
- 根據 CJK 字形的 `0xfe` 標記跳過其後的儲存格，不再根據高於 U+0080 的任意碼位判斷；舊判斷會遺失窄字元旁的字元。
- 透過 `con_putcs` 重新繪製反白的 CJK 儲存格，因為從 6.6 起，`fbcon_putc` 已將參數縮窄為一個 `u16`。
- 在旋轉游標路徑中設定 `FB_CUR_SETIMAGE`，使硬體游標後端能夠取得新的點陣圖。
- 使用四行說明文字解釋兩個字型選項，並註明各自的成本。
- 讓 Unicode 側平面隨主平面一同搬移。在含 CJK 的行中插入儲存格會遺失第一個字形，並在行尾留下多餘字元；`vc_uniscr_insert()`、`vc_uniscr_delete()`、`vc_uniscr_clear_line()`、`vc_uniscr_clear_lines()` 與 `vc_uniscr_scroll()` 共同涵蓋 `CSI @`、`CSI P`、插入模式、清除操作與替代畫面。
- Unicode 側平面改由 `vc_screenbuf` 而非 `vc_pos` 定址，使平面位址指向配置的記憶體，而非主控台驅動程式持有的記憶體。

## 2026.8.8 / 6.12.102, 6.18, 7.1.7

- 新增適用於 linux 6.12.102 與 6.18 的補丁。
- 更新至 linux 7.1.7。
- 使用 `kvfree` 釋放 CJK 字型緩衝區，並釋放先前從未釋放的 `fontbuffer_utf`。
- 修正 6.12.63、6.16 與 6.17.8 的建置。

## 2026.7.27 / 7.1.2

- 修正 `CONFIG_FRAMEBUFFER_CONSOLE_ROTATION` 遺失的問題。

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
- 將字型資料更新至 Unifont 15.1.04。
- 將雙寬字元表更新至 Unicode 15.1.0。

## 2023.06.26 / 6.4

- 重新同步至 linux-6.4.y。
- 將字型資料更新至 Unifont 15.0.06。

## 2023.04.24 / 6.3

- 重新同步至 linux-6.3.y。
- 將捲動變數 `t`、`b`、`s` 與 `d` 重新命名為 `top`、`bottom`、`src` 與 `dst`，並在 `con_scroll()` 中快取列數（上游）。
  - [torvalds/linux@424c82a](https://github.com/torvalds/linux/commit/424c82af26b1b8ca6c0be06987a4e6d18c9a92dd)
  - [torvalds/linux@bf8baa0](https://github.com/torvalds/linux/commit/bf8baa00668dbc4fcfca5ac49ae8a3059c795e4e)

## 2022.10.03 / 6.0

- 重新同步至 linux-6.0.y。
- 將字型資料更新至 Unifont 15.0.01。
- 將雙寬字元表更新至 Unicode 15.0.0。
- 進行小幅清理。

## 2022.08.01 / 5.19

- 重新同步至 linux-5.19.y。
- 將字型資料更新至 Unifont 14.0.04。
- 將雙寬字元表更新至 Unicode 14.0.0。
- 修正 Unifont 雙寬字形遭截斷的問題（例如 `①  ②  ③ `）。
- 避免不必要的字元寬度檢查。
- 移除來自 [gentoo-zh/linux-cjktty@6caf83a](https://github.com/gentoo-zh/linux-cjktty/commit/6caf83a638886220d1e1880c92e8b18243c3965a) 的暫時解決方案。

## 2022.05.23 / 5.18

- 重新同步至 linux-5.18.y。
- 修正 GCC 12 的建置警告（`-Wbidi-chars=unpaired`）。

## 2022.03.21 / 5.17

- 重新同步至 linux-5.17.y。
- 將字型資料更新至 Unifont 14.0.02。
- 還原捲動加速程式碼（上游）。
  - [torvalds/linux@1148836](https://github.com/torvalds/linux/commit/1148836fd3226c20de841084aba24184d4fbbe77)

## 2022.01.10 / 5.16

- 重新同步至 linux-5.16.y。
- 移除捲動加速程式碼（上游）。
  - [torvalds/linux@b3ec8cd](https://github.com/torvalds/linux/commit/b3ec8cdf457e5e63d396fe1346cc788cf7c1b578)

## 2021.09.17 / 5.14.5

- 將字型資料更新至 Unifont 14.0.01。
- 使用 Unifont 取代原有 16x16 字型，以改善 Unicode 支援。

## 2021.02.22 / 5.11

- 重新同步至 linux-5.11.y。
- 將 CJK 32x32 字型資料更新至 Unifont 13.0.06。
- 減少 checkpatch.pl 回報的問題。
- 上游已實作 charcount，因此移除相關變更。
  - [torvalds/linux@4ee5730](https://github.com/torvalds/linux/commit/4ee573086bd88ff3060dda07873bf755d332e9ba)
  - [torvalds/linux@a1ac250](https://github.com/torvalds/linux/commit/a1ac250a82a5e97db71f14101ff7468291a6aaef)

## 2020.12.14 / 5.10

- 重新同步至 linux-5.10.y。
- 更新部分中文標點符號的字形。
- 支援顯示旋轉。
- 支援 `setfont`。cjktty 預期使用 8x16 或 16x32 儲存格，其他尺寸可能無法正確顯示。
- 修正部分單寬字元的顯示。
- 修正雙寬字元的換行（<https://github.com/zhmars/cjktty-patches/issues/1>）。
- 套用來自 [gentoo-zh/linux-cjktty@6caf83a](https://github.com/gentoo-zh/linux-cjktty/commit/6caf83a638886220d1e1880c92e8b18243c3965a) 的暫時解決方案。
- 支援高解析度螢幕使用 32x32 字型尺寸。此功能為實驗性功能，必須確認已套用字型資料補丁。

## 2020.09.18 / 5.8.10

- 重新同步至 linux-5.8.10。
- 移除軟體回捲緩衝區程式碼（上游）。
  - [torvalds/linux@5014547](https://github.com/torvalds/linux/commit/50145474f6ef4a9c19205b173da6264a644c7489)

[简体中文](README.md) | [English](README.en.md) | [正體中文](README.zh-TW.md) | [日本語](README.ja.md) | [한국어](README.ko.md)

# cjktty-patches

cjktty-patches は、`gentoo-zh/overlay` が Gentoo カーネルと一部の CachyOS および XanMod カーネルで使用する framebuffer console 向け CJK 描画パッチ集です。

パッチは [gentoo-zh/linux-cjktty](https://github.com/gentoo-zh/linux-cjktty) を基にしています。本リポジトリで追加した修正は [CHANGELOG.ja.md](CHANGELOG.ja.md) に記録しています。

- Linux 5.10 でカーネル設定オプション `CONFIG_FONT_16x16_CJK` は `CONFIG_FONT_CJK_16x16` に改名されました。
- 32x32 フォントデータパッチは、高解像度の画面向けに大きなフォントを提供します。
- 組み込み CJK ビットマップデータは、8x16 または 16x32 のベースフォント形状を前提とします。他のベースフォントサイズでは、文字が正しく表示されない可能性があります。
- 現在の CJK ビットマップデータは [GNU Unifont](https://savannah.gnu.org/projects/unifont) 15.1.04 から派生しています。32x32 データの半角文字範囲は、メインラインカーネルの `font_ter16x32.c` を介して [Terminus Font](http://terminus-font.sourceforge.net) から取得されています。

## 更新

**フォントデータとコードは別々のパッチです。8 つのカーネルが 1 つの 12 MB フォントパッチを共有し、各カーネルに 33–44 KB のコードパッチがあります。**

### 2026.8.12 / 5.10.264, 5.15.215, 6.1.182, 6.6.151, 6.12.103, 6.18.44, 7.1.8, 7.2-rc7

- 主セルにマーカーがある場合、`screen_glyph()` はプライベートプレーンのコードポイントを返していました。そのため、選択処理の判定 `(screen_glyph(...) & 0xff) == 0xfe` はコードポイントの下位バイトを比較し、下位バイトが偶然 `0xfe` だった場合を除いて CJK 文字を 2 回コピーしていました。新しい `is_cjk_continuation()` は主プレーンの生のワードを読み取り、`glyph & (vc_hi_font_mask | 0xff)` を `0xfe` と比較します。
- グリフ `0x1fe` は `vc_hi_font_mask` がビット 8 を復元する前に判定されていたため、継続セルと誤認されていました。`is_cjk_continuation()` は高位フォントビットを含む完全なグリフ値を比較するようになりました。
- マーカー代入後の `continue` が、アップストリームで第 2 セルに保持される値（6.12 までは空白、6.18 以降は `U+200B`）を飛ばしていました。そのため、`/dev/vcsu` は CJK グリフの両方のセルで同じコードポイントを返していました。Unicode 画面はアップストリームの値を保持し、コードポイントはプライベートプレーンだけに格納するようになりました。
- Linux 5.10 から 6.12 では、範囲内の unimap の結果がグリフ未検出分岐内のマーカー代入を迂回したため、グリフの片側が読み込み済みフォント、もう片側が組み込み CJK フォントから描画されることがありました。マーカー代入はこの分岐に依存しなくなりました。
- `utf8_pos()` は引数の第 2 ワードを読み取りますが、`con_putc()` は 6.6 以降 1 個の `u16` だけを渡し、それ以前は第 2 ワードとしてゼロを渡していました。そのため、CJK セル上のソフトウェアカーソルは誤ったフォントテーブルのエントリから描画されていました。`add_softcursor()` と `hide_softcursor()` は `con_putcs()` を介して両方のセルを渡すようになりました。
- 補助回転バッファは読み込み済みフォントに対してのみ作成されるため、組み込みフォントでは `fd_size_utf` がゼロでした。すべての検索が主回転バッファの `0xff` または `0xfe` エントリにフォールバックし、回転したコンソールは対応する CJK の半分ではなくマーカーエントリを描画していました。`font_bits()` は実際に参照するバッファを基準にオフセットを制限するようになりました。
- 補助回転ヘルパーの `-ENOENT` または `-ENOMEM` が破棄され、キャッシュキーも更新済みで再試行できなかったため、補助回転に失敗しても成功と報告されていました。ステータスを返して伝播するようにし、fbcon は回転しない描画にフォールバックします。
- プライベートプレーンを `vc_uniscr_scroll()` 内で移動した後、`SCROLL_PAN_REDRAW` がスクロール前の行をコンソールドライバーへ渡していたため、主プレーンの行が誤ったプライベートプレーンの行と組み合わされていました。プライベートプレーンの移動はこのコールバックの後に行うようになりました。
- 書き込み処理が対象セルだけを更新していたため、`/dev/vcs` または `/dev/vcsa` から文字を書き込むと、古いグリフの半分が新しい文字の隣に残っていました。`vcs_scr_writew()` は対象のプライベートセルと対応するマーカーセルを無効化して両方を再描画し、属性だけの書き込みではプライベートプレーンを変更しないようになりました。
- Linux 6.1 固有の `is_double_width()` テーブルは、配列の生成に使用した Unifont 15.1.04 と一致していませんでした。狭いグリフ 21 個を幅広と判定し、幅広グリフ 16 個を見落としていたため、U+2648 は空白の第 2 セルを消費し、U+2605 は右半分を失っていました。このテーブルは配列と同じフォントから再生成するようになりました。
- コンソールバッファを `KMALLOC_MAX_SIZE` に対して検証した後、その 2 倍のサイズで確保していたため、`CONFIG_FONT_CJK` が有効な場合は検証を通過した画面サイズを確保できませんでした。上限は実際の確保サイズと一致するようになりました。
- `c_utf` は `u16` ですが、ディスクリプタの `charcount` は `65536 * 2` であるため、`c_utf >= font->charcount` はどのグリフも拒否できませんでした。ディスクリプタに基づく境界には同じ問題があるため、この条件は置き換えずに削除しました。
- 各パッチでは、17～21 個の `IS_ENABLED(CONFIG_FONT_CJK)` 条件が `#ifdef CONFIG_FONT_CJK` 内にあり、偽になることはありませんでした。回転バッファの確保フラグも、カーネル側の要件がないにもかかわらず 5.x と 6.x で異なっていました。冗長な条件を削除し、確保フラグを統一しました。
- 2026-08-11 に kernel.org が掲載していた 8 つのカーネルにパッチを追加しました。
- 5.10、5.15、6.1 のフォントを Unifont 15.1.04 から再構築し、8 つのカーネルが同じグリフを描画するようにしました。
- 保守対象の各カーネル向けに、共有フォントパッチと 33–44 KB のコードパッチからなる分割形式を提供しました。従来の結合ファイルは 12 MB です。
- `font_cjk_16x16.c` と `font_cjk_32x32.c` にフォントの出典を記載しました。

- 7.1.x では、回転後の 32x32 バッファを `kvmalloc_array` で事前に確保しました。未修正時は 2 つのグリフしか描画されないにもかかわらず、成功と報告されていました。
- 両方の CJK フォントオプションが無効な場合、Makefile が CJK フォントオブジェクトを生成しないようにしました。
- `CONFIG_FONT_CJK_32x32` をデフォルトで無効にしました。ベースパッチの `font_cjk_32x32.h` は空ですが、このオプションは 2021 年の追加以来ずっと既定で有効だったため、ビルドは 8 MiB のゼロをカーネルに組み込んだうえで成功を報告していました。
- 5.10 の `font_cjk_32x32` ディスクリプタを他のパッチと同じ順序に並べ、32x32 データパッチを 5.10 に適用できるようにしました。
- スクロール時に `clear` を `dst` および `src` とともに進め、2 回目の `memset` が消去文字を上書きせず Unicode プレーンを消去するようにしました。
- U+0080 より大きい任意のコードポイントではなく、CJK グリフの `0xfe` マーカーに基づいて次のセルを飛ばすようにしました。従来の判定では、幅の狭い文字の隣にある文字が失われていました。
- `con_putcs` を介して反転表示された CJK セルを再描画するようにしました。6.6 以降、`fbcon_putc` の引数は 1 つの `u16` に縮小されています。
- 回転カーソルの処理経路で `FB_CUR_SETIMAGE` を設定し、ハードウェアカーソルのバックエンドが新しいビットマップを取得できるようにしました。
- 両方のフォントオプションを 4 行のヘルプで説明し、それぞれのコストを明記しました。
- Unicode プレーンを主プレーンとともに移動するようにしました。CJK を含む行にセルを挿入すると、先頭のグリフが失われ、行末に余分な文字が残っていました。`vc_uniscr_insert()`、`vc_uniscr_delete()`、`vc_uniscr_clear_line()`、`vc_uniscr_clear_lines()`、`vc_uniscr_scroll()` が `CSI @`、`CSI P`、挿入モード、消去処理、代替画面を扱います。
- Unicode プレーンのアドレスを `vc_pos` ではなく `vc_screenbuf` を基準に求め、コンソールドライバーが保持するメモリではなく、割り当てられたメモリを参照するようにしました。

### 2026.8.8 / 6.12.102, 6.18, 7.1.7

- linux 6.12.102 および 6.18 向けのパッチを追加しました。
- linux 7.1.7 に更新しました。
- CJK フォントバッファを `kvfree` で解放し、それまで一度も解放されていなかった `fontbuffer_utf` も解放するようにしました。
- 6.12.63、6.16、6.17.8 のビルドを修正しました。

完全なリリース履歴は [CHANGELOG.ja.md](CHANGELOG.ja.md) にあります。

## 使用方法

[SUPPORTED.md](SUPPORTED.md) は、保守対象の各カーネルでテスト済みのパッチを示します。パッチリポジトリが `../cjktty-patches` にある場合、カーネルソースのルートディレクトリで次のコマンドを実行します。

```sh
patch -p1 --fuzz=0 < ../cjktty-patches/v6.x/cjktty-6.18.patch
```

以下のカーネル設定オプションをすべて有効にします。

- `CONFIG_FONTS=y`
- `CONFIG_FONT_CJK_16x16=y`
- `CONFIG_FRAMEBUFFER_CONSOLE=y`

32x32 フォントには、データパッチも必要です。

```sh
patch -p1 --fuzz=0 < ../cjktty-patches/cjktty-add-cjk32x32-font-data.patch
```

データパッチの適用後に `CONFIG_FONT_CJK_32x32=y` を有効にします。`CONFIG_FONT_CJK_32x32` は既定で無効です。

フレームバッファコンソールが必要です。`vgacon` では CJK を表示できません。

## 履歴

| 年 | 所在 |
|---|---|
| 2011–2020 | [gentoo-zh/linux-cjktty](https://github.com/gentoo-zh/linux-cjktty)。microcai が保守し、カーネルごとに 1 つのブランチを使用していました |
| 2020–2024 | [zhmars/cjktty-patches](https://github.com/zhmars/cjktty-patches)。パッチ集として抽出されました |
| 2022– | [bigshans/cjktty-patches](https://github.com/bigshans/cjktty-patches)。現在も保守されている現行フォークの派生元 |

## ライセンス

32x32 フォントデータを除くパッチ集は [GPL-2.0-only](LICENSE) です。32x32 フォントデータは OFL-1.1 です。`LICENSE` には両ライセンスの全文とフォントの著作権表示を収録しています。

## クレジット

- [youbest](http://blog.chinaunix.net/uid/436750.html) は[元の univt パッチ](https://github.com/zhmars/univt-patches/tree/master/v2.6)を提供しました。
- [microcai](https://github.com/microcai) と [gentoo-zh/linux-cjktty](https://github.com/gentoo-zh/linux-cjktty) は元の cjktty パッチを提供しました。
- [AOSC-Dev/aosc-os-abbs](https://github.com/AOSC-Dev/aosc-os-abbs) は univt の変更の一部を提供しました。
- [Unifont](https://savannah.gnu.org/projects/unifont) はフォントデータを提供しました。
- [Terminus Font](http://terminus-font.sourceforge.net) はフォントデータを提供しました。

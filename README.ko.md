[简体中文](README.md) | [English](README.en.md) | [正體中文](README.zh-TW.md) | [日本語](README.ja.md) | [한국어](README.ko.md)

# cjktty-patches

cjktty-patches는 `gentoo-zh/overlay`에서 Gentoo 커널과 일부 CachyOS 및 XanMod 커널에 사용하는 framebuffer console CJK 렌더링 패치 모음입니다.

패치는 [gentoo-zh/linux-cjktty](https://github.com/gentoo-zh/linux-cjktty)를 기반으로 합니다. 이 저장소에서 추가한 수정 사항은 [CHANGELOG.ko.md](CHANGELOG.ko.md)에 기록됩니다.

- Linux 5.10에서 커널 구성 옵션 `CONFIG_FONT_16x16_CJK`의 이름이 `CONFIG_FONT_CJK_16x16`으로 변경되었습니다.
- 32x32 글꼴 데이터 패치는 고해상도 화면에 더 큰 글꼴을 제공합니다.
- 내장 CJK 비트맵 데이터는 8x16 또는 16x32 기본 글꼴 형태를 전제로 합니다. 다른 기본 글꼴 크기에서는 문자가 올바르게 표시되지 않을 수 있습니다.
- 현재 CJK 비트맵 데이터는 [GNU Unifont](https://savannah.gnu.org/projects/unifont) 15.1.04에서 파생되었습니다. 32x32 데이터의 반각 문자 범위는 메인라인 커널의 `font_ter16x32.c`를 통해 [Terminus Font](http://terminus-font.sourceforge.net)에서 가져왔습니다.

## 업데이트

**글꼴 데이터와 코드는 별도 패치입니다. 커널 8개가 12 MB 글꼴 패치 하나를 공유하고 각 커널은 33–44 KB 코드 패치 하나를 갖습니다.**

### 2026.8.12 / 5.10.264, 5.15.215, 6.1.182, 6.6.151, 6.12.103, 6.18.44, 7.1.8, 7.2-rc7

- 기본 셀에 마커가 있으면 `screen_glyph()`가 전용 평면의 코드 포인트를 반환했습니다. 따라서 선택 검사 `(screen_glyph(...) & 0xff) == 0xfe`가 코드 포인트의 하위 바이트를 비교하여 하위 바이트가 우연히 `0xfe`인 경우를 제외한 CJK 문자를 두 번 복사했습니다. 새 `is_cjk_continuation()`은 기본 평면의 원시 워드를 읽고 `glyph & (vc_hi_font_mask | 0xff)`를 `0xfe`와 비교합니다.
- 글리프 `0x1fe`는 `vc_hi_font_mask`가 8번 비트를 복원하기 전에 판정되었으므로 연속 셀로 잘못 인식되었습니다. `is_cjk_continuation()`은 이제 상위 글꼴 비트를 포함한 전체 글리프 값을 비교합니다.
- 마커를 할당한 뒤의 `continue`가 업스트림에서 두 번째 셀에 유지하는 값, 즉 6.12까지는 공백이고 6.18부터는 `U+200B`인 값을 건너뛰었습니다. 이 때문에 `/dev/vcsu`가 CJK 글리프의 두 셀 모두에서 같은 코드 포인트를 반환했습니다. 이제 Unicode 화면은 업스트림 값을 유지하고 코드 포인트는 전용 평면에만 기록합니다.
- Linux 5.10부터 6.12까지는 범위 안의 unimap 결과가 글리프를 찾지 못한 분기 안의 마커 할당을 우회했으므로, 글리프의 한쪽은 로드한 글꼴에서, 다른 쪽은 내장 CJK 글꼴에서 그려질 수 있었습니다. 이제 마커 할당은 해당 분기에 의존하지 않습니다.
- `utf8_pos()`는 인수의 두 번째 워드를 읽지만, `con_putc()`는 6.6부터 `u16` 하나만 전달하고 그 이전에는 두 번째 워드로 0을 전달했습니다. 이 때문에 CJK 셀 위의 소프트웨어 커서가 잘못된 글꼴 테이블 항목에서 그려졌습니다. `add_softcursor()`와 `hide_softcursor()`는 이제 `con_putcs()`를 통해 두 셀을 모두 전달합니다.
- 보조 회전 버퍼는 로드한 글꼴에만 생성되므로 내장 글꼴에서는 `fd_size_utf`가 0이었습니다. 모든 조회가 기본 회전 버퍼의 `0xff` 또는 `0xfe` 항목으로 대체되어, 회전한 콘솔이 해당 CJK 절반 대신 마커 항목을 그렸습니다. `font_bits()`는 이제 실제로 조회하는 버퍼를 기준으로 오프셋의 범위를 제한합니다.
- 보조 회전 도우미의 `-ENOENT` 또는 `-ENOMEM`이 폐기되고 캐시 키도 이미 갱신되어 재시도할 수 없었으므로, 보조 회전에 실패해도 성공으로 보고되었습니다. 이제 상태를 반환하고 전파하며, fbcon은 회전하지 않은 렌더링으로 대체합니다.
- 전용 평면이 `vc_uniscr_scroll()` 안에서 이동한 뒤 `SCROLL_PAN_REDRAW`가 스크롤 전 행을 콘솔 드라이버에 전달했으므로, 기본 평면 행이 잘못된 전용 평면 행과 짝지어졌습니다. 이제 전용 평면은 해당 콜백 뒤에 이동합니다.
- 쓰기 작업이 대상 셀만 갱신했으므로 `/dev/vcs` 또는 `/dev/vcsa`로 문자를 쓰면 이전 글리프의 절반이 새 문자 옆에 남았습니다. `vcs_scr_writew()`는 이제 대상 전용 셀과 짝인 마커 셀을 무효화하고 둘 다 다시 그리며, 속성만 쓰는 경우에는 전용 평면을 변경하지 않습니다.
- Linux 6.1에만 있는 `is_double_width()` 테이블은 배열 생성에 사용한 Unifont 15.1.04와 일치하지 않았습니다. 좁은 글리프 21개를 넓다고 표시하고 넓은 글리프 16개를 누락했으므로 U+2648은 빈 두 번째 셀을 차지하고 U+2605는 오른쪽 절반을 잃었습니다. 이제 배열과 같은 글꼴에서 테이블을 다시 생성합니다.
- 콘솔 버퍼를 `KMALLOC_MAX_SIZE`에 맞춰 검증한 뒤 그 두 배 크기로 할당했으므로, `CONFIG_FONT_CJK`가 켜져 있으면 검사를 통과한 화면 크기도 할당할 수 없었습니다. 이제 제한이 실제 할당 크기와 일치합니다.
- `c_utf`는 `u16`이고 디스크립터의 `charcount`는 `65536 * 2`이므로, `c_utf >= font->charcount`는 어떤 글리프도 거부하지 못했습니다. 디스크립터에 기반한 경계에는 같은 문제가 있으므로 이 조건은 대체하지 않고 삭제했습니다.
- 각 패치에는 `#ifdef CONFIG_FONT_CJK` 안에 17~21개의 `IS_ENABLED(CONFIG_FONT_CJK)` 조건이 있어 거짓이 될 수 없었습니다. 회전 버퍼의 할당 플래그도 커널에서 요구하지 않았지만 5.x와 6.x에서 달랐습니다. 중복 조건을 삭제하고 할당 플래그를 통일했습니다.
- 2026-08-11에 kernel.org에 등재된 커널 8개에 패치를 추가했습니다.
- 5.10, 5.15, 6.1 글꼴을 Unifont 15.1.04에서 다시 빌드하여 8개 커널이 같은 글리프를 그리도록 했습니다.
- 유지 관리하는 각 커널에 공용 글꼴 패치와 33–44 KB 코드 패치로 구성된 분할 형식을 제공했습니다. 기존 결합 파일은 12 MB입니다.
- `font_cjk_16x16.c`와 `font_cjk_32x32.c`에 글꼴 출처를 명시했습니다.

- 7.1.x에서 회전된 32x32 버퍼를 `kvmalloc_array`로 미리 할당했습니다. 수정 전에는 글리프 두 개만 그리면서도 성공으로 보고했습니다.
- 두 CJK 글꼴 옵션이 모두 꺼진 경우 Makefile이 CJK 글꼴 오브젝트를 생성하지 않도록 했습니다.
- `CONFIG_FONT_CJK_32x32`를 기본적으로 끄도록 했습니다. 기본 패치의 `font_cjk_32x32.h`는 비어 있지만 이 옵션은 2021년 추가된 이후 계속 기본으로 켜져 있었으므로, 빌드는 8 MiB의 0을 커널에 포함한 채 성공을 보고했습니다.
- 5.10의 `font_cjk_32x32` 디스크립터를 다른 패치와 같은 순서로 배치하여 32x32 데이터 패치를 5.10에도 적용할 수 있게 했습니다.
- 스크롤할 때 `clear`를 `dst` 및 `src`와 함께 이동하여 두 번째 `memset`이 지우기 문자를 덮어쓰지 않고 Unicode 평면을 지우도록 했습니다.
- U+0080보다 큰 모든 코드 포인트가 아니라 CJK 글리프의 `0xfe` 마커를 기준으로 다음 셀을 건너뛰도록 했습니다. 기존 판정은 폭이 좁은 문자 옆의 문자를 잃었습니다.
- `con_putcs`를 통해 반전 표시된 CJK 셀을 다시 그리도록 했습니다. 6.6부터 `fbcon_putc`의 인수는 `u16` 하나로 축소되었습니다.
- 회전된 커서 경로에서 `FB_CUR_SETIMAGE`를 설정하여 하드웨어 커서 백엔드가 새 비트맵을 가져오도록 했습니다.
- 두 글꼴 옵션을 네 줄의 도움말로 설명하고 각 옵션의 비용을 명시했습니다.
- Unicode 평면을 주 평면과 함께 이동하도록 했습니다. CJK가 포함된 줄에 셀을 삽입하면 첫 번째 글리프가 사라지고 줄 끝에 불필요한 문자가 남았습니다. `vc_uniscr_insert()`, `vc_uniscr_delete()`, `vc_uniscr_clear_line()`, `vc_uniscr_clear_lines()`, `vc_uniscr_scroll()`이 `CSI @`, `CSI P`, 삽입 모드, 지우기 작업, 대체 화면을 처리합니다.
- Unicode 평면의 주소를 `vc_pos`가 아니라 `vc_screenbuf`를 기준으로 계산하여, 콘솔 드라이버가 보유한 메모리가 아니라 할당된 메모리를 참조하도록 했습니다.

### 2026.8.8 / 6.12.102, 6.18, 7.1.7

- linux 6.12.102와 6.18용 패치를 추가했습니다.
- linux 7.1.7에 맞게 업데이트했습니다.
- CJK 글꼴 버퍼를 `kvfree`로 해제하고, 이전에는 한 번도 해제되지 않았던 `fontbuffer_utf`도 해제하도록 했습니다.
- 6.12.63, 6.16, 6.17.8의 빌드를 수정했습니다.

전체 릴리스 기록은 [CHANGELOG.ko.md](CHANGELOG.ko.md)에 있습니다.

## 사용법

[SUPPORTED.md](SUPPORTED.md)는 유지 관리하는 각 커널에서 테스트한 패치를 명시합니다. 패치 저장소가 `../cjktty-patches`에 있는 경우 커널 소스 루트에서 다음 명령을 실행합니다.

```sh
patch -p1 --fuzz=0 < ../cjktty-patches/v6.x/cjktty-6.18.patch
```

다음 커널 구성 옵션을 모두 활성화합니다.

- `CONFIG_FONTS=y`
- `CONFIG_FONT_CJK_16x16=y`
- `CONFIG_FRAMEBUFFER_CONSOLE=y`

32x32 글꼴에는 데이터 패치도 필요합니다.

```sh
patch -p1 --fuzz=0 < ../cjktty-patches/cjktty-add-cjk32x32-font-data.patch
```

데이터 패치를 적용한 뒤 `CONFIG_FONT_CJK_32x32=y`를 활성화합니다. `CONFIG_FONT_CJK_32x32`는 기본적으로 비활성화되어 있습니다.

프레임버퍼 콘솔이 필요합니다. `vgacon` 은 CJK 를 표시할 수 없습니다.

## 역사

| 연도 | 위치 |
|---|---|
| 2011–2020 | [gentoo-zh/linux-cjktty](https://github.com/gentoo-zh/linux-cjktty). microcai가 유지 관리했으며 커널마다 브랜치 하나를 사용했습니다 |
| 2020–2024 | [zhmars/cjktty-patches](https://github.com/zhmars/cjktty-patches). 패치 모음으로 추출되었습니다 |
| 2022– | [bigshans/cjktty-patches](https://github.com/bigshans/cjktty-patches). 계속 유지 관리되는 현재 포크의 원본 저장소 |

## 라이선스

32x32 글꼴 데이터를 제외한 패치 모음은 [GPL-2.0-only](LICENSE)입니다. 32x32 글꼴 데이터는 OFL-1.1입니다. `LICENSE`에는 두 라이선스의 전체 본문과 글꼴 저작권 고지가 포함되어 있습니다.

## 감사의 말

- [youbest](http://blog.chinaunix.net/uid/436750.html)는 [원본 univt 패치](https://github.com/zhmars/univt-patches/tree/master/v2.6)를 제공했습니다.
- [microcai](https://github.com/microcai)와 [gentoo-zh/linux-cjktty](https://github.com/gentoo-zh/linux-cjktty)는 원본 cjktty 패치를 제공했습니다.
- [AOSC-Dev/aosc-os-abbs](https://github.com/AOSC-Dev/aosc-os-abbs)는 univt 수정 사항 일부를 제공했습니다.
- [Unifont](https://savannah.gnu.org/projects/unifont)는 글꼴 데이터를 제공했습니다.
- [Terminus Font](http://terminus-font.sourceforge.net)는 글꼴 데이터를 제공했습니다.

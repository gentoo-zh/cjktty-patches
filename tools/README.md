# tools

Maintenance and test scripts for the patch collection. Required programs are
`gcc`, `cpio`, `patch`, `qemu-system-x86_64` with KVM, and OVMF firmware. Kernel trees and test
artifacts go to `$CJKTTY_LAB`, which defaults to `../lab`.

## check-release-drift.py

The optional feed, tarball, and scratch paths are accepted through
`--releases-file`, `--tarball-dir`, and `--scratch-dir`. The repository fixture
provides a reproducible invocation:

```sh
tools/check-release-drift.py \
  --releases-file tools/testdata/releases-2026-08-11.json \
  --tarball-dir "$CJKTTY_LAB" --scratch-dir "$CJKTTY_LAB"
```

Reads kernel.org's `releases.json` feed and checks the active, non-EOL
`mainline`, `stable` and `longterm` series with a published cjktty-patches
monolithic patch. Archived series are deliberately omitted even though archived
patches remain published. For each watched series, the script selects the newest
versioned `cjktty-<version>.patch` filename; split `cjktty-code-*` patches are
not a second patch lineage and are omitted.

Each patch is checked against the feed's current release with
`patch -p1 --fuzz=0 --dry-run`. A stable or longterm reject exits nonzero. A
mainline release-candidate reject is reported but exits zero because movement is
expected during the RC cycle. Network, feed and extraction errors are reported
separately and exit 2 rather than being mislabeled as patch drift.

`check-release-drift.py` only proves that a patch applies without fuzz. The
script does not build the kernel or render CJK; `test-patch.sh` and
`test-system.sh` cover build and rendering.

## gen-supported.py

```sh
python3 tools/gen-supported.py \
  --releases-file tools/testdata/releases-2026-08-11.json --check
```

Generates `SUPPORTED.md` from the active kernel.org releases, the patch
selection rule and `tools/supported-verification.json`. `SUPPORTED.md` is a
generated file and must never be edited by hand. Without `--check`, the script
writes the generated matrix to `SUPPORTED.md`, or to the path passed through
`--output`.

`--check` compares the complete generated content with the current output file.
A difference prints a unified diff and exits 1. A verification record whose
patch is missing or has changed also exits 1, which is what makes a patch edit
invalidate the measurement recorded against its bytes. A split record whose
digest keys are not exactly its declared font and code paths exits 2. An unreadable or malformed release
feed or verification file exits 2.

## patch_selection.py

```sh
python3 tools/patch_selection.py . 6.12.103
```

Prints the monolithic patch selected for one kernel version. Within the same
major and minor series, the newest patch version not newer than the kernel wins;
therefore Linux 6.12.103 selects `v6.x/cjktty-6.12.102.patch`. A bare series
patch is the baseline for a release candidate when no earlier candidate exists.

An invalid kernel version or a series with no applicable patch exits 1 without
printing a path. Supplying anything other than the repository and kernel version
exits 2. Selection does not apply the patch.

## fetch-kernel.sh

```sh
tools/fetch-kernel.sh 6.18.44 "$CJKTTY_LAB/tarballs"
```

Prints the local tarball path, downloading the file when it is absent. A final
release such as Linux 6.18.44 uses `linux-6.18.44.tar.xz`; a release candidate
such as Linux 7.2-rc7 uses the git snapshot `linux-7.2-rc7.tar.gz`. The optional
second argument overrides `CJKTTY_TARBALLS` and the default lab tarball directory.

A failed download or a corrupt new xz or gzip archive exits 1, and the partial
file is removed. Omitting the kernel version also exits 1. An existing archive
is returned without an integrity check; a corrupt cached file therefore exits 0
and must be removed before retrying the download.

## ci-matrix.py

```sh
python3 tools/ci-matrix.py v6.x/cjktty-6.12.102.patch
python3 tools/ci-matrix.py --all
```

Prints the JSON `apply` and `boot` matrices consumed by
`.github/workflows/ci.yml`. A maintained combined patch produces both jobs for
the maintained kernel it serves; the first command selects Linux 6.12.103.
An archived combined patch produces an apply-only job. Split code, shared font,
CJK32 data and loadable-font changes select their corresponding jobs, while
documentation-only paths select none. `--all` selects all eight maintained
kernel versions in `tools/supported-verification.json`.

An absolute path, a path containing `..`, a missing changed patch, or a patch
that cannot be mapped to a CI job exits 2. Invalid verification data also exits
2. `--all` rejects additional changed paths with exit 2.

## test-patch.sh

Usage: `tools/test-patch.sh [--cjk32] <kernel-version> [patch-file ...]`.

```sh
JOBS=32 tools/test-patch.sh 6.18.44
```

Downloads the kernel if needed, then runs three checks. A patch is only finished
when all three pass:

1. **applies** — `patch -p1 --fuzz=0`, no fuzzy matching allowed.
2. **builds** — a full `bzImage` with the framebuffer console and
   `CONFIG_FONT_CJK_16x16` enabled.
3. **renders** — boots under OVMF and checks the screenshot.

The third check is not an ioctl. cjktty leaves `vc_font` at the base 256-glyph
font and draws CJK from the separate cjktty buffer, so the console keeps reporting
`8x16 charcount=256` whether or not the patch works. `check-console.py` instead
compares two different CJK cells on screen: real glyphs differ and carry ink,
missing glyphs produce the same empty box.

When patch paths are given, `test-patch.sh` applies every patch from left to
right. Explicit paths let a split font-and-code pair go through the same build and boot checks as
a monolithic patch.

`CONFIG_FONT_CJK_32x32` stays off during the test. The base patch ships an empty
`font_cjk_32x32.h`, so enabling `CONFIG_FONT_CJK_32x32` spends 8 MiB on a blank font.

## make-testvm.sh, make-boot-testvm.sh and test-system.sh

`tools/make-testvm.sh` builds `testvm/base.img` once.
`tools/make-boot-testvm.sh` builds the partitioned `boot-testvm/base.img` once.
Usage: `tools/test-system.sh [--bootloader] [--cjk32] <kernel-version>
[patch-file ...]`.

```sh
JOBS=32 tools/test-system.sh 6.18.44
JOBS=32 tools/test-system.sh --bootloader 6.18.44
```

`test-patch.sh` stops at an initramfs, which never reaches the paths changed by cjktty
changes. `test-system.sh` boots a stage3 systemd userland from disk and drives
the rest over the serial port: systemd to `running`, `systemd-vconsole-setup`
reloading the font, `setfont`, `chvt`, the framebuffer handover from efifb to
virtio-gpu, console rotation, an fbcon unbind and rebind, `dmesg` free of oops
and call traces, and `systemctl poweroff`.

Rotation and rebind reach the two code paths most frequently changed by
cjktty-patches. `fbcon_rotate_font_utf()` runs under rotation and nowhere else, and
kernel ports rewrite `fbcon_rotate_font_utf()` more often than
anything else in the patch; `fbcon_release()` frees both font buffers and a normal
shutdown does not reach `fbcon_release()`. Both paths run in one boot through
second boot: `/sys/class/graphics/fbcon/rotate_all` and
`/sys/class/vtconsole/vtcon*/bind`.

The default `test-system.sh` path keeps the kernel out of the image. QEMU receives the kernel through `-kernel`
and the disk is a qcow2 overlay on the base, so swapping kernels costs one build
and no install, and a run cannot damage the base image.

The optional `--bootloader` path uses a separate partitioned base image. The path
builds and installs the kernel modules into an overlay, invokes the image's
`installkernel`, requires dracut to produce a non-empty initramfs and requires
GRUB's generated configuration to name both files. The verification boot then
receives neither `-kernel` nor `-append`; OVMF starts GRUB from the ESP and GRUB
supplies the kernel command line. The serial driver distinguishes GRUB not
starting from GRUB starting but failing to hand off to Linux, and the guest
confirms initramfs unpacking before the normal system test continues.

Three screenshots come out of each run: `login.ppm` is the getty screen,
`rotated.ppm` is the CJK line drawn while the console is turned ninety degrees,
and `console.ppm` is the CJK line after the DRM handover. `check-console.py`
checks the last two.

Every step is an assertion. The bind
loop ends in `[ $n -gt 0 ]` because a loop that matches no console exits 0 and
the release path would go unrun; `test-system.sh` then confirms from `dmesg` that the
console really left the framebuffer driver.

Like `test-patch.sh`, `test-system.sh` applies any explicitly named patches from
left to right.

## split-patch.py

```sh
tools/test-split-patch.sh
```

`tools/split-patch.py <source-patch> <font-output> <code-output>` performs one
split; `tools/test-split-patch.sh` checks the published split patches.

Splits a monolithic patch by complete file stanza. Every hunk for a path matching
`lib/fonts/font_cjk_<width>x<height>.h` goes to the font output; every other hunk
goes to the code output. File metadata stays with the corresponding stanza, so the empty
`font_cjk_32x32.h` is retained in the font output despite having no
`---`/`+++` pair.

The source file list is the ordered union of `diff --git a/` and `--- a/`
headers. Both forms are required: current patches use plain `---` headers for
most files, while an empty new file can have only a `diff --git` header.

Apply `cjktty-font-unifont-15.1.04.patch` before the matching
`cjktty-code-*.patch`.

## test-split-matches-combined.py

```sh
python3 tools/test-split-matches-combined.py
```

Runs `split-patch.py` on the combined counterpart of every
`v[0-9]*.x/cjktty-code-*.patch`, then byte-compares the generated code output
with the published split code patch. The current repository checks eight split forms twice, once for the code half
and once for the font half.

A split code patch with no combined counterpart, code bytes that differ from
splitting that counterpart, or generated font bytes that differ from
`cjktty-font-unifont-15.1.04.patch`, exits 1. Changing the first font data byte
returns eight font failures with eight code passes, exit 1. A deliberately divergent
`cjktty-code-1.0.patch` returned exit 1.

## port.sh

Start a port with `tools/port.sh <new-version> <base-patch>`, resolve every
listed `.rej` file, and finish with `tools/port.sh --finish <new-version>`.

Applies the nearest existing patch to a new kernel, leaves the tree and rejects
for hand fixing, then regenerates the patch. Neighbouring versions usually differ
only in line offsets; a reject means upstream changed a struct field, a function's
visibility, or the order of an allocation.

## regen.sh

Usage: `tools/regen.sh <pristine-tree> <patched-tree> <source-patch> <output>`.

Writes a patch from the difference between two trees. The file list comes from
the source patch's `diff --git` lines, not from `+++`: git emits no `---`/`+++`
pair for an empty new file, and `font_cjk_32x32.h` is empty. Every stanza gets
an independent `diff --git` header so `patch` cannot attach a `new file mode` to the
file that follows.

Prefer editing a patch in place over regeneration. A regenerated 12 MB file
hides a two-line change from review.

## gen-font.py

```sh
tools/gen-font.py --format psf2 --size 16 \
  --base-font "$CJKTTY_LAB/linux-6.18.44/lib/fonts/font_8x16.c" \
  --output "$CJKTTY_LAB/cjk-16.psf" \
  "$CJKTTY_LAB/unifont-15.1.04.hex"
```

Generates the two-cell BMP layout used by cjktty. The first 256 halfwidth
glyphs come from the named Linux base font; `font_ter16x32.c` is derived from
Terminus. Remaining glyphs come from the official GNU Unifont `.hex` release.
`gen-font.py` determines halfwidth versus fullwidth from each hex payload, not
the codepoint, and doubles both axes for 32x32 output. Use
`font/precompiled/unifont-<version>.hex` from the project's
[official release tarball](https://unifoundry.com/pub/unifont/). Both current
arrays match Unifont 15.1.04; later whole-font updates superseded the 13.0.06
source named by the first 32x32 changelog entry.

The generated 16x16 C header selects GPL version 2 and retains the GNU
Unifont 15.1.04 copyright notice. The generated 32x32 C header selects
OFL-1.1 and retains both the Unifont notice and the Terminus Font 4.49.1
copyright and Reserved Font Name notice. The repository's `LICENSE` contains
the copyright notices and the complete GPL version 2 and OFL-1.1 texts. Distribute
generated C headers and PSF2 files with `LICENSE`; PSF2 has no field for license
metadata.

The default output is the C header used by the existing patches. The `psf2`
format wraps the same bytes as 131,072 half-cell glyphs for the loadable-font
prototype.

Pass `--compare` with a generated header or a cjktty patch to verify the data
without writing the generated array:

```sh
tools/gen-font.py --size 16 \
  --base-font "$CJKTTY_LAB/linux-6.18.44/lib/fonts/font_8x16.c" \
  --compare v6.x/cjktty-6.18.patch \
  "$CJKTTY_LAB/unifont-15.1.04.hex"
```

## loadable-font prototype

The command, scope, and current result are in
[`docs/loadable-font.md`](../docs/loadable-font.md#prototype-and-evidence).

`tools/test-loadable-font.sh` tests the existing console-font ioctl as a narrow
prototype. The production design uses a separate CJK object; the prototype does
not implement that ownership model.

## check-console.py

```sh
python3 tools/check-console.py \
  "$CJKTTY_LAB/out-system-6.18.44/console.ppm"
python3 tools/check-console.py --rotated \
  "$CJKTTY_LAB/out-system-6.18.44/rotated.ppm"
```

Both test scripts call `check-console.py`; a direct Python invocation re-checks
a saved screenshot.

The default mode compares two adjacent CJK cells at a known row. `--rotated`
cannot use fixed rows, so `--rotated` measures the bounding box of the lit pixels and
requires a height greater than the width. Ink alone is insufficient: a console
without rotation still shows a horizontal line with the same amount of ink.

## drive-system.py and init.c

`drive-system.py` is the serial driver run by `test-system.sh`; every guest
command has a checked exit status, and a numeric result is read back inside a
unique marker because the stage3 shell wraps the prompt in OSC 133 sequences.
`init.c` is the initramfs init for `test-patch.sh`: `init.c` mounts devtmpfs,
since `CONFIG_DEVTMPFS_MOUNT` applies only to a real root, then prints the CJK
lines the screenshot is taken of.

## test-stress.sh

`tools/test-stress.sh <version> [patch ...]` builds the patch with KASAN,
kmemleak, lockdep and `DEBUG_ATOMIC_SLEEP`, then cycles `setfont`, `chvt`,
console rotation, an fbcon unbind and rebind, a console resize and a burst of
CJK output. `test-system.sh` performs each operation once; a leak on the release
path or a lock taken in the wrong order only appears after repeated operations.

The verdict comes from `tools/stress-verdict.py`, which strips the shell's own
echo of the grep command before counting. Counting the raw serial log reports
the pattern itself as a finding.

Proven to fail: removing one `kvfree(par->fontbuffer_utf)` from
`fbcon_release()` makes kmemleak report `unreferenced object` of 2,097,152
bytes, exactly the 16x16 font buffer, and the script exits 1.

The guest needs 4 GiB because KASAN roughly triples the kernel's memory use.

## Testing the 32x32 font

`--cjk32` on either stage applies `cjktty-add-cjk32x32-font-data.patch` on top
of the base patch, turns `CONFIG_FONT_CJK_32x32` on and `CONFIG_FONT_CJK_16x16`
off, and selects `FONT_TER16x32` as the base font.

```sh
JOBS=32 tools/test-patch.sh --cjk32 6.18.44
JOBS=32 tools/test-system.sh --cjk32 6.18.44
```

Without the data patch, `CONFIG_FONT_CJK_32x32` compiles 8 MiB of zeros.
Therefore the option defaults off, and `--cjk32` applies the data patch.

The console cell follows the base font, so `--cjk32` passes `--cell 16x32` to
`check-console.py`. Sampling 8x16 cells on a 16x32 screen lands between glyphs
and reports a blank cell on a working kernel.

`scripts/config` exits 0 without changing `CONFIG_FONT_CJK_16x16` or
`CONFIG_FONT_CJK_32x32`, so `set_option` deletes
the line and appends the wanted form. `defconfig` omits a symbol whose default
is n, so absence there is normal; the assertion after `olddefconfig` is what
proves the symbol exists.

Measured on 6.18.44: 16x16 draws 144 and 135 lit subpixels, 32x32 draws 576 and
540, four times the area for glyphs twice as wide and twice as tall.

## test-cjk32-applies.py

```sh
CJKTTY_LAB=/path/to/lab python3 tools/test-cjk32-applies.py
python3 tools/test-cjk32-applies.py --lab /path/to/lab
```

Reads the maintained kernel versions from `tools/supported-verification.json`,
copies each version's `linux-<version>` tree from the lab, applies the shared
font patch and the serving split code patch, then dry-runs
`cjktty-add-cjk32x32-font-data.patch` against the result with `--fuzz=0`. The
current repository checks eight kernels.

The lab directory comes from `--lab`, or from `CJKTTY_LAB`, or from `../lab`
beside the repository. A missing tree exits 1 rather than passing, so a run that
had nothing to test against never reads as green.

A data patch that rejects exits 1. Changing `.height = 32` to `.height = 31` in
`v6.x/cjktty-code-6.18.patch` returns `cjk32 patch application: 7 passed, 1
failed`, exit 1, while the descriptor-order check this replaced returned exit 0
for the same input.

## patch_selection.py

```sh
python3 tools/patch_selection.py . 6.12.103
```

Prints the monolithic patch selected for one kernel version. Within the same
major and minor series, the newest patch version not newer than the kernel wins;
therefore Linux 6.12.103 selects `v6.x/cjktty-6.12.102.patch`. A bare series
patch is the baseline for a release candidate when no earlier candidate exists.

An invalid kernel version or a series with no applicable patch exits 1 without
printing a path. Supplying anything other than the repository and kernel version
exits 2. Selection does not apply the patch.

## fetch-kernel.sh

```sh
tools/fetch-kernel.sh 6.18.44 "$CJKTTY_LAB/tarballs"
```

Prints the local tarball path, downloading the file when it is absent. A final
release such as Linux 6.18.44 uses `linux-6.18.44.tar.xz`; a release candidate
such as Linux 7.2-rc7 uses the git snapshot `linux-7.2-rc7.tar.gz`. The optional
second argument overrides `CJKTTY_TARBALLS` and the default lab tarball directory.

A failed download or a corrupt new xz or gzip archive exits 1, and the partial
file is removed. Omitting the kernel version also exits 1. An existing archive
is returned without an integrity check; a corrupt cached file therefore exits 0
and must be removed before retrying the download.

## ci-matrix.py

```sh
python3 tools/ci-matrix.py v6.x/cjktty-6.12.102.patch
python3 tools/ci-matrix.py --all
```

Prints the JSON `apply` and `boot` matrices consumed by
`.github/workflows/ci.yml`. A maintained combined patch produces both jobs for
the maintained kernel it serves; the first command selects Linux 6.12.103.
An archived combined patch produces an apply-only job. Split code, shared font,
CJK32 data and loadable-font changes select their corresponding jobs, while
documentation-only paths select none. `--all` selects all eight maintained
kernel versions in `tools/supported-verification.json`.

An absolute path, a path containing `..`, a missing changed patch, or a patch
that cannot be mapped to a CI job exits 2. Invalid verification data also exits
2. `--all` rejects additional changed paths with exit 2.

## test-patch.sh

Usage: `tools/test-patch.sh [--cjk32] <kernel-version> [patch-file ...]`.

```sh
JOBS=32 tools/test-patch.sh 6.18.44
```

Downloads the kernel if needed, then runs three checks. A patch is only finished
when all three pass:

1. **applies** — `patch -p1 --fuzz=0`, no fuzzy matching allowed.
2. **builds** — a full `bzImage` with the framebuffer console and
   `CONFIG_FONT_CJK_16x16` enabled.
3. **renders** — boots under OVMF and checks the screenshot.

The third check is not an ioctl. cjktty leaves `vc_font` at the base 256-glyph
font and draws CJK from the separate cjktty buffer, so the console keeps reporting
`8x16 charcount=256` whether or not the patch works. `check-console.py` instead
compares two different CJK cells on screen: real glyphs differ and carry ink,
missing glyphs produce the same empty box.

When patch paths are given, `test-patch.sh` applies every patch from left to
right. Explicit paths let a split font-and-code pair go through the same build and boot checks as
a monolithic patch.

`CONFIG_FONT_CJK_32x32` stays off during the test. The base patch ships an empty
`font_cjk_32x32.h`, so enabling `CONFIG_FONT_CJK_32x32` spends 8 MiB on a blank font.

## make-testvm.sh, make-boot-testvm.sh and test-system.sh

`tools/make-testvm.sh` builds `testvm/base.img` once.
`tools/make-boot-testvm.sh` builds the partitioned `boot-testvm/base.img` once.
Usage: `tools/test-system.sh [--bootloader] [--cjk32] <kernel-version>
[patch-file ...]`.

```sh
JOBS=32 tools/test-system.sh 6.18.44
JOBS=32 tools/test-system.sh --bootloader 6.18.44
```

`test-patch.sh` stops at an initramfs, which never reaches the paths changed by cjktty
changes. `test-system.sh` boots a stage3 systemd userland from disk and drives
the rest over the serial port: systemd to `running`, `systemd-vconsole-setup`
reloading the font, `setfont`, `chvt`, the framebuffer handover from efifb to
virtio-gpu, console rotation, an fbcon unbind and rebind, `dmesg` free of oops
and call traces, and `systemctl poweroff`.

Rotation and rebind reach the two code paths most frequently changed by
cjktty-patches. `fbcon_rotate_font_utf()` runs under rotation and nowhere else, and
kernel ports rewrite `fbcon_rotate_font_utf()` more often than
anything else in the patch; `fbcon_release()` frees both font buffers and a normal
shutdown does not reach `fbcon_release()`. Both paths run in one boot through
second boot: `/sys/class/graphics/fbcon/rotate_all` and
`/sys/class/vtconsole/vtcon*/bind`.

The default `test-system.sh` path keeps the kernel out of the image. QEMU receives the kernel through `-kernel`
and the disk is a qcow2 overlay on the base, so swapping kernels costs one build
and no install, and a run cannot damage the base image.

The optional `--bootloader` path uses a separate partitioned base image. The path
builds and installs the kernel modules into an overlay, invokes the image's
`installkernel`, requires dracut to produce a non-empty initramfs and requires
GRUB's generated configuration to name both files. The verification boot then
receives neither `-kernel` nor `-append`; OVMF starts GRUB from the ESP and GRUB
supplies the kernel command line. The serial driver distinguishes GRUB not
starting from GRUB starting but failing to hand off to Linux, and the guest
confirms initramfs unpacking before the normal system test continues.

Three screenshots come out of each run: `login.ppm` is the getty screen,
`rotated.ppm` is the CJK line drawn while the console is turned ninety degrees,
and `console.ppm` is the CJK line after the DRM handover. `check-console.py`
checks the last two.

Every step is an assertion. The bind
loop ends in `[ $n -gt 0 ]` because a loop that matches no console exits 0 and
the release path would go unrun; `test-system.sh` then confirms from `dmesg` that the
console really left the framebuffer driver.

Like `test-patch.sh`, `test-system.sh` applies any explicitly named patches from
left to right.

## split-patch.py

```sh
tools/test-split-patch.sh
```

`tools/split-patch.py <source-patch> <font-output> <code-output>` performs one
split; `tools/test-split-patch.sh` checks the published split patches.

Splits a monolithic patch by complete file stanza. Every hunk for a path matching
`lib/fonts/font_cjk_<width>x<height>.h` goes to the font output; every other hunk
goes to the code output. File metadata stays with the corresponding stanza, so the empty
`font_cjk_32x32.h` is retained in the font output despite having no
`---`/`+++` pair.

The source file list is the ordered union of `diff --git a/` and `--- a/`
headers. Both forms are required: current patches use plain `---` headers for
most files, while an empty new file can have only a `diff --git` header.

Apply `cjktty-font-unifont-15.1.04.patch` before the matching
`cjktty-code-*.patch`.

## test-split-matches-combined.py

```sh
python3 tools/test-split-matches-combined.py
```

Runs `split-patch.py` on the combined counterpart of every
`v[0-9]*.x/cjktty-code-*.patch`, then byte-compares the generated code output
with the published split code patch. The current repository checks eight split forms twice, once for the code half
and once for the font half.

A split code patch with no combined counterpart, code bytes that differ from
splitting that counterpart, or generated font bytes that differ from
`cjktty-font-unifont-15.1.04.patch`, exits 1. Changing the first font data byte
returns eight font failures with eight code passes, exit 1. A deliberately divergent
`cjktty-code-1.0.patch` returned exit 1.

## port.sh

Start a port with `tools/port.sh <new-version> <base-patch>`, resolve every
listed `.rej` file, and finish with `tools/port.sh --finish <new-version>`.

Applies the nearest existing patch to a new kernel, leaves the tree and rejects
for hand fixing, then regenerates the patch. Neighbouring versions usually differ
only in line offsets; a reject means upstream changed a struct field, a function's
visibility, or the order of an allocation.

## regen.sh

Usage: `tools/regen.sh <pristine-tree> <patched-tree> <source-patch> <output>`.

Writes a patch from the difference between two trees. The file list comes from
the source patch's `diff --git` lines, not from `+++`: git emits no `---`/`+++`
pair for an empty new file, and `font_cjk_32x32.h` is empty. Every stanza gets
an independent `diff --git` header so `patch` cannot attach a `new file mode` to the
file that follows.

Prefer editing a patch in place over regeneration. A regenerated 12 MB file
hides a two-line change from review.

## gen-font.py

```sh
tools/gen-font.py --format psf2 --size 16 \
  --base-font "$CJKTTY_LAB/linux-6.18.44/lib/fonts/font_8x16.c" \
  --output "$CJKTTY_LAB/cjk-16.psf" \
  "$CJKTTY_LAB/unifont-15.1.04.hex"
```

Generates the two-cell BMP layout used by cjktty. The first 256 halfwidth
glyphs come from the named Linux base font; `font_ter16x32.c` is derived from
Terminus. Remaining glyphs come from the official GNU Unifont `.hex` release.
`gen-font.py` determines halfwidth versus fullwidth from each hex payload, not
the codepoint, and doubles both axes for 32x32 output. Use
`font/precompiled/unifont-<version>.hex` from the project's
[official release tarball](https://unifoundry.com/pub/unifont/). Both current
arrays match Unifont 15.1.04; later whole-font updates superseded the 13.0.06
source named by the first 32x32 changelog entry.

The generated 16x16 C header selects GPL version 2 and retains the GNU
Unifont 15.1.04 copyright notice. The generated 32x32 C header selects
OFL-1.1 and retains both the Unifont notice and the Terminus Font 4.49.1
copyright and Reserved Font Name notice. The repository's `LICENSE` contains
the copyright notices and the complete GPL version 2 and OFL-1.1 texts. Distribute
generated C headers and PSF2 files with `LICENSE`; PSF2 has no field for license
metadata.

The default output is the C header used by the existing patches. The `psf2`
format wraps the same bytes as 131,072 half-cell glyphs for the loadable-font
prototype.

Pass `--compare` with a generated header or a cjktty patch to verify the data
without writing the generated array:

```sh
tools/gen-font.py --size 16 \
  --base-font "$CJKTTY_LAB/linux-6.18.44/lib/fonts/font_8x16.c" \
  --compare v6.x/cjktty-6.18.patch \
  "$CJKTTY_LAB/unifont-15.1.04.hex"
```

## loadable-font prototype

The command, scope, and current result are in
[`docs/loadable-font.md`](../docs/loadable-font.md#prototype-and-evidence).

`tools/test-loadable-font.sh` tests the existing console-font ioctl as a narrow
prototype. The production design uses a separate CJK object; the prototype does
not implement that ownership model.

## check-console.py

```sh
python3 tools/check-console.py \
  "$CJKTTY_LAB/out-system-6.18.44/console.ppm"
python3 tools/check-console.py --rotated \
  "$CJKTTY_LAB/out-system-6.18.44/rotated.ppm"
```

Both test scripts call `check-console.py`; a direct Python invocation re-checks
a saved screenshot.

The default mode compares two adjacent CJK cells at a known row. `--rotated`
cannot use fixed rows, so `--rotated` measures the bounding box of the lit pixels and
requires a height greater than the width. Ink alone is insufficient: a console
without rotation still shows a horizontal line with the same amount of ink.

## drive-system.py and init.c

`drive-system.py` is the serial driver run by `test-system.sh`; every guest
command has a checked exit status, and a numeric result is read back inside a
unique marker because the stage3 shell wraps the prompt in OSC 133 sequences.
`init.c` is the initramfs init for `test-patch.sh`: `init.c` mounts devtmpfs,
since `CONFIG_DEVTMPFS_MOUNT` applies only to a real root, then prints the CJK
lines the screenshot is taken of.

## test-stress.sh

`tools/test-stress.sh <version> [patch ...]` builds the patch with KASAN,
kmemleak, lockdep and `DEBUG_ATOMIC_SLEEP`, then cycles `setfont`, `chvt`,
console rotation, an fbcon unbind and rebind, a console resize and a burst of
CJK output. `test-system.sh` performs each operation once; a leak on the release
path or a lock taken in the wrong order only appears after repeated operations.

The verdict comes from `tools/stress-verdict.py`, which strips the shell's own
echo of the grep command before counting. Counting the raw serial log reports
the pattern itself as a finding.

Proven to fail: removing one `kvfree(par->fontbuffer_utf)` from
`fbcon_release()` makes kmemleak report `unreferenced object` of 2,097,152
bytes, exactly the 16x16 font buffer, and the script exits 1.

The guest needs 4 GiB because KASAN roughly triples the kernel's memory use.

## Testing the 32x32 font

`--cjk32` on either stage applies `cjktty-add-cjk32x32-font-data.patch` on top
of the base patch, turns `CONFIG_FONT_CJK_32x32` on and `CONFIG_FONT_CJK_16x16`
off, and selects `FONT_TER16x32` as the base font.

```sh
JOBS=32 tools/test-patch.sh --cjk32 6.18.44
JOBS=32 tools/test-system.sh --cjk32 6.18.44
```

Without the data patch, `CONFIG_FONT_CJK_32x32` compiles 8 MiB of zeros.
Therefore the option defaults off, and `--cjk32` applies the data patch.

The console cell follows the base font, so `--cjk32` passes `--cell 16x32` to
`check-console.py`. Sampling 8x16 cells on a 16x32 screen lands between glyphs
and reports a blank cell on a working kernel.

`scripts/config` exits 0 without changing `CONFIG_FONT_CJK_16x16` or
`CONFIG_FONT_CJK_32x32`, so `set_option` deletes
the line and appends the wanted form. `defconfig` omits a symbol whose default
is n, so absence there is normal; the assertion after `olddefconfig` is what
proves the symbol exists.

Measured on 6.18.44: 16x16 draws 144 and 135 lit subpixels, 32x32 draws 576 and
540, four times the area for glyphs twice as wide and twice as tall.

## test-cjk32-applies.py

```sh
python3 tools/test-cjk32-applies.py
```

Reads the maintained kernel versions from
`tools/supported-verification.json`, selects each serving base patch, and
compares the order of `.charcount`, `.data` and `.pref` in its
`font_cjk_32x32` descriptor with the context order in
`cjktty-add-cjk32x32-font-data.patch`. The current repository checks eight base
patches. This is a descriptor-context check; it does not apply either patch to a
kernel tree, and a base patch with no descriptor is skipped.

A data patch with no `font_cjk_32x32` descriptor, or a selected base patch with
a different field order, exits 1. A fixture that marked Linux 5.10 as maintained
selected `cjktty-5.10.patch`; its `.data`, `.pref`, `.charcount` order made the
check return exit 1.

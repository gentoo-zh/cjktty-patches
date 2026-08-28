#!/bin/bash
# Apply a cjktty patch, build the kernel, boot it and check the console font.
#
# Usage: tools/test-patch.sh [--cjk32] <kernel-version> [patch-file ...]
#
#   tools/test-patch.sh 6.18.43
#   tools/test-patch.sh 7.0 v7.x/cjktty-7.0.patch
#   tools/test-patch.sh 6.18.44 cjktty-font-v2.patch cjktty-code-v2-6.18.patch
#
# A patch passes only when all three succeed: it applies with no fuzz, the
# kernel builds, and the booted console reports the CJK font. Artifacts stay in
# $CJKTTY_LAB for inspection.
set -uo pipefail

repo=$(cd "$(dirname "$0")/.." && pwd)
lab=${CJKTTY_LAB:-$(cd "$repo/.." && pwd)/lab}
ovmf_code=${OVMF_CODE:-/usr/share/edk2-ovmf/OVMF_CODE_4M.qcow2}
ovmf_vars=${OVMF_VARS:-/usr/share/edk2-ovmf/OVMF_VARS.fd}
jobs=${JOBS:-$(nproc)}
boot_timeout=${BOOT_TIMEOUT:-120}

die() { echo "$*" >&2; exit 1; }
step() { printf '\n== %s\n' "$*"; }

cjk32=0
if [ "${1:-}" = "--cjk32" ]; then
	cjk32=1
	shift
fi

[ $# -ge 1 ] || die "usage: $0 [--cjk32] <kernel-version> [patch-file ...]"
version=$1
series=${version%%.*}
shift

patch_files=("$@")
if [ ${#patch_files[@]} -eq 0 ]; then
	command -v python3 >/dev/null || die "python3 is not installed"
	selected_patch=$(python3 "$repo/tools/patch_selection.py" "$repo" "$version") ||
		die "no patch for $version"
	patch_files=("$selected_patch")
fi
for patch_file in "${patch_files[@]}"; do
	[ -f "$patch_file" ] || die "patch not found: $patch_file"
done

for tool in gcc cpio qemu-system-x86_64 patch; do
	command -v "$tool" >/dev/null || die "$tool is not installed"
done
[ -f "$ovmf_code" ] || die "OVMF firmware not found at $ovmf_code; set OVMF_CODE"

mkdir -p "$lab"
tarball="$lab/linux-$version.tar.xz"
pristine="$lab/linux-$version"
tree="$lab/test-$version"
out="$lab/out-$version"
mkdir -p "$out"

step "kernel source $version"
if [ ! -d "$pristine" ]; then
	tarball=$("$repo/tools/fetch-kernel.sh" "$version" "$lab") ||
		die "cannot fetch linux-$version"
	tar -xf "$tarball" -C "$lab" || die "cannot unpack $tarball"
fi

patch_names=()
for patch_file in "${patch_files[@]}"; do
	patch_names+=("$(basename "$patch_file")")
done
step "apply ${patch_names[*]}"
rm -rf "$tree"
cp -a "$pristine" "$tree"
for patch_file in "${patch_files[@]}"; do
	patch -d "$tree" -p1 --fuzz=0 --silent < "$patch_file" ||
		die "$(basename "$patch_file") does not apply to $version with fuzz=0"
done
if [ "$cjk32" = 1 ]; then
	patch -d "$tree" -p1 --fuzz=0 --silent < "$repo/cjktty-add-cjk32x32-font-data.patch" ||
		die "the 32x32 font data patch does not apply to $version"
fi
find "$tree" -name '*.orig' -delete

step "configure"
make -C "$tree" -s x86_64_defconfig >/dev/null || die "defconfig failed"
# FB_EFI drives the framebuffer under OVMF. Without a framebuffer console the
# kernel falls back to vgacon, whose font holds 512 glyphs and cannot show CJK.
# FONT_CJK_32x32 stays off: the base patch ships an empty font_cjk_32x32.h, so
# it would cost 8 MiB for a blank font.
"$tree/scripts/config" --file "$tree/.config" \
	-e CONFIG_FB -e CONFIG_FB_EFI -e CONFIG_FB_SIMPLE -e CONFIG_SYSFB_SIMPLEFB \
	-e CONFIG_DRM_FBDEV_EMULATION -e CONFIG_FRAMEBUFFER_CONSOLE \
	-e CONFIG_FRAMEBUFFER_CONSOLE_ROTATION -e CONFIG_CONSOLE_TRANSLATIONS \
	-e CONFIG_FONTS \
	-e CONFIG_BLK_DEV_INITRD -e CONFIG_DEVTMPFS -e CONFIG_DEVTMPFS_MOUNT \
	-e CONFIG_SERIAL_8250 -e CONFIG_SERIAL_8250_CONSOLE || die "scripts/config failed"
# scripts/config exits 0 without touching these symbols, so rewrite the line
# outright; olddefconfig keeps what it finds here.
set_option() {
	# defconfig omits a symbol whose default is n, so absence is normal here;
	# the assertion after olddefconfig is what proves the symbol exists.
	local name=$1 value=$2 file=$tree/.config
	sed -i "/^CONFIG_$name=/d; /^# CONFIG_$name is not set/d" "$file"
	if [ "$value" = n ]; then
		echo "# CONFIG_$name is not set" >> "$file"
	else
		echo "CONFIG_$name=$value" >> "$file"
	fi
}
if [ "$cjk32" = 1 ]; then
	# ter16x32 becomes the base font, so the console cell doubles in both axes
	set_option FONT_CJK_16x16 n
	set_option FONT_CJK_32x32 y
	set_option FONT_TER16x32 y
	# fbcon picks the first registered font, so 8x16 has to go or the console
	# stays 8x16 and the 32x32 path is never reached
	set_option FONT_8x16 n
else
	set_option FONT_CJK_16x16 y
	set_option FONT_CJK_32x32 n
fi
make -C "$tree" -s olddefconfig >/dev/null || die "olddefconfig failed"
want=CONFIG_FONT_CJK_16x16
[ "$cjk32" = 1 ] && want=CONFIG_FONT_CJK_32x32
grep -q "^$want=y" "$tree/.config" ||
	die "$want did not enable; the patch may not touch lib/fonts"

step "build"
make -C "$tree" -j"$jobs" bzImage > "$out/build.log" 2>&1 || {
	tail -20 "$out/build.log"
	die "kernel build failed, see $out/build.log"
}
warnings=$(grep -c 'warning:' "$out/build.log")
echo "built with $warnings warnings"

step "initramfs"
initdir="$lab/initramfs-$version"
rm -rf "$initdir"
mkdir -p "$initdir"/{proc,sys,dev}
gcc -static -Os -o "$initdir/init" "$repo/tools/init.c" 2>/dev/null || die "cannot build init"
strip "$initdir/init"
(cd "$initdir" && find . | cpio -o -H newc --quiet | gzip -1 > "$out/initramfs.gz") ||
	die "cannot pack initramfs"

step "boot"
cp -f "$ovmf_vars" "$out/OVMF_VARS.fd"
rm -f "$out/serial.log" "$out/console.ppm" "$out/monitor.sock"
# -cpu max: init is statically linked against the host glibc, which on a
# -march=native build carries AVX the default model lacks. 'host' would
# do, but CI drops -enable-kvm and 'host' needs KVM; 'max' works on both.
qemu-system-x86_64 -enable-kvm -cpu max -m 2G -smp 2 -machine q35 \
	-drive "if=pflash,format=qcow2,readonly=on,file=$ovmf_code" \
	-drive "if=pflash,format=raw,file=$out/OVMF_VARS.fd" \
	-kernel "$tree/arch/x86/boot/bzImage" -initrd "$out/initramfs.gz" \
	-append 'console=tty0 console=ttyS0,115200 rdinit=/init' \
	-vga std -display none \
	-serial "file:$out/serial.log" \
	-monitor "unix:$out/monitor.sock,server,nowait" >/dev/null 2>&1 &
qemu=$!

deadline=$((SECONDS + boot_timeout))
while [ $SECONDS -lt $deadline ]; do
	grep -q 'CJKTTY-BOOTED' "$out/serial.log" 2>/dev/null && break
	kill -0 $qemu 2>/dev/null || break
	sleep 2
done

if [ -S "$out/monitor.sock" ]; then
	printf 'screendump %s\n' "$out/console.ppm" |
		timeout 20 socat - "unix-connect:$out/monitor.sock" >/dev/null 2>&1 ||
		python3 -c "
import socket, sys, time
s = socket.socket(socket.AF_UNIX)
s.connect(sys.argv[1])
time.sleep(0.5)
s.sendall(b'screendump ' + sys.argv[2].encode() + b'\n')
time.sleep(3)
" "$out/monitor.sock" "$out/console.ppm" 2>/dev/null
fi
kill $qemu 2>/dev/null
wait $qemu 2>/dev/null

grep -q 'CJKTTY-BOOTED' "$out/serial.log" 2>/dev/null ||
	die "the guest never reached the test; see $out/serial.log"
vcfont=$(grep -o 'vc-font: .*' "$out/serial.log" | head -1)
echo "$vcfont"
want_font=8x16
[ "$cjk32" = 1 ] && want_font=16x32
case "$vcfont" in
*"vc-font: $want_font"*) ;;
*) die "the console used ${vcfont:-no font}, not $want_font; the tested path is not the one intended" ;;
esac

step "console"
[ -s "$out/console.ppm" ] || die "no screenshot was captured; see $out/serial.log"
cell=8x16
[ "$cjk32" = 1 ] && cell=16x32
python3 "$repo/tools/check-console.py" --cell "$cell" "$out/console.ppm" ||
	die "$version: the console did not render CJK; see $out/console.ppm"

echo
echo "$version: PASS (applies with fuzz=0, builds, renders CJK on the console)"
echo "artifacts in $out"
rm -rf "$tree"

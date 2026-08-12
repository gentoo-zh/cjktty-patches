#!/bin/bash
# Build and boot the narrow loadable-font proof against Linux 6.18.
set -euo pipefail

repo=$(cd "$(dirname "$0")/.." && pwd)
lab=${CJKTTY_LAB:-$(cd "$repo/.." && pwd)/lab}
ovmf_code=${OVMF_CODE:-/usr/share/edk2-ovmf/OVMF_CODE_4M.qcow2}
ovmf_vars=${OVMF_VARS:-/usr/share/edk2-ovmf/OVMF_VARS.fd}
jobs=${JOBS:-8}
version=${1:-6.18.44}
patch_file=${2:-$repo/v6.x/cjktty-6.18.patch}
unifont=${UNIFONT_HEX:-$lab/unifont-15.1.04.hex}
pristine=$lab/linux-$version
work=$lab/loadfont-poc
tree=$work/linux-$version
out=$work/out
qemu_pid=

die() { echo "$*" >&2; exit 1; }
step() { printf '\n== %s\n' "$*"; }

stop_qemu()
{
	if [ -n "$qemu_pid" ]; then
		kill "$qemu_pid" 2>/dev/null || true
		wait "$qemu_pid" 2>/dev/null || true
		qemu_pid=
	fi
}
trap stop_qemu EXIT

wait_for_marker()
{
	local marker=$1
	local count

	for count in $(seq 1 300); do
		grep -Fq "$marker" "$out/serial.log" 2>/dev/null && return 0
		kill -0 "$qemu_pid" 2>/dev/null || return 1
		sleep 0.1
	done
	return 1
}

screendump()
{
	local output=$1

	printf 'screendump %s\n' "$output" |
		timeout 10 socat - "unix-connect:$out/monitor.sock" >/dev/null
	[ -s "$output" ] || die "QEMU did not write $output"
}

for tool in cpio gcc nm patch qemu-system-x86_64 socat; do
	command -v "$tool" >/dev/null || die "$tool is not installed"
done
[ "$version" = 6.18.44 ] || die "the proof patch is scoped to Linux 6.18.44"
[ -d "$pristine" ] || die "kernel source not found at $pristine"
[ -f "$patch_file" ] || die "cjktty patch not found at $patch_file"
[ -f "$unifont" ] || die "Unifont hex file not found at $unifont"
[ -f "$ovmf_code" ] || die "OVMF firmware not found at $ovmf_code"

case "$work" in
	*/loadfont-poc) ;;
	*) die "refusing unsafe work directory: $work" ;;
esac

step "prepare scratch kernel"
rm -rf -- "$work"
mkdir -p "$work" "$out"
cp -a "$pristine" "$tree"
patch -d "$tree" -p1 --fuzz=0 --silent < "$patch_file"
patch -d "$tree" -p1 --fuzz=0 --silent < "$repo/tools/loadable-font-poc.patch"
find "$tree" -name '*.orig' -delete

step "configure without a built-in CJK font"
make -C "$tree" -s x86_64_defconfig >/dev/null
"$tree/scripts/config" --file "$tree/.config" \
	-e FB -e FB_EFI -e FB_SIMPLE -e SYSFB_SIMPLEFB \
	-e DRM_FBDEV_EMULATION -e FRAMEBUFFER_CONSOLE \
	-e FRAMEBUFFER_CONSOLE_ROTATION -e CONSOLE_TRANSLATIONS \
	-e FONTS --keep-case -e FONT_8x16 -d FONT_CJK_16x16 \
	-d FONT_CJK_32x32 -e BLK_DEV_INITRD -e DEVTMPFS \
	-e DEVTMPFS_MOUNT -e SERIAL_8250 -e SERIAL_8250_CONSOLE
make -C "$tree" -s olddefconfig >/dev/null
grep -qx 'CONFIG_FONT_8x16=y' "$tree/.config" ||
	die "CONFIG_FONT_8x16 was not enabled"
grep -qx '# CONFIG_FONT_CJK_16x16 is not set' "$tree/.config" ||
	die "CONFIG_FONT_CJK_16x16 was not disabled"
grep -qx '# CONFIG_FONT_CJK_32x32 is not set' "$tree/.config" ||
	die "CONFIG_FONT_CJK_32x32 was not disabled"

step "build kernel with $jobs jobs"
make -C "$tree" -j"$jobs" bzImage > "$out/build.log" 2>&1 || {
	tail -30 "$out/build.log"
	die "kernel build failed"
}
if nm "$tree/vmlinux" |
	grep -E 'font_cjk_(16x16|32x32)' > "$out/font-symbols"; then
	die "the built kernel still contains the CJK font symbol"
fi

step "generate external PSF2 font and initramfs"
"$repo/tools/gen-font.py" --format psf2 --size 16 \
	--base-font "$tree/lib/fonts/font_8x16.c" --output "$work/cjk-16.psf" \
	"$unifont"
mkdir -p "$work/initramfs"/{dev,proc,sys}
gcc -static -Os -Wall -Wextra -Werror \
	-o "$work/initramfs/load-cjk-font" "$repo/tools/load-cjk-font.c"
gcc -static -Os -Wall -Wextra -Werror \
	-o "$work/initramfs/init" "$repo/tools/loadable-font-init.c"
cp "$work/cjk-16.psf" "$work/initramfs/cjk-16.psf"
(cd "$work/initramfs" &&
	find . -print0 | cpio --null -o -H newc --quiet | gzip -1 > "$out/initramfs.gz")

step "boot and capture before and after loading"
cp "$ovmf_vars" "$out/OVMF_VARS.fd"
qemu-system-x86_64 -enable-kvm -m 2G -smp 2 -machine q35 \
	-drive "if=pflash,format=qcow2,readonly=on,file=$ovmf_code" \
	-drive "if=pflash,format=raw,file=$out/OVMF_VARS.fd" \
	-kernel "$tree/arch/x86/boot/bzImage" -initrd "$out/initramfs.gz" \
	-append 'console=tty0 console=ttyS0,115200 rdinit=/init' \
	-vga std -display none -serial "file:$out/serial.log" \
	-monitor "unix:$out/monitor.sock,server,nowait" >/dev/null 2>&1 &
qemu_pid=$!

wait_for_marker CJKTTY-BEFORE-LOAD || die "guest did not reach the pre-load marker"
screendump "$out/before.ppm"
wait_for_marker CJKTTY-AFTER-LOAD || die "guest did not load the font"
screendump "$out/after.ppm"
stop_qemu

step "prove the rendering transition"
if python3 "$repo/tools/check-console.py" "$out/before.ppm" \
	> "$out/before-check.log" 2>&1; then
	die "CJK unexpectedly rendered before the external font was loaded"
fi
python3 "$repo/tools/check-console.py" "$out/after.ppm"
grep -Fq 'CJKTTY-IOCTL-SUCCESS' "$out/serial.log" ||
	die "the loader ioctl did not return success"
echo "loader ioctl: success"
echo "built-in CJK font: absent"
echo "before load: CJK rendering check failed as expected"
echo "after load: CJK rendering check passed"
echo "loadable-font proof: PASS"
echo "artifacts in $out"

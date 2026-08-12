#!/bin/bash
# Build a debug kernel with the patch and hammer the paths cjktty changes.
#
# Usage: tools/test-stress.sh <kernel-version> [patch-file ...]
#
# test-system.sh proves a patched kernel boots and draws CJK once. It never
# repeats an operation, so it cannot see a leak on the release path or a lock
# taken in the wrong order. This turns on KASAN, kmemleak and lockdep, then
# cycles setfont, chvt, console rotation and an fbcon unbind and rebind.
set -uo pipefail

repo=$(cd "$(dirname "$0")/.." && pwd)
lab=${CJKTTY_LAB:-$(cd "$repo/.." && pwd)/lab}
ovmf_code=${OVMF_CODE:-/usr/share/edk2-ovmf/OVMF_CODE_4M.qcow2}
ovmf_vars=${OVMF_VARS:-/usr/share/edk2-ovmf/OVMF_VARS.fd}
jobs=${JOBS:-$(nproc)}

die() { echo "$*" >&2; exit 1; }
step() { printf '\n== %s\n' "$*"; }

[ $# -ge 1 ] || die "usage: $0 <kernel-version> [patch-file ...]"
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

base="$lab/testvm/base.img"
[ -f "$base" ] || die "no base image; run tools/make-testvm.sh first"

out=$lab/out-stress-$version
tree=$lab/stress-$version
mkdir -p "$out"

step "kernel source $version"
pristine="$lab/linux-$version"
if [ ! -d "$pristine" ]; then
	tarball=$("$repo/tools/fetch-kernel.sh" "$version" "$lab") ||
		die "cannot fetch linux-$version"
	tar -xf "$tarball" -C "$lab" || die "cannot unpack $tarball"
fi

step "apply"
rm -rf "$tree"
cp -a "$pristine" "$tree"
for p in "${patch_files[@]}"; do
	patch -d "$tree" -p1 --fuzz=0 --silent < "$p" ||
		die "$(basename "$p") does not apply to $version with fuzz=0"
done
find "$tree" -name '*.orig' -delete

step "configure"
make -C "$tree" -s x86_64_defconfig >/dev/null || die "defconfig failed"
# KASAN_OUTLINE keeps the build time tolerable; BTF doubles it and is unused here.
"$tree/scripts/config" --file "$tree/.config" \
	-e CONFIG_FB -e CONFIG_FB_EFI -e CONFIG_SYSFB_SIMPLEFB \
	-e CONFIG_DRM -e CONFIG_DRM_VIRTIO_GPU -e CONFIG_DRM_FBDEV_EMULATION \
	-e CONFIG_FRAMEBUFFER_CONSOLE -e CONFIG_FRAMEBUFFER_CONSOLE_DETECT_PRIMARY \
	-e CONFIG_FRAMEBUFFER_CONSOLE_ROTATION -e CONFIG_CONSOLE_TRANSLATIONS \
	-e CONFIG_FONTS -e CONFIG_FONT_CJK_16x16 -d CONFIG_FONT_CJK_32x32 \
	-e CONFIG_VIRTIO -e CONFIG_VIRTIO_PCI -e CONFIG_VIRTIO_BLK \
	-e CONFIG_EXT4_FS -e CONFIG_DEVTMPFS -e CONFIG_DEVTMPFS_MOUNT \
	-e CONFIG_SERIAL_8250 -e CONFIG_SERIAL_8250_CONSOLE \
	-e CONFIG_CGROUPS -e CONFIG_INOTIFY_USER -e CONFIG_SIGNALFD -e CONFIG_TIMERFD \
	-e CONFIG_EPOLL -e CONFIG_TMPFS -e CONFIG_TMPFS_POSIX_ACL \
	-e CONFIG_AUTOFS_FS -e CONFIG_NET_NS -e CONFIG_PROC_FS -e CONFIG_SYSFS \
	-e CONFIG_DEBUG_KERNEL -e CONFIG_DEBUG_FS \
	-e CONFIG_KASAN -e CONFIG_KASAN_GENERIC -e CONFIG_KASAN_OUTLINE \
	-e CONFIG_DEBUG_KMEMLEAK -e CONFIG_PROVE_LOCKING -e CONFIG_LOCKDEP \
	-e CONFIG_DEBUG_ATOMIC_SLEEP -e CONFIG_DEBUG_SPINLOCK \
	-d CONFIG_MODULE_SIG_ALL -d CONFIG_DEBUG_INFO_BTF -d CONFIG_RANDOMIZE_BASE ||
	die "scripts/config failed"
make -C "$tree" -s olddefconfig >/dev/null || die "olddefconfig failed"
for o in CONFIG_KASAN CONFIG_DEBUG_KMEMLEAK CONFIG_PROVE_LOCKING CONFIG_FONT_CJK_16x16; do
	grep -q "^$o=y" "$tree/.config" || die "$o did not enable"
done

step "build"
make -C "$tree" -j"$jobs" bzImage > "$out/build.log" 2>&1 ||
	{ tail -25 "$out/build.log"; die "build failed, see $out/build.log"; }
echo "built with $(grep -c 'warning:' "$out/build.log") warnings"

step "stress"
rm -f "$out/disk.qcow2" "$out/serial.log" "$out/serial.sock"
qemu-img create -q -f qcow2 -F raw -b "$base" "$out/disk.qcow2" >/dev/null ||
	die "cannot create the overlay"
cp -f "$ovmf_vars" "$out/OVMF_VARS.fd"
qemu-system-x86_64 -enable-kvm -m 4G -smp 4 -machine q35 \
	-drive "if=pflash,format=qcow2,readonly=on,file=$ovmf_code" \
	-drive "if=pflash,format=raw,file=$out/OVMF_VARS.fd" \
	-drive "file=$out/disk.qcow2,format=qcow2,if=virtio" \
	-kernel "$tree/arch/x86/boot/bzImage" \
	-append 'root=/dev/vda rw console=tty0 console=ttyS0,115200 kmemleak=on' \
	-vga virtio -display none \
	-serial "unix:$out/serial.sock,server,nowait" >/dev/null 2>&1 &
qemu=$!
python3 "$repo/tools/drive-stress.py" "$out" "${STRESS_TIMEOUT:-1800}"
driver=$?
kill $qemu 2>/dev/null
wait $qemu 2>/dev/null
[ $driver -eq 0 ] || die "$version: the stress driver failed; see $out/serial.log"

step "verdict"
python3 "$repo/tools/stress-verdict.py" "$out/serial.log" ||
	die "$version: KASAN, kmemleak or lockdep reported something; see $out/serial.log"

echo
echo "$version: PASS (KASAN, kmemleak and lockdep clean under setfont, chvt, rotation and fbcon rebind)"
echo "artifacts in $out"
rm -rf "$tree"

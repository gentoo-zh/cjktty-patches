#!/bin/bash
# Build the partitioned base image used by the bootloader system test.
#
# Usage: tools/make-boot-testvm.sh [--force]
#
# This image is separate from make-testvm.sh's ext4 filesystem image. It has a
# GPT, an EFI System Partition mounted at /boot, and an ext4 root containing
# GRUB, dracut and installkernel. Kernels are installed into throwaway overlays
# by test-system.sh --bootloader, so the base never contains a test kernel.
set -uo pipefail

repo=$(cd "$(dirname "$0")/.." && pwd)
lab=${CJKTTY_LAB:-$(cd "$repo/.." && pwd)/lab}
mirror=${GENTOO_MIRROR:-https://distfiles.gentoo.org}
size=${BOOT_IMAGE_SIZE:-8G}

dir="$lab/boot-testvm"
base="$dir/base.img"
building="$dir/base.img.build"
root="$dir/root"

die() { echo "$*" >&2; exit 1; }
step() { printf '\n== %s\n' "$*"; }

cleanup() {
	set +e
	for target in "$root/dev" "$root/sys" "$root/proc"; do
		mountpoint -q "$target" && sudo umount -l "$target"
	done
}
trap cleanup EXIT

case ${1:-} in
	--force) sudo rm -rf "$dir" ;;
	"") ;;
	*) die "usage: $0 [--force]" ;;
esac
[ -f "$base" ] && { echo "$base already exists; pass --force to rebuild"; exit 0; }

for tool in chroot curl dd mkfs.ext4 mkfs.vfat mount sgdisk sudo tar truncate; do
	command -v "$tool" >/dev/null || die "$tool is not installed"
done

mkdir -p "$dir"

step "stage3"
pointer="$dir/latest-stage3.txt"
curl -fsS -o "$pointer" \
	"$mirror/releases/amd64/autobuilds/latest-stage3-amd64-systemd.txt" ||
	die "cannot fetch the stage3 pointer"
relative=$(grep -oE '[0-9]{8}T[0-9]{6}Z/stage3-amd64-systemd-[^ ]+\.tar\.xz' "$pointer" | head -1)
[ -n "$relative" ] || die "the stage3 pointer is empty"
tarball="$dir/$(basename "$relative")"
[ -f "$tarball" ] ||
	curl -fL# -o "$tarball" "$mirror/releases/amd64/autobuilds/$relative" ||
	die "cannot download the stage3"

step "partition"
rm -f "$building"
truncate -s "$size" "$building" || die "cannot allocate $building"
sgdisk --zap-all \
	--new=1:2048:+512M --typecode=1:ef00 --change-name=1:ESP \
	--new=2:0:0 --typecode=2:8300 --change-name=2:root \
	"$building" >/dev/null || die "cannot partition $building"

step "unpack"
sudo rm -rf "$root"
sudo mkdir -p "$root"
sudo tar -xpf "$tarball" -C "$root" --xattrs-include='*.*' --numeric-owner ||
	die "cannot unpack the stage3"

step "configure"
# Root logs in on the serial port with no password. The test drives the VM only
# through the host-side serial connection.
sudo sed -i 's|^root:[^:]*:|root::|' "$root/etc/shadow"
echo cjktty-test | sudo tee "$root/etc/hostname" >/dev/null
printf 'LABEL=cjktty-test / ext4 defaults,noatime 0 1\nLABEL=CJKTTY-ESP /boot vfat defaults,noatime 0 2\n' |
	sudo tee "$root/etc/fstab" >/dev/null
sudo ln -sf /usr/lib/systemd/system/serial-getty@.service \
	"$root/etc/systemd/system/getty.target.wants/serial-getty@ttyS0.service"
sudo mkdir -p "$root/etc/systemd/system/serial-getty@ttyS0.service.d"
printf '[Service]\nExecStart=\nExecStart=-/sbin/agetty -o "-p -- \\\\u" --autologin root --keep-baud 115200,57600,38400,9600 %%I $TERM\n' |
	sudo tee "$root/etc/systemd/system/serial-getty@ttyS0.service.d/autologin.conf" >/dev/null
printf 'FONT=LatArCyrHeb-16\nKEYMAP=us\n' | sudo tee "$root/etc/vconsole.conf" >/dev/null

# The explicit command line makes installkernel's chroot safety check accept
# dracut and keeps the generated initramfs independent of the host system.
printf 'root=LABEL=cjktty-test rootfstype=ext4 rw console=tty0 console=ttyS0,115200 cjktty.bootloader=1\n' |
	sudo tee "$root/etc/cmdline" >/dev/null
sudo mkdir -p "$root/etc/portage/package.use" "$root/var/tmp/portage"
printf 'sys-boot/grub -branding -fonts -nls -sdl -themes -truetype\nsys-kernel/installkernel dracut grub -systemd -efistub -refind -systemd-boot -ugrd -uki -ukify\n' |
	sudo tee "$root/etc/portage/package.use/cjktty-test" >/dev/null
printf '\nGRUB_PLATFORMS="efi-64"\nMAKEOPTS="-j%s"\nPORTAGE_TMPDIR="/var/tmp/portage"\n' "$(nproc)" |
	sudo tee -a "$root/etc/portage/make.conf" >/dev/null
sudo cp -L /etc/resolv.conf "$root/etc/resolv.conf"

sudo mount --bind /dev "$root/dev" || die "cannot bind /dev"
sudo mount --bind /sys "$root/sys" || die "cannot bind /sys"
sudo mount -t proc proc "$root/proc" || die "cannot mount /proc"

step "boot packages"
sudo chroot "$root" /usr/bin/emerge-webrsync || die "emerge-webrsync failed"
sudo chroot "$root" /usr/bin/emerge --getbinpkg --jobs "$(nproc)" \
	sys-boot/grub:2 sys-fs/mtools sys-kernel/dracut sys-kernel/installkernel ||
	die "cannot install GRUB, dracut and installkernel"

step "GRUB"
sudo mkdir -p "$root/etc/default" "$root/etc/grub.d"
sudo tee "$root/etc/default/grub" >/dev/null <<'EOF'
GRUB_DEFAULT=0
GRUB_TIMEOUT=0
GRUB_TIMEOUT_STYLE=hidden
GRUB_DISABLE_RECOVERY=true
GRUB_DISABLE_SUBMENU=y
GRUB_CMDLINE_LINUX="root=LABEL=cjktty-test rootfstype=ext4 rw console=tty0 console=ttyS0,115200 cjktty.bootloader=1"
GRUB_CMDLINE_LINUX_DEFAULT=""
GRUB_SERIAL_COMMAND="serial --speed=115200 --unit=0 --word=8 --parity=no --stop=1"
GRUB_TERMINAL_INPUT="console serial"
GRUB_TERMINAL_OUTPUT="console serial"
EOF
sudo mkdir -p "$root/etc/dracut.conf.d"
sudo tee "$root/etc/dracut.conf.d/cjktty-test.conf" >/dev/null <<'EOF'
hostonly="no"
hostonly_cmdline="no"
compress="gzip"
EOF
sudo tee "$root/etc/grub.d/01_cjktty_serial" >/dev/null <<'EOF'
#!/bin/sh
cat <<'GRUB_EOF'
echo CJKTTY-GRUB-STARTED
GRUB_EOF
EOF
sudo chmod 0755 "$root/etc/grub.d/01_cjktty_serial"
sudo mkdir -p "$root/boot/grub"
sudo tee "$root/boot/grub/grub.cfg" >/dev/null <<'EOF'
echo CJKTTY-GRUB-STARTED
echo CJKTTY-GRUB-NO-KERNEL
halt
EOF

# grub-install and grub-mkconfig insist on probing the device below /boot. This
# root is an offline directory, so build the removable EFI loader directly.
# installkernel replaces the placeholder grub.cfg inside the running guest.
sudo mkdir -p "$root/boot/EFI/BOOT"
sudo tee "$root/tmp/cjktty-grub-early.cfg" >/dev/null <<'EOF'
search --file --set=root /grub/grub.cfg
set prefix=($root)/grub
configfile /grub/grub.cfg
EOF
sudo chroot "$root" grub-mkstandalone -O x86_64-efi \
	-o /boot/EFI/BOOT/BOOTX64.EFI --fonts= --themes= --locales= \
	--modules='part_gpt fat search_fs_file configfile' \
	'boot/grub/grub.cfg=/tmp/cjktty-grub-early.cfg' ||
	die "grub-mkstandalone failed"
sudo cp -a "$root/usr/lib/grub/x86_64-efi" "$root/boot/grub/" ||
	die "cannot stage the GRUB EFI modules"

sudo rm -rf "$root/var/tmp/portage"/*
sudo sync
cleanup
trap - EXIT

step "filesystems"
esp_start=$(sgdisk -i 1 "$building" | awk '/First sector:/ { print $3 }')
esp_end=$(sgdisk -i 1 "$building" | awk '/Last sector:/ { print $3 }')
root_start=$(sgdisk -i 2 "$building" | awk '/First sector:/ { print $3 }')
root_end=$(sgdisk -i 2 "$building" | awk '/Last sector:/ { print $3 }')
for value in "$esp_start" "$esp_end" "$root_start" "$root_end"; do
	[[ $value =~ ^[0-9]+$ ]] || die "cannot read the GPT partition bounds"
done

esp_image="$root/root/esp.img"
root_image="$dir/root.img"
sudo truncate -s "$(((esp_end - esp_start + 1) * 512))" "$esp_image"
sudo mkfs.vfat -F 32 -n CJKTTY-ESP "$esp_image" >/dev/null || die "cannot format the ESP"
sudo chroot "$root" /bin/bash -c \
	'MTOOLS_SKIP_CHECK=1 mcopy -i /root/esp.img -s /boot/EFI /boot/grub ::/' ||
	die "cannot copy GRUB to the ESP"
sudo mv "$esp_image" "$dir/esp.img"

truncate -s "$(((root_end - root_start + 1) * 512))" "$root_image"
sudo mkfs.ext4 -q -F -L cjktty-test -d "$root" "$root_image" ||
	die "cannot build the root filesystem"
dd if="$dir/esp.img" of="$building" bs=512 seek="$esp_start" conv=notrunc,sparse status=none ||
	die "cannot place the ESP in $building"
dd if="$root_image" of="$building" bs=512 seek="$root_start" conv=notrunc,sparse status=none ||
	die "cannot place the root filesystem in $building"
sgdisk -v "$building" >/dev/null || die "the completed GPT is invalid"

sudo rm -rf "$root"
rm -f "$dir/esp.img" "$root_image"
mv "$building" "$base"

[ -s "$base" ] || die "the base image is empty"
echo
echo "bootloader base image: $base ($(du -h "$base" | cut -f1))"
echo "now run: tools/test-system.sh --bootloader <kernel-version>"

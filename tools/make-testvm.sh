#!/bin/bash
# Build the base image the system test boots.
#
# Usage: tools/make-testvm.sh [--force] [--variant systemd|openrc] [--snapshot SNAPSHOT] [--output IMAGE]
#
# One ext4 image holding a Gentoo userland, built once and reused. The
# kernel is never installed into it: test-system.sh passes the kernel on the
# QEMU command line and gives each run its own qcow2 overlay, so swapping
# kernels costs nothing and no run can damage the base.
set -uo pipefail

repo=$(cd "$(dirname "$0")/.." && pwd)
lab=${CJKTTY_LAB:-$(cd "$repo/.." && pwd)/lab}
mirror=${GENTOO_MIRROR:-https://distfiles.gentoo.org}
size=${IMAGE_SIZE:-6G}
release_keyring=${GENTOO_RELEASE_KEYRING:-/etc/portage/gnupg/pubring.kbx}

base="$lab/testvm/base.img"
snapshot=latest
variant=systemd
force=0

die() { echo "$*" >&2; exit 1; }
step() { printf '\n== %s\n' "$*"; }

while [ $# -gt 0 ]; do
	case "$1" in
	--force)
		force=1
		shift
		;;
	--snapshot)
		[ $# -ge 2 ] || die "--snapshot needs an argument"
		snapshot=$2
		shift 2
		;;
	--variant)
		[ $# -ge 2 ] || die "--variant needs an argument"
		variant=$2
		shift 2
		;;
	--output)
		[ $# -ge 2 ] || die "--output needs an argument"
		base=$2
		shift 2
		;;
	*)
		die "usage: $0 [--force] [--variant systemd|openrc] [--snapshot SNAPSHOT] [--output IMAGE]"
		;;
	esac
done
[ "$variant" = systemd ] || [ "$variant" = openrc ] ||
	die "invalid stage3 variant: $variant"
[ "$snapshot" = latest ] ||
	[[ $snapshot =~ ^[0-9]{8}T[0-9]{6}Z$ ]] ||
	die "invalid snapshot: $snapshot"

metadata="$base.metadata"
if [ -f "$base" ] && [ $force -eq 0 ]; then
	echo "$base already exists; pass --force to rebuild"
	exit 0
fi

for tool in curl gpgv tar mkfs.ext4 sha256sum sudo; do
	command -v "$tool" >/dev/null || die "$tool is not installed"
done
[ -f "$release_keyring" ] || die "Gentoo release keyring not found: $release_keyring"

mkdir -p "$lab/testvm" "$(dirname "$base")"
root=$(mktemp -d "$lab/testvm/root.XXXXXX") || die "cannot create the unpack directory"
pointer=
tarball_tmp=
checksum_tmp=
image_tmp="$base.tmp.$$"
metadata_tmp="$metadata.tmp.$$"
cleanup() {
	[ -n "$pointer" ] && rm -f "$pointer"
	[ -n "$tarball_tmp" ] && rm -f "$tarball_tmp"
	[ -n "$checksum_tmp" ] && rm -f "$checksum_tmp"
	rm -f "$image_tmp" "$metadata_tmp"
	sudo rm -rf "$root"
}
trap cleanup EXIT

step "stage3"
if [ "$snapshot" = latest ]; then
	pointer=$(mktemp "$lab/testvm/latest-stage3.XXXXXX") ||
		die "cannot create the stage3 pointer file"
	curl -fsS -o "$pointer" \
		"$mirror/releases/amd64/autobuilds/latest-stage3-amd64-$variant.txt" ||
		die "cannot fetch the stage3 pointer"
	# The pointer is PGP clearsigned, so pick the path out rather than the first line.
	relative=$(grep -oE "[0-9]{8}T[0-9]{6}Z/stage3-amd64-$variant-[^ ]+\\.tar\\.xz" "$pointer" | head -1)
	[ -n "$relative" ] || die "the stage3 pointer is empty"
	snapshot=${relative%%/*}
else
	relative="$snapshot/stage3-amd64-$variant-$snapshot.tar.xz"
fi
tarball="$lab/testvm/$(basename "$relative")"
stage3_url="$mirror/releases/amd64/autobuilds/$relative"
if [ ! -f "$tarball" ]; then
	tarball_tmp="$tarball.tmp.$$"
	curl -fL# -o "$tarball_tmp" "$stage3_url" ||
		die "cannot download the stage3"
	mv "$tarball_tmp" "$tarball" || die "cannot publish the stage3 tarball"
	tarball_tmp=
fi
checksum="$tarball.sha256"
if [ ! -f "$checksum" ]; then
	checksum_tmp="$checksum.tmp.$$"
	curl -fsS -o "$checksum_tmp" "$stage3_url.sha256" ||
		die "cannot download the stage3 checksum"
	mv "$checksum_tmp" "$checksum" || die "cannot publish the stage3 checksum"
	checksum_tmp=
fi
gpgv --keyring "$release_keyring" "$checksum" >/dev/null 2>&1 ||
	die "the stage3 checksum signature is invalid"
stage3_sha256=$(sed -n "s/^\([0-9a-f]\{64\}\)  $(basename "$tarball")$/\1/p" "$checksum" | head -1)
[ -n "$stage3_sha256" ] || die "the stage3 checksum is invalid"
printf '%s  %s\n' "$stage3_sha256" "$tarball" | sha256sum -c - >/dev/null ||
	die "the stage3 checksum does not match"

step "unpack"
sudo tar -xpf "$tarball" -C "$root" --xattrs-include='*.*' --numeric-owner ||
	die "cannot unpack the stage3"

systemd_version=none
openrc_version=none
shopt -s nullglob
if [ "$variant" = systemd ]; then
	init_dirs=("$root"/var/db/pkg/sys-apps/systemd-[0-9]*)
	init_package=systemd
else
	init_dirs=("$root"/var/db/pkg/sys-apps/openrc-[0-9]*)
	init_package=openrc
fi
shopt -u nullglob
[ ${#init_dirs[@]} -eq 1 ] || die "expected one $init_package package in the stage3"
init_pf=$(sudo sed -n '1p' "${init_dirs[0]}/PF") ||
	die "cannot read the $init_package version"
[[ $init_pf =~ ^$init_package-[0-9] ]] || die "invalid $init_package package: $init_pf"
if [ "$variant" = systemd ]; then
	systemd_version=${init_pf#systemd-}
else
	openrc_version=${init_pf#openrc-}
fi

step "configure"
# Root logs in on the serial port with no password: the test drives the machine
# over ttyS0 and nothing here is ever exposed off the host.
sudo sed -i 's|^root:[^:]*:|root::|' "$root/etc/shadow"
echo cjktty-test | sudo tee "$root/etc/hostname" >/dev/null
printf '/dev/vda / ext4 defaults,noatime 0 1\n' | sudo tee "$root/etc/fstab" >/dev/null
if [ "$variant" = systemd ]; then
	sudo ln -sf /usr/lib/systemd/system/serial-getty@.service \
		"$root/etc/systemd/system/getty.target.wants/serial-getty@ttyS0.service"
	sudo mkdir -p "$root/etc/systemd/system/serial-getty@ttyS0.service.d"
	printf '[Service]\nExecStart=\nExecStart=-/sbin/agetty -o "-p -- \\\\u" --autologin root --keep-baud 115200,57600,38400,9600 %%I $TERM\n' |
		sudo tee "$root/etc/systemd/system/serial-getty@ttyS0.service.d/autologin.conf" >/dev/null
	# The patch only has 8x16 and 16x32 glyphs, so use a supported size.
	printf 'FONT=LatArCyrHeb-16\nKEYMAP=us\n' | sudo tee "$root/etc/vconsole.conf" >/dev/null
else
	sudo sed -i '/^s0:/d; s|^consolefont=.*|consolefont="default8x16"|' \
		"$root/etc/inittab" "$root/etc/conf.d/consolefont"
	printf 's0:12345:respawn:/sbin/agetty --autologin root --noclear ttyS0 115200 vt100\n' |
		sudo tee -a "$root/etc/inittab" >/dev/null
	sudo ln -sf /etc/init.d/consolefont "$root/etc/runlevels/boot/consolefont"
fi
printf 'format\t1\nstage3_variant\t%s\nstage3_snapshot\t%s\nstage3_url\t%s\nstage3_sha256\t%s\ninit_system\t%s\nsystemd_version\t%s\nopenrc_version\t%s\nimage_size\t%s\n' \
	"$variant" "$snapshot" "$stage3_url" "$stage3_sha256" "$variant" \
	"$systemd_version" "$openrc_version" "$size" |
	sudo tee "$root/etc/cjktty-testvm" >/dev/null

step "image"
sudo mkfs.ext4 -q -F -L cjktty-test -d "$root" "$image_tmp" "$size" ||
	die "cannot build the image"
sudo chown "$(id -u):$(id -g)" "$image_tmp"
sudo cp "$root/etc/cjktty-testvm" "$metadata_tmp" || die "cannot copy image metadata"
sudo chown "$(id -u):$(id -g)" "$metadata_tmp"
mv "$metadata_tmp" "$metadata" || die "cannot publish image metadata"
mv "$image_tmp" "$base" || die "cannot publish the image"

echo
echo "base image: $base ($(du -h "$base" | cut -f1))"
echo "stage3 variant: $variant"
echo "stage3 snapshot: $snapshot"
echo "$init_package: ${init_pf#*-}"
echo "metadata: $metadata"
echo "now run: tools/test-system.sh --image $base <kernel-version>"

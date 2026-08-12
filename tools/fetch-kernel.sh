#!/bin/bash
# Print the path to a kernel tarball, downloading it once if needed.
#
# Release candidates are not published under pub/linux/kernel/v*/testing: that
# path 404s even while releases.json still advertises it. The only tarball for
# an -rc is the git snapshot, which is gzip rather than xz.
set -euo pipefail

die() { echo "$*" >&2; exit 1; }

print_path=false
if [ "${1:-}" = --print-path ]; then
	print_path=true
	shift
fi
[ $# -ge 1 ] || die "usage: $0 [--print-path] <kernel-version> [tarball-dir]"
version=$1
repo=$(cd "$(dirname "$0")/.." && pwd)
lab=${CJKTTY_LAB:-$(cd "$repo/.." && pwd)/lab}
tarballs=${2:-${CJKTTY_TARBALLS:-$lab/tarballs}}
series=${version%%.*}

case "$version" in
	*-rc*)
		url="https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/snapshot/linux-$version.tar.gz"
		tarball="$tarballs/linux-$version.tar.gz"
		verify=(gzip --test)
		;;
	*)
		url="https://cdn.kernel.org/pub/linux/kernel/v$series.x/linux-$version.tar.xz"
		tarball="$tarballs/linux-$version.tar.xz"
		verify=(xz --test)
		;;
esac

if $print_path; then
	echo "$tarball"
	exit 0
fi

if [ ! -f "$tarball" ]; then
	mkdir -p "$tarballs"
	download="$tarball.part.$$"
	trap 'rm -f "$download"' EXIT
	# --retry alone does not cover a connection the CDN resets mid-transfer,
	# which is how a 6.12.103 download failed once; --retry-all-errors does.
	curl --fail --location --retry 3 --retry-all-errors --retry-delay 2 \
		--silent --show-error \
		--output "$download" "$url" || die "cannot download $url"
	"${verify[@]}" "$download" || die "downloaded $(basename "$tarball") is corrupt"
	mv "$download" "$tarball"
	trap - EXIT
fi

echo "$tarball"

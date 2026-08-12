#!/bin/bash
# Check that cjktty patches apply to a named kernel version.
set -euo pipefail

repo=$(cd "$(dirname "$0")/.." && pwd)
lab=${CJKTTY_LAB:-$(cd "$repo/.." && pwd)/lab}
tarballs=${CJKTTY_TARBALLS:-$lab/tarballs}

die() { echo "$*" >&2; exit 1; }

[ $# -ge 1 ] || die "usage: $0 <kernel-version> [patch ...]"
command -v curl >/dev/null || die "curl is not installed"
command -v patch >/dev/null || die "patch is not installed"
command -v xz >/dev/null || die "xz is not installed"

version=$1
[[ "$version" =~ ^[0-9]+\.[0-9]+([.-][0-9A-Za-z]+)*$ ]] ||
	die "invalid kernel version: $version"
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

mkdir -p "$lab" "$tarballs"
work=$(mktemp -d "$lab/apply-patches.XXXXXX")
trap 'rm -rf "$work"' EXIT

tarball=$("$repo/tools/fetch-kernel.sh" "$version" "$tarballs") ||
	die "cannot fetch linux-$version"

tree="$work/linux-$version"
mkdir "$tree"
tar -xf "$tarball" -C "$tree" --strip-components=1 ||
	die "cannot unpack $tarball"

for patch_file in "${patch_files[@]}"; do
	display=$patch_file
	case "$display" in
		"$repo"/*) display=${display#"$repo"/} ;;
	esac
	patch -d "$tree" -p1 --fuzz=0 --dry-run --silent < "$patch_file" ||
		die "$display does not apply to linux-$version with fuzz=0"
	echo "$display: applies to linux-$version with fuzz=0"
done

echo "patch apply: PASS (${#patch_files[@]} patch file(s) against linux-$version)"

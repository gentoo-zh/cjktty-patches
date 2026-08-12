#!/bin/bash
# Port a cjktty patch to a new kernel and regenerate it.
#
# Usage: tools/port.sh <new-version> <base-patch>
#
#   tools/port.sh 6.19 v6.x/cjktty-6.18.patch
#
# Applies the base patch with fuzz allowed, leaves the tree and any .rej files
# for hand fixing, and prints what to do next. Run it again with --finish once
# the rejects are resolved to write the new patch.
set -uo pipefail

repo=$(cd "$(dirname "$0")/.." && pwd)
lab=${CJKTTY_LAB:-$(cd "$repo/.." && pwd)/lab}

die() { echo "$*" >&2; exit 1; }

finish=0
[ "${1:-}" = "--finish" ] && { finish=1; shift; }
[ $# -ge 1 ] || die "usage: $0 [--finish] <new-version> [base-patch]"

version=$1
series=${version%%.*}
minor=$(echo "$version" | cut -d. -f2)
base=${2:-}
pristine="$lab/linux-$version"
work="$lab/port-$version"
target="$repo/v$series.x/cjktty-$version.patch"

if [ "$finish" = 1 ]; then
	[ -d "$work" ] || die "no port in progress for $version"
	rejects=$(find "$work" -name '*.rej' | sort) || die "cannot scan $work for rejects"
	[ -z "$rejects" ] || die "unresolved rejects remain: ${rejects//$'\n'/ }"
	if [ -z "$base" ]; then
		base=$(cat "$work/.cjktty-base") || die "cannot read the base patch path"
	fi
	find "$work" -name '*.orig' -delete
	bash "$repo/tools/regen.sh" "$pristine" "$work" "$base" "$target" || die "regeneration failed"
	echo "wrote $target"
	echo "now run: tools/test-patch.sh $version"
	exit 0
fi

[ -n "$base" ] && [ -f "$base" ] || die "give the base patch to port from"
base=$(cd "$(dirname "$base")" && pwd)/$(basename "$base")

if [ ! -d "$pristine" ]; then
	tarball=$("$repo/tools/fetch-kernel.sh" "$version" "$lab") ||
		die "cannot fetch linux-$version"
	tar -xf "$tarball" -C "$lab" || die "cannot unpack $tarball"
fi

rm -rf "$work" || die "cannot clear port tree: $work"
cp -a "$pristine" "$work" || die "cannot copy the pristine kernel tree"
echo "$base" > "$work/.cjktty-base" || die "cannot record the base patch path"

patch_status=0
patch -d "$work" -p1 --forward < "$base" > "$lab/port-$version.log" 2>&1 ||
	patch_status=$?
[ $patch_status -le 1 ] || die "patch failed with status $patch_status; see $lab/port-$version.log"
rejects=$(find "$work" -name '*.rej' | sort) || die "cannot scan $work for rejects"
[ $patch_status -eq 0 ] || [ -n "$rejects" ] ||
	die "patch failed without producing rejects; see $lab/port-$version.log"

grep -E 'FAILED|Hunk #' "$lab/port-$version.log" | tail -20
echo
if [ -z "$rejects" ]; then
	echo "every hunk applied; run: $0 --finish $version"
else
	echo "rejects to fix by hand:"
	echo "$rejects" | sed 's/^/  /'
	echo
	echo "edit the files under $work, delete each .rej once resolved, then run:"
	echo "  $0 --finish $version"
fi

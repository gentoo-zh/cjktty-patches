#!/bin/bash
# Regenerate a cjktty patch from a patched tree.
#
# The file list is the union of `diff --git` and `--- a/` lines. Neither alone
# is enough: an empty new file such as lib/fonts/font_cjk_32x32.h carries no
# ---/+++ pair, and the older patches in this collection are plain diff output
# with a single `diff --git` line for the whole file.
#
# Usage: regen.sh <pristine-tree> <patched-tree> <source-patch> <output>
set -uo pipefail

die() { echo "regen.sh: $*" >&2; exit 1; }

[ $# -eq 4 ] || die "usage: $0 <pristine-tree> <patched-tree> <source-patch> <output>"
src=$1
work=$2
source_patch=$3
out=$4

[ -d "$src" ] || die "pristine tree does not exist: $src"
[ -d "$work" ] || die "patched tree does not exist: $work"
[ -f "$source_patch" ] || die "source patch does not exist: $source_patch"
[ ! -d "$out" ] || die "output is a directory: $out"
out_dir=$(dirname "$out")
[ -d "$out_dir" ] || die "output directory does not exist: $out_dir"

declare -a files=()
declare -A seen=() old_null=() new_null=()
current=
while IFS= read -r line; do
	case "$line" in
		"diff --git a/"*)
			current=${line#diff --git a/}
			current=${current%% b/*}
			;;
		"--- a/"*)
			current=${line#--- a/}
			current=${current%%$'\t'*}
			current=${current%% *}
			;;
		"--- /dev/null"*)
			[ -n "$current" ] && old_null["$current"]=1
			;;
		"+++ /dev/null"*)
			[ -n "$current" ] && new_null["$current"]=1
			;;
		"new file mode "*)
			[ -n "$current" ] && old_null["$current"]=1
			;;
		"deleted file mode "*)
			[ -n "$current" ] && new_null["$current"]=1
			;;
	esac
	if [ -n "$current" ] && [ -z "${seen[$current]:-}" ]; then
		case "/$current/" in
			*"/../"*) die "unsafe path in source patch: $current" ;;
		esac
		[[ "$current" != /* ]] || die "absolute path in source patch: $current"
		seen["$current"]=1
		files+=("$current")
	fi
done < "$source_patch"
[ ${#files[@]} -gt 0 ] || die "source patch contains no file headers"

tmp=$(mktemp "$out_dir/.regen.$(basename "$out").XXXXXX") ||
	die "cannot create temporary output in $out_dir"
segment=
cleanup() {
	rm -f "$tmp"
	[ -z "$segment" ] || rm -f "$segment"
}
trap cleanup EXIT

for f in "${files[@]}"; do
	old="$src/$f"
	new="$work/$f"
	if [ -n "${old_null[$f]:-}" ]; then
		[ ! -e "$old" ] || die "source marks $f as new, but it exists in the pristine tree"
		old=/dev/null
	else
		[ -f "$old" ] || die "pristine file does not exist: $old"
	fi
	if [ -n "${new_null[$f]:-}" ]; then
		[ ! -e "$new" ] || die "source marks $f as deleted, but it exists in the patched tree"
		new=/dev/null
	else
		[ -f "$new" ] || die "patched file does not exist: $new"
	fi
	[ "$old" != /dev/null ] || [ "$new" != /dev/null ] ||
		die "source marks $f as both new and deleted"

	if [ "$old" = /dev/null ] && [ ! -s "$new" ]; then
		printf 'diff --git a/%s b/%s\nnew file mode 100644\nindex 0000000..e69de29\n' \
			"$f" "$f" >> "$tmp" || die "cannot write output: $tmp"
		continue
	fi
	if [ "$new" = /dev/null ] && [ ! -s "$old" ]; then
		printf 'diff --git a/%s b/%s\ndeleted file mode 100644\nindex e69de29..0000000\n' \
			"$f" "$f" >> "$tmp" || die "cannot write output: $tmp"
		continue
	fi

	segment=$(mktemp "$out_dir/.regen.segment.XXXXXX") ||
		die "cannot create temporary diff in $out_dir"
	old_label="a/$f"
	new_label="b/$f"
	[ "$old" != /dev/null ] || old_label=/dev/null
	[ "$new" != /dev/null ] || new_label=/dev/null
	diff -up --label "$old_label" --label "$new_label" "$old" "$new" > "$segment"
	diff_status=$?
	if [ $diff_status -gt 1 ]; then
		die "diff failed for $f"
	fi
	if [ $diff_status -eq 1 ]; then
		# Every stanza needs its own git header, otherwise patch attaches file
		# metadata from the preceding stanza to this file.
		printf 'diff --git a/%s b/%s\n' "$f" "$f" >> "$tmp" ||
			die "cannot write output: $tmp"
		cat "$segment" >> "$tmp" || die "cannot write output: $tmp"
	fi
	rm -f "$segment"
	segment=
done

[ -s "$tmp" ] || die "the listed files contain no differences"
chmod 0644 "$tmp" || die "cannot set output permissions"
mv "$tmp" "$out" || die "cannot replace output: $out"
trap - EXIT

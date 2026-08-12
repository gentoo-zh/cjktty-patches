#!/bin/bash
set -euo pipefail

repo=$(cd "$(dirname "$0")/.." && pwd)
scratch_root=${CJKTTY_LAB:-${TMPDIR:-/tmp}}
mkdir -p "$scratch_root"
scratch=$(mktemp -d "$scratch_root/split-patch-test.XXXXXX")
trap 'rm -rf "$scratch"' EXIT

cat > "$scratch/source.patch" <<'EOF'
--- a/code.c
+++ b/code.c
@@ -1 +1 @@
-old
+new
diff --git a/lib/fonts/font_cjk_16x16.h b/lib/fonts/font_cjk_16x16.h
--- a/lib/fonts/font_cjk_16x16.h
+++ b/lib/fonts/font_cjk_16x16.h
@@ -0,0 +1 @@
+font data
diff --git a/lib/fonts/font_cjk_32x32.h b/lib/fonts/font_cjk_32x32.h
new file mode 100644
index 0000000..e69de29
EOF

cat > "$scratch/expected-font.patch" <<'EOF'
diff --git a/lib/fonts/font_cjk_16x16.h b/lib/fonts/font_cjk_16x16.h
--- a/lib/fonts/font_cjk_16x16.h
+++ b/lib/fonts/font_cjk_16x16.h
@@ -0,0 +1 @@
+font data
diff --git a/lib/fonts/font_cjk_32x32.h b/lib/fonts/font_cjk_32x32.h
new file mode 100644
index 0000000..e69de29
EOF

cat > "$scratch/expected-code.patch" <<'EOF'
--- a/code.c
+++ b/code.c
@@ -1 +1 @@
-old
+new
EOF

"$repo/tools/split-patch.py" "$scratch/source.patch" \
	"$scratch/font.patch" "$scratch/code.patch" >/dev/null
cmp "$scratch/expected-font.patch" "$scratch/font.patch"
cmp "$scratch/expected-code.patch" "$scratch/code.patch"

echo "split-patch: PASS (plain, git, and empty-file stanzas preserved)"

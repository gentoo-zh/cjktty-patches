#!/usr/bin/env python3
"""Count real kernel findings, ignoring the shell's echo of the grep command."""

from __future__ import annotations

import re
import sys
from pathlib import Path

raw = Path(sys.argv[1]).read_bytes().decode("utf-8", "replace")
clean = re.sub(r'\x1b\][0-9;]*;[^\x1b]*\x1b\\|\x1b\[[0-9;?]*[A-Za-z]|\r', '', raw)


class InvalidLog(Exception):
    pass


def between(a: str, b: str) -> list[str]:
    out: list[str] = []
    complete = False
    for seg in clean.split(a)[1:]:
        if b not in seg:
            continue
        complete = True
        for line in seg.split(b)[0].splitlines():
            if line.strip() and 'grep -E' not in line and not line.lstrip().startswith('echo '):
                out.append(line)
    if not complete:
        raise InvalidLog(f"missing complete {a}/{b} section")
    return out


try:
    bad_section = between("BADSTART", "BADEND")
    leak_section = between("LEAKSTART", "LEAKEND")
    if not any(line == "LEAKREAD=0" for line in leak_section):
        raise InvalidLog("kmemleak output has no successful read marker")
    if not any(line in ("BADREAD=0", "BADREAD=1") for line in bad_section):
        raise InvalidLog("kernel log output has no successful read marker")
except InvalidLog as error:
    print(f"stress verdict failed: {error}", file=sys.stderr)
    raise SystemExit(1)

bad = [l for l in bad_section
       if re.search(r'KASAN|BUG:|WARNING:|possible recursive locking|INFO: trying to register', l)]
leak = [l for l in leak_section if 'unreferenced object' in l]
for l in bad[:8] + leak[:8]:
    print("  ", l[:140])
print(f"dmesg findings {len(bad)}, kmemleak objects {len(leak)}")
sys.exit(1 if (bad or leak) else 0)

#!/usr/bin/env python3
"""Exercise CI matrix generation through its command-line entry point."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any


TOOLS = Path(__file__).resolve().parent
SCRIPT = TOOLS / "ci-matrix.py"
EMPTY = {
    "apply": {"include": []},
    "boot": {"include": []},
    "apply_count": 0,
    "boot_count": 0,
}
CASES = (
    (
        "changed 5.10 patch",
        ["v5.x/cjktty-5.10.264.patch"],
        {
            "apply": {
                "include": [
                    {
                        "name": "Apply Linux 5.10.264 combined patch",
                        "version": "5.10.264",
                        "patches": ["v5.x/cjktty-5.10.264.patch"],
                    }
                ]
            },
            "boot": {
                "include": [
                    {
                        "name": "Build and boot Linux 5.10.264 combined patch",
                        "version": "5.10.264",
                        "patches": ["v5.x/cjktty-5.10.264.patch"],
                        "cjk32": False, "script": "tools/test-patch.sh",
                    }
                ]
            },
            "apply_count": 1,
            "boot_count": 1,
        },
    ),
    (
        "changed patch serving a later point release",
        ["v6.x/cjktty-6.12.102.patch"],
        {
            "apply": {
                "include": [
                    {
                        "name": "Apply Linux 6.12.103 combined patch",
                        "version": "6.12.103",
                        "patches": ["v6.x/cjktty-6.12.102.patch"],
                    }
                ]
            },
            "boot": {
                "include": [
                    {
                        "name": "Build and boot Linux 6.12.103 combined patch",
                        "version": "6.12.103",
                        "patches": ["v6.x/cjktty-6.12.102.patch"],
                        "cjk32": False, "script": "tools/test-patch.sh",
                    }
                ]
            },
            "apply_count": 1,
            "boot_count": 1,
        },
    ),
    ("README only", ["README.md"], EMPTY),
    ("documentation only", ["docs/usage.md", "SUPPORTED.md", "LICENSE"], EMPTY),
    (
        "split code patch",
        ["v6.x/cjktty-code-6.12.102.patch"],
        {
            "apply": {
                "include": [
                    {
                        "name": "Apply Linux 6.12.103 split patches",
                        "version": "6.12.103",
                        "patches": [
                            "cjktty-font-unifont-15.1.04.patch",
                            "v6.x/cjktty-code-6.12.102.patch",
                        ],
                    }
                ]
            },
            "boot": {
                "include": [
                    {
                        "name": "Build and boot Linux 6.12.103 split patches",
                        "version": "6.12.103",
                        "patches": [
                            "cjktty-font-unifont-15.1.04.patch",
                            "v6.x/cjktty-code-6.12.102.patch",
                        ],
                        "cjk32": False, "script": "tools/test-patch.sh",
                    }
                ]
            },
            "apply_count": 1,
            "boot_count": 1,
        },
    ),
    (
        "CJK32 data patch",
        ["cjktty-add-cjk32x32-font-data.patch"],
        {
            "apply": {
                "include": [
                    {
                        "name": "Apply Linux 7.2-rc7 CJK32 patches",
                        "version": "7.2-rc7",
                        "patches": [
                            "v7.x/cjktty-7.2-rc7.patch",
                            "cjktty-add-cjk32x32-font-data.patch",
                        ],
                    }
                ]
            },
            "boot": {
                "include": [
                    {
                        "name": "Build and boot Linux 7.2-rc7 CJK32 patches",
                        "version": "7.2-rc7",
                        "patches": ["v7.x/cjktty-7.2-rc7.patch"],
                        "cjk32": True, "script": "tools/test-patch.sh",
                    }
                ]
            },
            "apply_count": 1,
            "boot_count": 1,
        },
    ),
    (
        "test tool",
        ["tools/test-patch.sh"],
        {
            "apply": {
                "include": [
                    {
                        "name": "Apply Linux 7.2-rc7 combined patch",
                        "version": "7.2-rc7",
                        "patches": ["v7.x/cjktty-7.2-rc7.patch"],
                    }
                ]
            },
            "boot": {
                "include": [
                    {
                        "name": "Build and boot Linux 7.2-rc7 combined patch",
                        "version": "7.2-rc7",
                        "patches": ["v7.x/cjktty-7.2-rc7.patch"],
                        "cjk32": False, "script": "tools/test-patch.sh",
                    }
                ]
            },
            "apply_count": 1,
            "boot_count": 1,
        },
    ),
    (
        "legacy patch",
        ["v3.x/cjktty-3.9.patch"],
        {
            "apply": {
                "include": [
                    {
                        "name": "Apply-only Linux 3.9 combined patch",
                        "version": "3.9",
                        "patches": ["v3.x/cjktty-3.9.patch"],
                    }
                ]
            },
            "boot": {"include": []},
            "apply_count": 1,
            "boot_count": 0,
        },
    ),
)


def run_matrix(paths: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), *paths],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return json.loads(result.stdout)


def run_all() -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), "--all"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return json.loads(result.stdout)


def font_patch_covers_every_split_form() -> bool:
    """The shared font patch serves every kernel that has a split code patch."""
    repo = Path(__file__).resolve().parent.parent
    expected = {
        path.name.replace("cjktty-code-", "").replace(".patch", "")
        for path in repo.glob("v[0-9]*.x/cjktty-code-*.patch")
    }
    matrix = run_matrix(["cjktty-font-unifont-15.1.04.patch"])
    produced = {job["patches"][1] for job in matrix["boot"]["include"]}
    produced = {
        Path(patch).name.replace("cjktty-code-", "").replace(".patch", "")
        for patch in produced
    }
    if produced != expected:
        print(f"FAIL: font patch covers {sorted(produced)}, repository has {sorted(expected)}")
        return False
    print(f"PASS: font patch produces a job for each of {len(expected)} split code patches")
    return True


def rejects_unmapped_patch() -> bool:
    result = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), "v5.x/not-a-cjktty-patch.patch"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return result.returncode == 2 and "changed patch does not exist" in result.stderr


def main() -> int:
    failures = 0
    for label, paths, expected in CASES:
        actual = run_matrix(paths)
        if actual == expected:
            print(f"PASS: {label}")
        else:
            print(f"FAIL: {label}")
            print(f"expected: {json.dumps(expected, sort_keys=True)}")
            print(f"actual:   {json.dumps(actual, sort_keys=True)}")
            failures += 1
    full = run_all()
    full_versions = [entry["version"] for entry in full["apply"]["include"]]
    expected_versions = [
        "7.2-rc7",
        "7.1.8",
        "6.18.44",
        "6.12.103",
        "6.6.151",
        "6.1.182",
        "5.15.215",
        "5.10.264",
    ]
    if (
        full_versions == expected_versions
        and full["apply_count"] == len(expected_versions)
        and full["boot_count"] == len(expected_versions)
    ):
        print("PASS: full maintained set")
    else:
        print("FAIL: full maintained set")
        failures += 1
    if font_patch_covers_every_split_form():
        pass
    else:
        failures += 1

    if rejects_unmapped_patch():
        print("PASS: reject unmapped patch")
    else:
        print("FAIL: reject unmapped patch")
        failures += 1
    total = len(CASES) + 3
    print(f"CI matrix: {total - failures} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""The 32x32 data patch must apply on every maintained split patch set."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parent.parent
DATA_PATCH = REPO / "cjktty-add-cjk32x32-font-data.patch"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "trees",
        nargs="*",
        type=Path,
        help="kernel trees named linux-<version> (default: every maintained tree in the lab)",
    )
    parser.add_argument(
        "--lab",
        type=Path,
        default=Path(os.environ.get("CJKTTY_LAB", REPO.parent / "lab")),
        help="directory containing linux-<version> trees",
    )
    return parser.parse_args()


def kernel_version(tree: Path) -> str | None:
    prefix = "linux-"
    return tree.name[len(prefix) :] if tree.name.startswith(prefix) else None


def apply_patch(tree: Path, patch_file: Path, *, dry_run: bool = False) -> str | None:
    command = ["patch", "-d", str(tree), "-p1", "--fuzz=0", "--batch", "--silent"]
    if dry_run:
        command.append("--dry-run")
    with patch_file.open("rb") as source:
        result = subprocess.run(
            command,
            stdin=source,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
    if result.returncode == 0:
        return None
    output = result.stdout.decode(errors="replace").strip()
    return output or f"patch exited {result.returncode}"


def check_tree(tree: Path, font_patch: Path, code_patch: Path) -> str | None:
    if not tree.is_dir():
        return f"kernel tree does not exist: {tree}"
    if not (tree / "Makefile").is_file():
        return f"not a kernel tree: {tree}"

    with tempfile.TemporaryDirectory(prefix=f"cjk32-{tree.name}.", dir=tree.parent) as scratch:
        work = Path(scratch) / tree.name
        shutil.copytree(tree, work, copy_function=os.link, symlinks=True)
        for base_patch in (font_patch, code_patch):
            failure = apply_patch(work, base_patch)
            if failure is not None:
                return f"{base_patch.relative_to(REPO)} rejects with --fuzz=0: {failure}"
        failure = apply_patch(work, DATA_PATCH, dry_run=True)
        if failure is not None:
            return f"{DATA_PATCH.name} rejects with --fuzz=0: {failure}"
    return None


def main() -> int:
    args = parse_args()
    sys.path.insert(0, str(REPO / "tools"))
    from patch_selection import version_key
    from support_data import read_verification, validated_split_forms

    records = read_verification(REPO / "tools" / "supported-verification.json")
    forms = validated_split_forms(REPO, records)
    if not forms:
        print("FAIL: verification data declares no maintained split patch sets")
        return 1

    failures = 0
    if args.trees:
        targets: list[tuple[str, Path]] = []
        for tree_arg in args.trees:
            tree = tree_arg.resolve()
            version = kernel_version(tree)
            if version is None:
                print(f"FAIL: kernel tree name must be linux-<version>: {tree}")
                failures += 1
                continue
            targets.append((version, tree))
    else:
        lab = args.lab.resolve()
        targets = [
            (version, lab / f"linux-{version}")
            for version in sorted(forms, key=version_key)
        ]

    checked = 0
    passed = 0
    for version, tree in targets:
        form = forms.get(version)
        if form is None:
            print(f"FAIL: Linux {version} has no maintained split patch set")
            failures += 1
            continue
        font_patch = REPO / form.font_patch
        code_patch = REPO / form.code_patch
        failure = check_tree(tree, font_patch, code_patch)
        checked += 1
        if failure is not None:
            print(f"FAIL: Linux {version}: {failure}")
            failures += 1
        else:
            passed += 1
            print(
                f"PASS: Linux {version}: {DATA_PATCH.name} applies after "
                f"{form.font_patch} and {form.code_patch} with --fuzz=0"
            )

    if checked == 0:
        print("FAIL: no kernel tree was tested")
        if failures == 0:
            failures += 1
    print(f"cjk32 patch application: {passed} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

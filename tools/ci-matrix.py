#!/usr/bin/env python3
"""Generate CI apply and boot matrices from changed repository paths."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from fnmatch import fnmatch
import json
from pathlib import Path, PurePosixPath
import re
import sys

from patch_selection import PATCH_RE, parse_version, select_patch, series_of, version_key
from support_data import (
    Verification,
    VerificationError,
    read_verification,
    validated_split_forms,
)


TOOLS = Path(__file__).resolve().parent
SERIES_DIR_RE = re.compile(r"^v(?P<major>[0-9]+)\.x$")
KIND_ORDER = {"combined": 0, "split": 1, "cjk32": 2, "loadable-font": 3}
# The loadable-font proof is written against 6.18 and its test hardcodes it.
LOADABLE_FONT_KERNEL = "6.18.44"


class MatrixError(RuntimeError):
    """Changed paths cannot be mapped to a meaningful CI job."""


@dataclass(frozen=True)
class Job:
    version: str
    kind: str
    apply_patches: tuple[str, ...]
    boot_patches: tuple[str, ...]
    cjk32: bool
    build: bool
    script: str = "tools/test-patch.sh"

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.version,
            self.kind,
            self.apply_patches,
            self.boot_patches,
            self.cjk32,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="changed repository paths")
    parser.add_argument(
        "--all",
        action="store_true",
        help="test every maintained kernel instead of changed paths",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=TOOLS.parent,
        help="patch repository root (default: parent of tools)",
    )
    parser.add_argument(
        "--verification-file",
        type=Path,
        default=TOOLS / "supported-verification.json",
        help="checked-in verification records",
    )
    args = parser.parse_args()
    if args.all and args.paths:
        parser.error("--all does not accept changed paths")
    return args


def normalize_path(path: str) -> str:
    normalized = PurePosixPath(path)
    if normalized.is_absolute() or ".." in normalized.parts:
        raise MatrixError(f"unsafe changed path: {path}")
    return normalized.as_posix()


def published_kernels(repo: Path) -> set[str]:
    """Read the kernel column of SUPPORTED.md.

    A series keeps its records after upstream ends it, so the records alone
    cannot say which series is still maintained; the published matrix can.
    """
    published: set[str] = set()
    for line in (repo / "SUPPORTED.md").read_text().splitlines():
        if not line.startswith("| ") or line.startswith("|---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 2 or cells[0].startswith("Kernel.org series"):
            continue
        published.add(cells[1])
    return published


def maintained_kernels(repo: Path, records: dict[str, list[Verification]]) -> list[str]:
    published = published_kernels(repo)
    newest: dict[str, str] = {}
    for kernel in records:
        if kernel not in published:
            continue
        series = series_of(kernel)
        previous = newest.get(series)
        if previous is None or version_key(kernel) > version_key(previous):
            newest[series] = kernel
    return sorted(newest.values(), key=version_key, reverse=True)


def selected_path(repo: Path, kernel: str) -> str:
    patch = select_patch(repo, kernel)
    if patch is None:
        raise MatrixError(f"no combined patch serves maintained kernel {kernel}")
    try:
        return patch.relative_to(repo).as_posix()
    except ValueError as error:
        raise MatrixError(f"selected patch is outside {repo}: {patch}") from error


def combined_version(path: str) -> str | None:
    parsed = PurePosixPath(path)
    if len(parsed.parts) != 2:
        return None
    directory = SERIES_DIR_RE.fullmatch(parsed.parts[0])
    patch = PATCH_RE.fullmatch(parsed.name)
    if directory is None or patch is None:
        return None
    version = patch.group("version")
    if parse_version(version).major != int(directory.group("major")):
        raise MatrixError(f"patch directory and filename disagree: {path}")
    return version


def documentation_path(path: str) -> bool:
    name = PurePosixPath(path).name
    return (
        fnmatch(name, "README*.md")
        or path == "SUPPORTED.md"
        or path == "LICENSE"
        or path.startswith("docs/")
    )


def add_job(jobs: dict[tuple[object, ...], Job], job: Job) -> None:
    previous = jobs.get(job.key)
    if previous is None or (job.build and not previous.build):
        jobs[job.key] = job


def combined_job(repo: Path, kernel: str, build: bool = True) -> Job:
    patch = selected_path(repo, kernel)
    return Job(kernel, "combined", (patch,), (patch,), False, build)


def split_job(kernel: str, font_patch: str, code_patch: str) -> Job:
    patches = (font_patch, code_patch)
    return Job(kernel, "split", patches, patches, False, True)


LOADABLE_FONT_PATHS = frozenset(
    {
        "tools/loadable-font-poc.patch",
        "tools/load-cjk-font.c",
        "tools/loadable-font-init.c",
        "tools/test-loadable-font.sh",
    }
)


def loadable_font_job(kernel: str) -> Job:
    """The proof carries its own patch, which no other job ever applies."""
    return Job(kernel, "loadable-font", (), (), False, True, "tools/test-loadable-font.sh")


def cjk32_job(repo: Path, kernel: str, data_patch: str) -> Job:
    combined = selected_path(repo, kernel)
    # test-patch.sh adds the data patch under --cjk32; passing it to the boot
    # job would apply the same patch twice.
    return Job(
        kernel,
        "cjk32",
        (combined, data_patch),
        (combined,),
        True,
        True,
    )


def job_name(job: Job, boot: bool) -> str:
    kind = {
        "combined": "combined patch",
        "split": "split patches",
        "cjk32": "CJK32 patches",
        "loadable-font": "loadable-font proof",
    }[job.kind]
    if boot:
        return f"Build and boot Linux {job.version} {kind}"
    prefix = "Apply" if job.build else "Apply-only"
    return f"{prefix} Linux {job.version} {kind}"


def serialize(jobs: dict[tuple[object, ...], Job]) -> dict[str, object]:
    # Stable sorting preserves kind order within each descending kernel version.
    ordered = sorted(jobs.values(), key=lambda job: KIND_ORDER[job.kind])
    ordered.sort(key=lambda job: version_key(job.version), reverse=True)
    apply = [
        {
            "name": job_name(job, False),
            "version": job.version,
            "patches": list(job.apply_patches),
        }
        for job in ordered
    ]
    boot = [
        {
            "name": job_name(job, True),
            "version": job.version,
            "patches": list(job.boot_patches),
            "cjk32": job.cjk32,
            "script": job.script,
        }
        for job in ordered
        if job.build
    ]
    return {
        "apply": {"include": apply},
        "boot": {"include": boot},
        "apply_count": len(apply),
        "boot_count": len(boot),
    }


def build_matrix(
    repo: Path,
    records: dict[str, list[Verification]],
    changed_paths: list[str],
    all_kernels: bool = False,
) -> dict[str, object]:
    current = maintained_kernels(repo, records)
    if not current:
        raise MatrixError("verification data has no maintained kernels")
    forms = validated_split_forms(repo, records)
    code_forms = {form.code_patch: form for form in forms.values()}

    jobs: dict[tuple[object, ...], Job] = {}
    if all_kernels:
        for kernel in current:
            add_job(jobs, combined_job(repo, kernel))
        return serialize(jobs)

    tool_change = False
    for original_path in changed_paths:
        path = normalize_path(original_path)
        if documentation_path(path):
            continue
        if path.endswith(".patch") and not (repo / path).is_file():
            raise MatrixError(f"changed patch does not exist: {path}")

        version = combined_version(path)
        if version is not None:
            matched = [kernel for kernel in current if selected_path(repo, kernel) == path]
            if matched:
                for kernel in matched:
                    add_job(jobs, Job(kernel, "combined", (path,), (path,), False, True))
            else:
                add_job(jobs, Job(version, "combined", (path,), (path,), False, False))
            continue

        if path in code_forms:
            form = code_forms[path]
            add_job(jobs, split_job(form.kernel, form.font_patch, path))
            continue
        if PurePosixPath(path).name.startswith("cjktty-code-") and path.endswith(".patch"):
            raise MatrixError(f"split code patch has no verification record: {path}")

        if fnmatch(path, "cjktty-font-unifont-*.patch"):
            for form in forms.values():
                add_job(jobs, split_job(form.kernel, path, form.code_patch))
            continue

        if path == "cjktty-add-cjk32x32-font-data.patch":
            add_job(jobs, cjk32_job(repo, current[0], path))
            continue

        if path in LOADABLE_FONT_PATHS:
            add_job(jobs, loadable_font_job(LOADABLE_FONT_KERNEL))
            continue

        if path.startswith("tools/") or path == ".github/workflows/ci.yml":
            tool_change = True
            continue

        if path.endswith(".patch"):
            raise MatrixError(f"changed patch cannot be mapped to CI: {path}")

        tool_change = True

    if tool_change:
        add_job(jobs, combined_job(repo, current[0]))
    return serialize(jobs)


def main() -> int:
    args = parse_args()
    repo = args.repo.resolve()
    records = read_verification(args.verification_file.resolve())
    matrix = build_matrix(repo, records, args.paths, args.all)
    print(json.dumps(matrix, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (MatrixError, OSError, VerificationError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)

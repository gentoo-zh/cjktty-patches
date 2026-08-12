#!/usr/bin/env python3
"""Read and validate checked-in kernel verification records."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
from datetime import date
import json
import re
from pathlib import Path, PurePosixPath

from patch_selection import VersionError, version_key


STAGES = frozenset(
    {
        "stage-1",
        "stage-2",
        "kasan",
        "kmemleak",
        "lockdep",
        "grub",
        "installkernel",
        "dracut-initramfs",
    }
)
STANDARD_STAGES = frozenset({"stage-1", "stage-2"})


class VerificationError(RuntimeError):
    """The verification data is incomplete or malformed."""


@dataclass(frozen=True)
class Verification:
    kernel: str
    stage: str
    verified: str
    digests: tuple[tuple[str, str], ...]
    note: str | None = None
    form: str = "combined"
    font_patch: str | None = None
    code_patch: str | None = None


@dataclass(frozen=True)
class SplitForm:
    kernel: str
    font_patch: str
    code_patch: str
    stages: frozenset[str]
    dates: frozenset[str]


def _digests(value: object, index: int) -> tuple[tuple[str, str], ...]:
    """A measurement describes the bytes that were measured, not a file name."""
    if not isinstance(value, dict) or not value:
        raise VerificationError(f"verification entry {index} has invalid digests")
    out: list[tuple[str, str]] = []
    for path, digest in sorted(value.items()):
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise VerificationError(f"verification entry {index} has invalid digest for {path}")
        out.append((_patch_path(path, "digests", index), digest))
    return tuple(out)


def _patch_path(value: object, field: str, index: int) -> str:
    if not isinstance(value, str):
        raise VerificationError(f"verification entry {index} has invalid {field}")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise VerificationError(f"verification entry {index} has unsafe {field}")
    return value


def read_verification(path: Path) -> dict[str, list[Verification]]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot read verification data {path}: {error}") from error
    if not isinstance(payload, list):
        raise VerificationError("verification data must be an array")

    records: dict[str, list[Verification]] = defaultdict(list)
    seen: set[tuple[str, str, str]] = set()
    split_paths: dict[str, tuple[str, str]] = {}
    for index, record in enumerate(payload, 1):
        if not isinstance(record, dict):
            raise VerificationError(f"verification entry {index} must be an object")
        form = record.get("form", "combined")
        fields = {"kernel", "stage", "date", "digests"}
        optional = {"note"}
        if form == "split":
            fields.update({"form", "font_patch", "code_patch"})
        elif form != "combined":
            raise VerificationError(f"verification entry {index} has unknown form {form}")
        if not fields <= set(record) or set(record) - fields - optional:
            raise VerificationError(f"verification entry {index} has invalid fields")

        kernel = record["kernel"]
        stage = record["stage"]
        verified = record["date"]
        if not all(isinstance(value, str) for value in (kernel, stage, verified)):
            raise VerificationError(f"verification entry {index} must contain strings")
        try:
            version_key(kernel)
            date.fromisoformat(verified)
        except (VersionError, ValueError) as error:
            raise VerificationError(f"verification entry {index}: {error}") from error
        if stage not in STAGES:
            raise VerificationError(f"verification entry {index} has unknown stage {stage}")
        if form == "split" and stage not in STANDARD_STAGES:
            raise VerificationError(f"verification entry {index} has invalid split stage {stage}")
        if (kernel, form, stage) in seen:
            raise VerificationError(f"duplicate verification for {kernel} {form} {stage}")
        seen.add((kernel, form, stage))

        font_patch = code_patch = None
        if form == "split":
            font_patch = _patch_path(record["font_patch"], "font_patch", index)
            code_patch = _patch_path(record["code_patch"], "code_patch", index)
            paths = (font_patch, code_patch)
            if kernel in split_paths and split_paths[kernel] != paths:
                raise VerificationError(f"split patch paths disagree for {kernel}")
            split_paths[kernel] = paths
        digests = _digests(record["digests"], index)
        if form == "split":
            assert font_patch is not None and code_patch is not None
            digest_paths = {path for path, _ in digests}
            expected_paths = {font_patch, code_patch}
            if digest_paths != expected_paths:
                raise VerificationError(
                    f"verification entry {index} split digest paths must be exactly "
                    f"{sorted(expected_paths)}, got {sorted(digest_paths)}"
                )
        records[kernel].append(
            Verification(
                kernel, stage, verified, digests, record.get("note"),
                form, font_patch, code_patch,
            )
        )

    for kernel, kernel_records in records.items():
        combined = {
            record.stage for record in kernel_records if record.form == "combined"
        }
        # A kernel that passed only stage 1 is a real state, and the table says so
        # rather than claiming a stage that was never measured.
        if "stage-1" not in combined:
            raise VerificationError(f"verification for {kernel} lacks stage-1")
    return dict(records)


def split_forms(records: dict[str, list[Verification]]) -> dict[str, SplitForm]:
    forms: dict[str, SplitForm] = {}
    for kernel, kernel_records in records.items():
        split = [record for record in kernel_records if record.form == "split"]
        if not split:
            continue
        font_patch = split[0].font_patch
        code_patch = split[0].code_patch
        if font_patch is None or code_patch is None:
            raise VerificationError(f"split patch paths are missing for {kernel}")
        forms[kernel] = SplitForm(
            kernel,
            font_patch,
            code_patch,
            frozenset(record.stage for record in split),
            frozenset(record.verified for record in split),
        )
    return forms


def validated_split_forms(
    repo: Path, records: dict[str, list[Verification]]
) -> dict[str, SplitForm]:
    forms = split_forms(records)
    recorded_code_patches = {form.code_patch for form in forms.values()}
    repository_code_patches = {
        path.relative_to(repo).as_posix()
        for path in repo.glob("v[0-9]*.x/cjktty-code-*.patch")
    }
    if recorded_code_patches != repository_code_patches:
        raise VerificationError("split code patches and verification data disagree")
    for form in forms.values():
        for patch in (form.font_patch, form.code_patch):
            if not (repo / patch).is_file():
                raise VerificationError(f"verified split patch does not exist: {patch}")
    return forms


def stale(
    records: dict[str, list[Verification]], repo: Path
) -> list[tuple[Verification, str]]:
    """Measurements whose patches no longer hold the bytes that were measured."""
    out: list[tuple[Verification, str]] = []
    for kernel_records in records.values():
        for record in kernel_records:
            for path, digest in record.digests:
                target = repo / path
                if not target.is_file():
                    out.append((record, f"{path} is missing"))
                    continue
                actual = hashlib.sha256(target.read_bytes()).hexdigest()
                if actual != digest:
                    out.append((record, f"{path} has changed since it was measured"))
    return out

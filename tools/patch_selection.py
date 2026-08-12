#!/usr/bin/env python3
"""Select the repository patch for a kernel version."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sys


VERSION_TEXT = r"[0-9]+\.[0-9]+(?:\.[0-9]+)?(?:-rc[0-9]+)?"
VERSION_RE = re.compile(
    r"^(?P<major>[0-9]+)\.(?P<minor>[0-9]+)"
    r"(?:\.(?P<point>[0-9]+))?(?:-rc(?P<rc>[0-9]+))?$"
)
PATCH_RE = re.compile(rf"^cjktty-(?P<version>{VERSION_TEXT})\.patch$")


class VersionError(ValueError):
    """A version cannot be ordered by the repository rule."""


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    point: int | None
    rc: int | None

    @property
    def series(self) -> str:
        return f"{self.major}.{self.minor}"

    @property
    def key(self) -> tuple[int, int, int, int, int]:
        # Separate ranks keep bare series patches below point releases and every
        # release candidate below the final release it precedes.
        return (
            self.major,
            self.minor,
            self.point + 1 if self.point is not None else 0,
            0 if self.rc is not None else 1,
            self.rc or 0,
        )


def parse_version(version: str) -> Version:
    match = VERSION_RE.fullmatch(version)
    if not match:
        raise VersionError(f"unsupported kernel version: {version}")
    point = match.group("point")
    rc = match.group("rc")
    return Version(
        major=int(match.group("major")),
        minor=int(match.group("minor")),
        point=int(point) if point is not None else None,
        rc=int(rc) if rc is not None else None,
    )


def version_key(version: str) -> tuple[int, int, int, int, int]:
    return parse_version(version).key


def series_of(version: str) -> str:
    return parse_version(version).series


def select_patch(repo: Path, kernel_version: str) -> Path | None:
    target = parse_version(kernel_version)
    candidates: list[tuple[tuple[int, int, int, int, int], Path]] = []
    series_patch: Path | None = None
    for path in (repo / f"v{target.major}.x").glob("cjktty-*.patch"):
        match = PATCH_RE.fullmatch(path.name)
        if not match or not path.is_file():
            continue
        version = parse_version(match.group("version"))
        if (version.major, version.minor) != (target.major, target.minor):
            continue
        if version.key <= target.key:
            candidates.append((version.key, path))
        if version.point is None and version.rc is None:
            series_patch = path
    if candidates:
        return max(candidates, key=lambda candidate: candidate[0])[1]
    # A series patch is also the baseline before that series reaches final release.
    if target.point is None and target.rc is not None:
        return series_patch
    return None


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <repository> <kernel-version>", file=sys.stderr)
        return 2
    try:
        patch = select_patch(Path(sys.argv[1]), sys.argv[2])
    except VersionError:
        return 1
    if patch is None:
        return 1
    print(patch)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

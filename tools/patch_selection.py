#!/usr/bin/env python3
"""Select the repository patches for a kernel version."""

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
CODE_PATCH_RE = re.compile(rf"^cjktty-code-(?P<version>{VERSION_TEXT})\.patch$")
FONT_PATCH_GLOB = "cjktty-font-unifont-*.patch"
# The combined form ended with 7.2. From 7.3 on a kernel is served by the shared
# font patch and its series' code patch, even where an older combined patch applies.
SPLIT_ONLY_FROM = "7.3"


class VersionError(ValueError):
    """A version cannot be ordered by the repository rule."""


class SelectionError(ValueError):
    """The repository does not hold exactly one shared font patch."""


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


def split_only(kernel_version: str) -> bool:
    return version_key(kernel_version) >= version_key(SPLIT_ONLY_FROM)


def newest_patch(repo: Path, kernel_version: str, pattern: re.Pattern[str]) -> Path | None:
    target = parse_version(kernel_version)
    candidates: list[tuple[tuple[int, int, int, int, int], Path]] = []
    series_patch: Path | None = None
    for path in (repo / f"v{target.major}.x").glob("cjktty-*.patch"):
        match = pattern.fullmatch(path.name)
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


def select_patch(repo: Path, kernel_version: str) -> Path | None:
    """The combined patch, which no kernel in a split-only series has."""
    if split_only(kernel_version):
        return None
    return newest_patch(repo, kernel_version, PATCH_RE)


def font_patch(repo: Path) -> Path:
    fonts = sorted(path for path in repo.glob(FONT_PATCH_GLOB) if path.is_file())
    if len(fonts) != 1:
        raise SelectionError(
            f"expected one {FONT_PATCH_GLOB} in {repo}, found {len(fonts)}"
        )
    return fonts[0]


def select_patches(repo: Path, kernel_version: str) -> tuple[Path, ...] | None:
    """The patches serving a kernel, in the order they are applied."""
    combined = select_patch(repo, kernel_version)
    if combined is not None:
        return (combined,)
    if not split_only(kernel_version):
        return None
    code = newest_patch(repo, kernel_version, CODE_PATCH_RE)
    if code is None:
        return None
    return (font_patch(repo), code)


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <repository> <kernel-version>", file=sys.stderr)
        return 2
    try:
        patches = select_patches(Path(sys.argv[1]), sys.argv[2])
    except VersionError:
        return 1
    except SelectionError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if patches is None:
        return 1
    for patch in patches:
        print(patch)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

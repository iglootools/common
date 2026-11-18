"""Whether built wheels carry the dynamic-versioning fallback version.

`[tool.uv-dynamic-versioning] fallback-version` turns "no git history" into a successful
build that produces 0.0.0 instead of an error. The fallback is required, because Renovate
runs `uv lock --upgrade-package`, which builds with no git context, so nothing else in the
publish path catches a mis-versioned artifact, and PyPI never lets a version number be
reused.

A build falls back when the source tree cannot see the git history or tags: a shallow CI
checkout without `fetch-tags`, a repository with no tags yet, an exported archive. Plain
`uv build` is not one of them: it builds the wheel from the sdist, but hatchling writes the
resolved version into the sdist's PKG-INFO and reads it back.
"""

import zipfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class VerifyVersionErrorKind(StrEnum):
    NO_METADATA = "no-metadata"
    NO_VERSION_FIELD = "no-version-field"


class VerifyVersionError(ValueError):
    def __init__(self, kind: VerifyVersionErrorKind, wheel: Path) -> None:
        super().__init__(f"{kind}: {wheel}")
        self.kind = kind
        self.wheel = wheel


@dataclass(frozen=True)
class WheelVersion:
    wheel: Path
    version: str


def metadata_version(wheel: Path) -> str:
    """The `Version:` field of the wheel's .dist-info/METADATA.

    Read from the metadata rather than the filename on purpose: a legitimate version such as
    1.0.0.dev0 contains "0.0.0" as a substring, so a filename match reports false positives.
    """
    with zipfile.ZipFile(wheel) as archive:
        metadata = next(
            (n for n in archive.namelist() if n.endswith(".dist-info/METADATA")), None
        )
        if metadata is None:
            raise VerifyVersionError(VerifyVersionErrorKind.NO_METADATA, wheel)
        lines = archive.read(metadata).decode("utf-8").splitlines()
    version = next(
        (
            line.removeprefix("Version: ")
            for line in lines
            if line.startswith("Version: ")
        ),
        None,
    )
    if version is None:
        raise VerifyVersionError(VerifyVersionErrorKind.NO_VERSION_FIELD, wheel)
    return version


def wheel_versions(dist_dir: Path) -> list[WheelVersion]:
    return [
        WheelVersion(wheel, metadata_version(wheel))
        for wheel in sorted(dist_dir.glob("*.whl"))
    ]

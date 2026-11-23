"""
A throwaway version for rehearsing a release on Test PyPI.

Test PyPI refuses a version it has seen, as PyPI does, so each rehearsal needs a new
one: the last release's version with a `.dev<UTC timestamp>` segment. It starts from the
base release in the tag, not the full VCS version, because appending to one that carries
`.post5.dev0` gives two dev segments, which PEP 440 forbids.
"""

import re
from datetime import datetime
from pathlib import Path

from iglootools.github.client import Run, capture

NO_RELEASE = "0.0.0"
"""The base version of a project that has no release tag yet."""

_RELEASE_TAG = re.compile(r"^v(?P<version>\d+(?:\.\d+)*)$")


def compute_dev_version(latest_tag: str | None, now: datetime) -> str:
    """
    Return `<base>.dev<YYYYMMDDHHMMSS>` from the latest release tag and the UTC time.

    The base is the tag without its `v`, or 0.0.0 when there is no tag or the tag is not
    a plain release version.
    """
    match _RELEASE_TAG.match(latest_tag or ""):
        case None:
            base = NO_RELEASE
        case found:
            base = found["version"]
    return f"{base}.dev{now:%Y%m%d%H%M%S}"


def latest_release_tag(root: Path, *, run: Run = capture) -> str | None:
    """Return the nearest `v<digit>…` tag reachable from HEAD at *root*, or None."""
    result = run(
        ["git", "describe", "--tags", "--abbrev=0", "--match", "v[0-9]*"],
        root,
    )
    return result.stdout.strip() if result.returncode == 0 else None

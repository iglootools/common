"""Where a project pins iglootools/common, and how to move every pin to a release.

A project pins common in four ways, each matched below: a reusable workflow by commit SHA
with the tag in a trailing comment, the `iglootools` command by tag (`git+…@vX.Y.Z`, as a
dev dependency or through uvx), a Renovate preset by tag, and IGLOOTOOLS_VERSION in
mise.toml for the projects that run the command through uvx.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from iglootools.github.client import GitHub, GitHubError, GitHubErrorKind, Repository

COMMON = Repository("iglootools", "common")
VERSION = re.compile(r"^\d+\.\d+\.\d+$")

_TAG = r"v\d+\.\d+\.\d+"
_WORKFLOW = re.compile(
    rf"(uses:\s*iglootools/common/\.github/workflows/[\w.-]+\.ya?ml@)[0-9a-f]{{40}}"
    rf"(\s*#\s*){_TAG}"
)
_GIT_URL = re.compile(rf"(git\+https://github\.com/iglootools/common(?:\.git)?@){_TAG}")
_PRESET = re.compile(rf"(github>iglootools/common//renovate/[\w-]+#){_TAG}")
_ENV = re.compile(rf'^(\s*IGLOOTOOLS_VERSION\s*=\s*"){_TAG}(")', re.MULTILINE)

PINNED_FILES = (
    "pyproject.toml",
    "mise.toml",
    "renovate.json",
    ".github/renovate.json",
)
"""Files that may pin common, besides the workflows under .github/workflows/."""


@dataclass(frozen=True)
class Rewrite:
    text: str
    changed: int


def rewrite(text: str, version: str, sha: str) -> Rewrite:
    """*text* with every pin on common moved to *version* (tags) and *sha* (workflows)."""
    tag = f"v{version}"
    substitutions = [
        (_WORKFLOW, rf"\g<1>{sha}\g<2>{tag}"),
        (_GIT_URL, rf"\g<1>{tag}"),
        (_PRESET, rf"\g<1>{tag}"),
        (_ENV, rf"\g<1>{tag}\g<2>"),
    ]
    changed = 0
    for pattern, replacement in substitutions:
        text, count = pattern.subn(replacement, text)
        changed += count
    return Rewrite(text, changed)


def candidate_files(root: Path) -> list[Path]:
    """The files under *root* that may pin common."""
    workflows = sorted((root / ".github" / "workflows").glob("*.y*ml"))
    return [
        path
        for path in workflows + [root / name for name in PINNED_FILES]
        if path.is_file()
    ]


def tag_commit(github: GitHub, version: str) -> str:
    """The commit common's `v<version>` tag points at, through an annotated tag."""
    try:
        ref = github.get(f"/repos/{COMMON.slug}/git/ref/tags/v{version}")["object"]
    except GitHubError as error:
        if error.status != 404:
            raise
        raise GitHubError(
            GitHubErrorKind.REQUEST_FAILED,
            f"{COMMON.slug} has no release v{version}",
            404,
        ) from None
    if ref["type"] == "tag":
        ref = github.get(f"/repos/{COMMON.slug}/git/tags/{ref['sha']}")["object"]
    return str(ref["sha"])

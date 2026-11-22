"""
Where a project pins iglootools/common, and how to move every pin to a release.

A project pins common in four ways, each matched below: a reusable workflow by commit
SHA with the tag in a trailing comment, the `iglootools` command by tag (`git+…@vX.Y.Z`,
as a dev dependency or through uvx), a Renovate preset by tag, and IGLOOTOOLS_VERSION in
mise.toml for the projects that run the command through uvx.
"""

import re
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path

from iglootools.github.client import GitHub, GitHubError, GitHubErrorKind, Repository

COMMON = Repository("iglootools", "common")
VERSION = re.compile(r"^\d+\.\d+\.\d+$")

_TAG = r"v\d+\.\d+\.\d+"
_WORKFLOW = re.compile(
    rf"(uses:\s*iglootools/common/\.github/workflows/[\w.-]+\.ya?ml@)[0-9a-f]{{40}}"
    rf"(\s*#\s*){_TAG}",
)
_GIT_URL = re.compile(rf"(git\+https://github\.com/iglootools/common(?:\.git)?@){_TAG}")
_PRESET = re.compile(rf"(github>iglootools/common//renovate/[\w-]+#){_TAG}")
_ENV = re.compile(rf'(IGLOOTOOLS_VERSION\s*=\s*"){_TAG}(")')

_REFERENCE = re.compile(
    r"iglootools/common(?:\.git)?(?:/[\w./-]*)?[@#](?P<ref>v\d+\.\d+\.\d+\b|[0-9a-f]{40}\b)",
)
"""Any pin on common, spelled any way: broader than the rewrite on purpose, so a pin the
rewrite does not recognise is found rather than silently left behind."""
_ENV_REFERENCE = re.compile(r'IGLOOTOOLS_VERSION\s*=\s*"(?P<ref>v\d+\.\d+\.\d+)"')
_TAG_COMMENT = re.compile(r"#\s*v(?P<version>\d+\.\d+\.\d+)\b")
_LOCKED = re.compile(
    r"iglootools/common\?rev=v(?P<version>\d+\.\d+\.\d+)#(?P<sha>[0-9a-f]{40})",
)
SKIPPED = ("uv.lock", "mise.lock", ".mise/locks/")
"""Lock files, which their own tools regenerate rather than adopt rewriting them."""

type Run = Callable[[Sequence[str], Path], subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class Rewrite:
    """A file's text with its pins moved, and how many pins moved."""

    text: str
    changed: int


def rewrite(text: str, version: str, sha: str) -> Rewrite:
    """Move every pin on common in *text* to *version* (tags) and *sha* (workflows)."""
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


def capture(
    command: Sequence[str],
    directory: Path,
) -> subprocess.CompletedProcess[str]:
    """Run *command* in *directory*, capturing its text output, whatever its status."""
    return subprocess.run(
        command,
        cwd=directory,
        capture_output=True,
        text=True,
        check=False,
    )


def candidate_files(root: Path, *, run: Run = capture) -> list[Path]:
    """
    Every file git tracks under *root* that mentions common, lock files aside.

    No list of file names: a pin in a file nobody thought to list is still found.
    """
    names = run(["git", "ls-files", "-z"], root).stdout.split("\0")
    return [
        root / name
        for name in names
        if name and not name.startswith(SKIPPED) and _mentions_common(root / name)
    ]


def _mentions_common(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError, OSError:
        return False
    return "iglootools/common" in text or "IGLOOTOOLS_VERSION" in text


@dataclass(frozen=True)
class Reference:
    """One pin on common: where it is, the release it names, and its commit if a SHA."""

    path: Path
    line: int
    version: str | None
    sha: str | None
    movable: bool
    """Whether adopt's rewrite would move it."""


def references(path: Path, text: str) -> list[Reference]:
    """Every pin on common in *text*, found by the broad patterns."""
    found: list[Reference] = []
    for number, line in enumerate(text.splitlines(), start=1):
        refs = [m["ref"] for m in _REFERENCE.finditer(line)] + [
            m["ref"] for m in _ENV_REFERENCE.finditer(line)
        ]
        movable = rewrite(line, "0.0.0", "0" * 40).changed >= len(refs)
        for ref in refs:
            if ref.startswith("v"):
                found.append(Reference(path, number, ref[1:], None, movable))
            else:
                comment = _TAG_COMMENT.search(line)
                version = comment["version"] if comment else None
                found.append(Reference(path, number, version, ref, movable))
    return found


@dataclass(frozen=True)
class Locked:
    """The release and commit uv.lock resolved the iglootools command to."""

    version: str
    sha: str


def locked(uv_lock: str) -> Locked | None:
    """Return what uv.lock resolved the iglootools command to, or None if not there."""
    match _LOCKED.search(uv_lock):
        case None:
            return None
        case found:
            return Locked(found["version"], found["sha"])


def problems(found: Sequence[Reference], lock: Locked | None, root: Path) -> list[str]:
    """List what is wrong with the pins: one a rewrite misses, or two that disagree."""

    def where(reference: Reference) -> str:
        return f"{reference.path.relative_to(root)}:{reference.line}"

    issues = [
        f"{where(r)}: adopt would not move this pin; teach pins.rewrite its spelling"
        for r in found
        if not r.movable
    ] + [
        f"{where(r)}: pinned by SHA with no `# vX.Y.Z` comment naming its release"
        for r in found
        if r.sha and not r.version
    ]
    versions = sorted(
        {r.version for r in found if r.version} | ({lock.version} if lock else set()),
    )
    if len(versions) > 1:
        issues.append(f"the pins name different releases: {', '.join(versions)}")
        issues += [f"  {where(r)}: v{r.version}" for r in found if r.version]
        if lock:
            issues.append(f"  uv.lock: v{lock.version}")
    if lock:
        issues += [
            f"{where(r)}: {r.sha[:12]} is not v{lock.version}'s commit "
            f"{lock.sha[:12]}, which uv.lock records"
            for r in found
            if r.sha and r.sha != lock.sha
        ]
    return issues


def scan(root: Path, *, run: Run = capture) -> tuple[list[Reference], Locked | None]:
    """Every pin on common in the project at *root*, and what uv.lock resolved."""
    found = [
        reference
        for path in candidate_files(root, run=run)
        for reference in references(path, path.read_text(encoding="utf-8"))
    ]
    uv_lock = root / "uv.lock"
    return found, locked(
        uv_lock.read_text(encoding="utf-8"),
    ) if uv_lock.is_file() else None


def tag_commit(github: GitHub, version: str) -> str:
    """
    Return the commit common's `v<version>` tag points at, through an annotated tag.

    Raises GitHubError, with status 404, when common has no such release.
    """
    try:
        ref = github.get(f"/repos/{COMMON.slug}/git/ref/tags/v{version}")["object"]
    except GitHubError as error:
        if error.status != HTTPStatus.NOT_FOUND:
            raise
        raise GitHubError(
            GitHubErrorKind.REQUEST_FAILED,
            f"{COMMON.slug} has no release v{version}",
            HTTPStatus.NOT_FOUND,
        ) from None
    if ref["type"] == "tag":
        ref = github.get(f"/repos/{COMMON.slug}/git/tags/{ref['sha']}")["object"]
    return str(ref["sha"])

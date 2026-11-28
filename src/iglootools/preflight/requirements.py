"""
Every program and credential an iglootools command depends on, declared once.

Each subsystem checks its own subset before its first change, so a missing tool fails a
command cleanly, with how to fix it, instead of half way: a release whose version bump
has merged but whose tags could not be made. `iglootools preflight` checks them all.
"""

import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

type Which = Callable[[str], str | None]
"""Finds a program on PATH, as shutil.which does."""

type Run = Callable[[Sequence[str], Path], subprocess.CompletedProcess[str]]

TOKEN_VARIABLES = ("GH_TOKEN", "GITHUB_TOKEN")


class Kind(StrEnum):
    """How a requirement is checked: a program on PATH, or a GitHub token."""

    PROGRAM = "program"
    GITHUB_TOKEN = "github-token"  # noqa: S105 - a requirement kind, not a secret


@dataclass(frozen=True)
class Requirement:
    """A program or credential a command needs: what it is for and how to get it."""

    name: str
    purpose: str
    fix: str
    kind: Kind = Kind.PROGRAM


GIT = Requirement(
    "git",
    "creates branches, commits and pushes",
    "install git: https://git-scm.com/downloads",
)
MISE = Requirement(
    "mise",
    "runs the project's tasks, and uv to regenerate uv.lock",
    "install mise: https://mise.jdx.dev/installing-mise.html",
)
CLAUDE = Requirement(
    "claude",
    "validates and tags a release of the plugin, and updates it after an adopt",
    "install Claude Code: https://docs.claude.com/en/docs/claude-code/setup",
)
GITHUB_TOKEN = Requirement(
    "GitHub token",
    "calls GitHub's API as you",
    "set GH_TOKEN, or install gh and run `gh auth login`",
    Kind.GITHUB_TOKEN,
)

GITHUB = (GIT, GITHUB_TOKEN)
"""What every `iglootools github` command needs."""
COMMON = (GIT, GITHUB_TOKEN, MISE, CLAUDE)
"""What adopting or releasing iglootools/common needs."""
BUILD = (MISE,)
"""What `iglootools repo run` needs."""

SUBSYSTEMS = {
    "github": GITHUB,
    "common": COMMON,
    "repo adopt-common": COMMON,
    "workspace": GITHUB,
    "workspace adopt-common": COMMON,
    "repo run": BUILD,
}
ALL = tuple(
    dict.fromkeys(
        requirement for group in SUBSYSTEMS.values() for requirement in group
    ),
)


def needed_by(requirement: Requirement) -> list[str]:
    """List the subsystems whose commands need *requirement*."""
    return [name for name, group in SUBSYSTEMS.items() if requirement in group]


@dataclass(frozen=True)
class Result:
    """Whether a requirement is met, and where it was found or why it was not."""

    requirement: Requirement
    ok: bool
    detail: str


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


def check(
    requirements: Sequence[Requirement],
    root: Path,
    *,
    environ: Mapping[str, str],
    which: Which = shutil.which,
    run: Run = capture,
) -> list[Result]:
    """Whether each of *requirements* is met, and where it was found."""
    return [
        _check(requirement, root, environ, which, run) for requirement in requirements
    ]


def _check(
    requirement: Requirement,
    root: Path,
    environ: Mapping[str, str],
    which: Which,
    run: Run,
) -> Result:
    match requirement.kind:
        case Kind.PROGRAM:
            found = which(requirement.name)
            return Result(
                requirement,
                ok=found is not None,
                detail=found or "not on PATH",
            )
        case Kind.GITHUB_TOKEN:
            return _token(requirement, root, environ, which, run)


def _token(
    requirement: Requirement,
    root: Path,
    environ: Mapping[str, str],
    which: Which,
    run: Run,
) -> Result:
    for variable in TOKEN_VARIABLES:
        if environ.get(variable):
            return Result(requirement, ok=True, detail=f"from {variable}")
    if which("gh") is None:
        return Result(
            requirement,
            ok=False,
            detail="no GH_TOKEN or GITHUB_TOKEN, and no gh",
        )
    result = run(["gh", "auth", "token"], root)
    if result.returncode != 0 or not result.stdout.strip():
        return Result(requirement, ok=False, detail="gh is not logged in")
    return Result(requirement, ok=True, detail="from gh")

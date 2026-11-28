"""
Clone every repository of the organization that the workspace lacks, and fetch the rest.

Archived repositories are left out: they take no change. A checkout is
`<workspace>/<repository name>`, and one whose origin is another repository, or a
directory there that is not a checkout, is reported rather than touched.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from iglootools.github.client import GitHubError, Run, capture, origin_repository
from iglootools.workspace.repositories import OrganizationRepository


class CloneProtocol(StrEnum):
    """How a missing repository is cloned."""

    SSH = "ssh"
    HTTPS = "https"


def infer_protocol(origins: Sequence[str]) -> CloneProtocol:
    """
    Clone the way the checkouts already there were cloned.

    HTTPS only when there is at least one and every one uses it, so the credentials
    that work for them work for the new ones; SSH otherwise.
    """
    https = bool(origins) and all(url.startswith("https://") for url in origins)
    return CloneProtocol.HTTPS if https else CloneProtocol.SSH


class CloneAction(StrEnum):
    """What clone did to a repository, or would do in a dry run."""

    CLONED = "cloned"
    FETCHED = "fetched"
    PRESENT = "present"
    FAILED = "failed"


@dataclass(frozen=True)
class CloneResult:
    """What clone did to one repository, and why it failed, if it did."""

    name: str
    action: CloneAction
    problem: str = ""


def checkout_path(workspace: Path, repository: OrganizationRepository) -> Path:
    """Return where *repository* is checked out in *workspace*."""
    return workspace / repository.name


def is_checkout(path: Path) -> bool:
    """Tell whether *path* is a git checkout: its own, or a worktree's `.git` file."""
    return (path / ".git").exists()


def existing_origins(
    workspace: Path,
    repositories: Sequence[OrganizationRepository],
    *,
    run: Run = capture,
) -> list[str]:
    """Return the origin URL of each of *repositories* already checked out."""
    paths = [checkout_path(workspace, found) for found in repositories]
    results = [
        run(["git", "remote", "get-url", "origin"], path)
        for path in paths
        if is_checkout(path)
    ]
    return [result.stdout.strip() for result in results if result.returncode == 0]


def clone_one(
    workspace: Path,
    repository: OrganizationRepository,
    protocol: CloneProtocol,
    *,
    fetch: bool,
    dry_run: bool,
    run: Run = capture,
) -> CloneResult:
    """
    Clone *repository* into *workspace* if it is missing, else fetch it if *fetch*.

    A dry run checks what is there and reports what it would do, running nothing that
    changes the workspace.
    """
    path = checkout_path(workspace, repository)
    if not path.exists():
        return _clone(workspace, repository, protocol, dry_run=dry_run, run=run)
    if not is_checkout(path):
        return CloneResult(
            repository.name,
            CloneAction.FAILED,
            f"{path} exists but is not a git checkout",
        )
    mismatch = _origin_mismatch(path, repository, run=run)
    if mismatch:
        return CloneResult(repository.name, CloneAction.FAILED, mismatch)
    if not fetch:
        return CloneResult(repository.name, CloneAction.PRESENT)
    if dry_run:
        return CloneResult(repository.name, CloneAction.FETCHED)
    result = run(["git", "fetch", "-q", "--prune", "origin"], path)
    if result.returncode != 0:
        return CloneResult(
            repository.name,
            CloneAction.FAILED,
            f"git fetch failed: {result.stderr.strip()}",
        )
    return CloneResult(repository.name, CloneAction.FETCHED)


def _clone(
    workspace: Path,
    repository: OrganizationRepository,
    protocol: CloneProtocol,
    *,
    dry_run: bool,
    run: Run,
) -> CloneResult:
    url = (
        repository.https_url if protocol == CloneProtocol.HTTPS else repository.ssh_url
    )
    if dry_run:
        return CloneResult(repository.name, CloneAction.CLONED)
    result = run(["git", "clone", "-q", url, repository.name], workspace)
    if result.returncode != 0:
        return CloneResult(
            repository.name,
            CloneAction.FAILED,
            f"git clone {url} failed: {result.stderr.strip()}",
        )
    return CloneResult(repository.name, CloneAction.CLONED)


def _origin_mismatch(
    path: Path,
    repository: OrganizationRepository,
    *,
    run: Run,
) -> str:
    """Return why *path*'s origin is not *repository*, or "" when it is."""
    try:
        origin = origin_repository(path, run=run)
    except GitHubError as error:
        return f"its origin is not a GitHub repository: {error.detail}"
    if origin != repository.repository:
        return f"its origin is {origin.slug}, not {repository.repository.slug}"
    return ""

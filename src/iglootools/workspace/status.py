"""
Read where every checkout of the workspace stands, changing nothing but fetched refs.

One row per repository: the branch it is on, its uncommitted changes, how its default
branch stands against origin's, its other local branches and worktrees, and its open
pull requests, Renovate's counted apart.
"""

from dataclasses import dataclass, field, replace
from pathlib import Path

from iglootools.github import local
from iglootools.github.client import GitHub, GitHubError, Run, capture
from iglootools.github.local import GitStepError
from iglootools.workspace import clone
from iglootools.workspace.repositories import OrganizationRepository
from iglootools.workspace.sync import other_worktrees

RENOVATE = "renovate[bot]"


@dataclass(frozen=True)
class RepositoryStatus:
    """
    Where one repository stands; *problem* says what could not be read, if anything.

    *branch* is empty for a detached HEAD; *ahead* and *behind* count the default
    branch's commits against origin's.
    """

    name: str
    cloned: bool
    branch: str = ""
    changes: int = 0
    ahead: int = 0
    behind: int = 0
    branches: list[str] = field(default_factory=list[str])
    worktrees: int = 0
    open_pulls: int = 0
    renovate_pulls: int = 0
    problem: str = ""


def read_status(
    path: Path,
    repository: OrganizationRepository,
    github: GitHub,
    *,
    fetch: bool,
    run: Run = capture,
) -> RepositoryStatus:
    """
    Read where *repository*'s checkout at *path* stands, fetching first when *fetch*.

    A repository that is not cloned still reports its open pull requests. Each failure
    is the problem of the status, never an exception.
    """
    cloned = clone.is_checkout(path)
    try:
        authors = [
            pull["user"]["login"]
            for pull in github.get_all(
                f"/repos/{repository.repository.slug}/pulls?state=open",
            )
        ]
    except GitHubError as error:
        return RepositoryStatus(repository.name, cloned=cloned, problem=error.detail)
    empty = RepositoryStatus(
        repository.name,
        cloned=cloned,
        open_pulls=len(authors),
        renovate_pulls=authors.count(RENOVATE),
    )
    if not cloned:
        return empty
    fetched = clone.fetch_origin(path, run=run) if fetch else ""
    try:
        return _checkout_status(path, repository, empty, fetched, run=run)
    except GitStepError as error:
        return replace(empty, problem=str(error))


def _checkout_status(
    path: Path,
    repository: OrganizationRepository,
    empty: RepositoryStatus,
    problem: str,
    *,
    run: Run,
) -> RepositoryStatus:
    base = repository.default_branch
    counts = local.git(
        path,
        "rev-list",
        "--left-right",
        "--count",
        f"refs/heads/{base}...refs/remotes/origin/{base}",
        run=run,
    ).split()
    return replace(
        empty,
        branch=local.git(path, "branch", "--show-current", run=run).strip(),
        changes=len(local.git(path, "status", "--porcelain", run=run).splitlines()),
        ahead=int(counts[0]),
        behind=int(counts[1]),
        branches=[b for b in local.local_branches(path, run=run) if b != base],
        worktrees=len(other_worktrees(path, run=run)),
        problem=problem,
    )

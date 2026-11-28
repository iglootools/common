"""
Delete the branches whose pull request has merged, on GitHub and locally.

A branch is deleted only when its latest pull request is merged and the default branch
holds every commit it has: one pushed to again after the merge, as Renovate does when it
reuses a branch name, carries work nobody merged. Everything else is kept, each for a
reason the plan states: the default branch, a protected branch, a
branch with an open pull request, one whose latest pull request was closed without
merging (it may hold work nobody merged), and one with no pull request at all, such as
`gh-pages`.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from urllib.parse import quote

from iglootools.github.client import GitHub, GitHubError, Repository, Run, capture


class PullState(StrEnum):
    """The state of a branch's latest pull request, NONE when it has none."""

    NONE = "none"
    OPEN = "open"
    MERGED = "merged"
    CLOSED = "closed"


@dataclass(frozen=True)
class Branch:
    """A branch on GitHub or in the checkout, and its latest pull request."""

    name: str
    on_remote: bool
    local: bool
    protected: bool
    pull: PullState
    pull_number: int | None = None
    ahead: int = 0
    """Commits the branch on GitHub has that the default branch lacks; 0 if unknown."""

    @property
    def where(self) -> str:
        """Say where the branch is: locally, on GitHub, or both."""
        return " and ".join(
            [
                *(["local"] if self.local else []),
                *(["GitHub"] if self.on_remote else []),
            ],
        )


@dataclass(frozen=True)
class Decision:
    """Whether prune deletes a branch, and why."""

    branch: Branch
    delete: bool
    reason: str


def decide(branch: Branch, default_branch: str) -> Decision:
    """Decide whether to delete *branch*, and why."""
    match branch:
        case Branch(name=name) if name == default_branch:
            return Decision(branch, delete=False, reason="default branch")
        case Branch(protected=True):
            return Decision(branch, delete=False, reason="protected")
        case Branch(pull=PullState.MERGED, pull_number=number, ahead=ahead) if ahead:
            return Decision(
                branch,
                delete=False,
                reason=f"{ahead} commit(s) pushed after #{number} merged",
            )
        case Branch(pull=PullState.MERGED, pull_number=number):
            return Decision(branch, delete=True, reason=f"#{number} merged")
        case Branch(pull=PullState.OPEN, pull_number=number):
            return Decision(branch, delete=False, reason=f"#{number} open")
        case Branch(pull=PullState.CLOSED, pull_number=number):
            return Decision(
                branch,
                delete=False,
                reason=f"#{number} closed without merging",
            )
        case _:
            return Decision(branch, delete=False, reason="no pull request")


def plan(branches: Sequence[Branch], default_branch: str) -> list[Decision]:
    """Decide for each of *branches*, sorted by name."""
    return [decide(branch, default_branch) for branch in sorted(branches, key=_name)]


def _name(branch: Branch) -> str:
    return branch.name


def latest_pull(
    github: GitHub,
    repository: Repository,
    branch: str,
) -> tuple[PullState, int | None]:
    """Return the state of the most recent pull request whose head is *branch*."""
    pulls = github.get(
        f"/repos/{repository.slug}/pulls?state=all&head={repository.owner}:{branch}"
        "&sort=created&direction=desc&per_page=1",
    )
    if not pulls:
        return PullState.NONE, None
    latest = pulls[0]
    if latest.get("merged_at"):
        return PullState.MERGED, latest["number"]
    state = PullState.OPEN if latest["state"] == "open" else PullState.CLOSED
    return state, latest["number"]


def gather(
    github: GitHub,
    repository: Repository,
    local_branches: Sequence[str],
) -> tuple[str, list[Branch]]:
    """
    Return the default branch, and every other branch on GitHub or in the checkout.

    Each branch comes with its latest pull request's state.
    """
    default_branch = github.get(f"/repos/{repository.slug}")["default_branch"]
    remote = {
        item["name"]: bool(item.get("protected"))
        for item in github.get_all(f"/repos/{repository.slug}/branches")
    }
    names = sorted(set(remote) | set(local_branches))
    return default_branch, [
        Branch(
            name=name,
            on_remote=name in remote,
            local=name in local_branches,
            protected=remote.get(name, False),
            pull=state,
            pull_number=number,
            ahead=ahead_of(github, repository, default_branch, name)
            if state == PullState.MERGED and name in remote
            else 0,
        )
        for name in names
        if name != default_branch
        for state, number in [latest_pull(github, repository, name)]
    ]


def ahead_of(
    github: GitHub,
    repository: Repository,
    default_branch: str,
    branch: str,
) -> int:
    """Return how many commits *branch* on GitHub has that *default_branch* lacks."""
    compared = github.get(
        f"/repos/{repository.slug}/compare/"
        f"{quote(default_branch, safe='/')}...{quote(branch, safe='/')}",
    )
    return int(compared["ahead_by"])


def delete_remote(github: GitHub, repository: Repository, branch: str) -> None:
    """Delete *branch* on GitHub; one already gone is not an error."""
    try:
        github.request("DELETE", f"/repos/{repository.slug}/git/refs/heads/{branch}")
    except GitHubError as error:
        if error.status not in (404, 422):
            raise


@dataclass(frozen=True)
class Pruned:
    """What deleting one merged branch did, or would do, and what kept part of it."""

    done: list[str]
    problems: list[str]


def delete_merged(
    github: GitHub,
    repository: Repository,
    decision: Decision,
    root: Path | None,
    *,
    current: str,
    dry_run: bool,
    run: Run = capture,
) -> Pruned:
    """
    Delete the branch *decision* chose, on GitHub and in the checkout at *root*.

    *root* is None when there is no checkout of *repository* to clean. The branch the
    checkout is on (*current*) is kept, and so is a local one `git branch -d` refuses,
    holding commits the default branch lacks: each is a problem of the result. A dry run
    changes nothing and says what it would do. Raises GitHubError when GitHub refuses.
    """
    branch = decision.branch
    verb = "would delete" if dry_run else "deleted"
    if branch.on_remote and not dry_run:
        delete_remote(github, repository, branch.name)
    remote = (
        [f"{verb} {branch.name} on GitHub ({decision.reason})"]
        if branch.on_remote
        else []
    )
    locally = f"{verb} the local {branch.name} ({decision.reason})"
    if root is None or not branch.local:
        return Pruned(remote, [])
    if branch.name == current:
        return Pruned(remote, [f"kept the local {branch.name}: it is checked out"])
    if dry_run:
        return Pruned([*remote, locally], [])
    result = run(["git", "branch", "-q", "-d", branch.name], root)
    if result.returncode != 0:
        return Pruned(
            remote,
            [f"kept the local {branch.name}: {result.stderr.strip()}"],
        )
    return Pruned([*remote, locally], [])

"""Delete the branches whose pull request has merged, on GitHub and locally.

A branch is deleted only when its latest pull request is merged. Everything else is kept,
each for a reason the plan states: the default branch, a protected branch, a branch with an
open pull request, one whose latest pull request was closed without merging (it may hold
work nobody merged), and one with no pull request at all, such as `gh-pages`.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from iglootools.github.client import GitHub, GitHubError, Repository


class PullState(StrEnum):
    NONE = "none"
    OPEN = "open"
    MERGED = "merged"
    CLOSED = "closed"


@dataclass(frozen=True)
class Branch:
    name: str
    on_remote: bool
    local: bool
    protected: bool
    pull: PullState
    pull_number: int | None = None


@dataclass(frozen=True)
class Decision:
    branch: Branch
    delete: bool
    reason: str


def decide(branch: Branch, default_branch: str) -> Decision:
    """Whether to delete *branch*, and why."""
    match branch:
        case Branch(name=name) if name == default_branch:
            return Decision(branch, False, "default branch")
        case Branch(protected=True):
            return Decision(branch, False, "protected")
        case Branch(pull=PullState.MERGED, pull_number=number):
            return Decision(branch, True, f"#{number} merged")
        case Branch(pull=PullState.OPEN, pull_number=number):
            return Decision(branch, False, f"#{number} open")
        case Branch(pull=PullState.CLOSED, pull_number=number):
            return Decision(branch, False, f"#{number} closed without merging")
        case _:
            return Decision(branch, False, "no pull request")


def plan(branches: Sequence[Branch], default_branch: str) -> list[Decision]:
    return [decide(branch, default_branch) for branch in sorted(branches, key=_name)]


def _name(branch: Branch) -> str:
    return branch.name


def latest_pull(
    github: GitHub, repository: Repository, branch: str
) -> tuple[PullState, int | None]:
    """The state of the most recent pull request whose head is *branch*."""
    pulls = github.get(
        f"/repos/{repository.slug}/pulls?state=all&head={repository.owner}:{branch}"
        "&sort=created&direction=desc&per_page=1"
    )
    if not pulls:
        return PullState.NONE, None
    latest = pulls[0]
    if latest.get("merged_at"):
        return PullState.MERGED, latest["number"]
    state = PullState.OPEN if latest["state"] == "open" else PullState.CLOSED
    return state, latest["number"]


def gather(
    github: GitHub, repository: Repository, local_branches: Sequence[str]
) -> tuple[str, list[Branch]]:
    """The default branch, and every branch on GitHub or in the checkout, with its state."""
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
        )
        for name in names
        if name != default_branch
        for state, number in [latest_pull(github, repository, name)]
    ]


def delete_remote(github: GitHub, repository: Repository, branch: str) -> None:
    try:
        github.request("DELETE", f"/repos/{repository.slug}/git/refs/heads/{branch}")
    except GitHubError as error:
        if error.status not in (404, 422):
            raise

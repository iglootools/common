"""
The open Renovate pull requests across the organization, and merging the green ones.

What a pull request needs next is merge-when-green's own verdict, read once without
waiting; merging goes through merge-when-green itself, so both agree with `iglootools
github merge-when-green` on every rule: required checks, merge commits, the branch
deleted after.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from iglootools.github import merge
from iglootools.github.client import GitHub, GitHubError
from iglootools.github.events import Report
from iglootools.workspace.repositories import OrganizationRepository

RENOVATE = "renovate[bot]"
"""The login Renovate's pull requests are opened by."""


@dataclass(frozen=True)
class RenovatePull:
    """
    An open Renovate pull request, and what merge-when-green would do with it next.

    *verdict* is None when it could not be assessed, and *problem* then says why.
    """

    repository: OrganizationRepository
    number: int
    title: str
    verdict: merge.Verdict | None = None
    problem: str = ""

    @property
    def mergeable(self) -> bool:
        """Tell whether merge-when-green would merge it, now or once checks pass."""
        return self.verdict is not None and self.verdict.action in (
            merge.Action.MERGE,
            merge.Action.WAIT,
        )


def find_pulls(
    github: GitHub,
    repository: OrganizationRepository,
) -> list[RenovatePull]:
    """
    List *repository*'s open Renovate pull requests, each with its verdict.

    Raises GitHubError when the pull requests cannot be listed; one that cannot be
    assessed carries its problem instead.
    """
    pulls = github.get_all(f"/repos/{repository.repository.slug}/pulls?state=open")
    return [
        _assessed(github, repository, pull["number"], pull["title"])
        for pull in pulls
        if pull["user"]["login"] == RENOVATE
    ]


def _assessed(
    github: GitHub,
    repository: OrganizationRepository,
    number: int,
    title: str,
) -> RenovatePull:
    try:
        verdict = merge.preview(github, repository.repository, number).verdict
    except GitHubError as error:
        return RenovatePull(repository, number, title, problem=error.detail)
    return RenovatePull(repository, number, title, verdict)


def merge_all(
    github: GitHub,
    pulls: Sequence[RenovatePull],
    *,
    sleep: Callable[[float], None],
    now: Callable[[], float],
    report: Callable[[RenovatePull], Report],
) -> list[tuple[RenovatePull, merge.Outcome | str]]:
    """
    Merge each of *pulls* once its checks pass, one after the other.

    Pass the pull requests of one repository: merging one can leave the next behind
    its base. Returns each one's outcome, or why merge-when-green could not run.
    """
    return [(pull, _merge(github, pull, sleep, now, report(pull))) for pull in pulls]


def _merge(
    github: GitHub,
    pull: RenovatePull,
    sleep: Callable[[float], None],
    now: Callable[[], float],
    report: Report,
) -> merge.Outcome | str:
    try:
        return merge.merge_when_green(
            github,
            pull.repository.repository,
            pull.number,
            sleep=sleep,
            now=now,
            report=report,
        )
    except GitHubError as error:
        return error.detail

"""
Move every iglootools project in the workspace to a release of common, in parallel.

The workspace is the directory the projects are checked out in, as
iglootools.workspace.location resolves it. Every project is checked before any is
changed, so a problem in one stops the run while nothing has happened yet.
Then each project runs `adopt`, which is safe to run again, in a thread of its own and a
temporary worktree, so the project's checkout is left to whoever works there: the work
is almost all waiting on CI and GitHub, so threads cost nothing. Pushes take turns,
so a credential prompt can never collide with another. Interrupting the run stops every
project at its next poll, and running it again picks up where each one stopped.

No project depends on another today, so they run in any order; docs/internals.md says
what would change if one did.
"""

import threading
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from iglootools.common import adopt, pins
from iglootools.github import local
from iglootools.github.client import (
    GitHub,
    GitHubError,
    Repository,
    Run,
    capture,
    origin_repository,
)
from iglootools.github.events import Event, Report
from iglootools.workspace import parallel

ORGANIZATION = "iglootools"


@dataclass(frozen=True)
class Project:
    """A checked-out iglootools project: its directory name, root and repository."""

    name: str
    root: Path
    repository: Repository


@dataclass(frozen=True)
class Skipped:
    """A directory or project left out of the run, and why."""

    name: str
    reason: str


def discover(
    workspace: Path,
    *,
    run: Run = capture,
) -> tuple[list[Project], list[Skipped]]:
    """
    Find the iglootools projects checked out in *workspace* that pin common.

    Also return the directories passed over, with why.
    """
    projects: list[Project] = []
    skipped: list[Skipped] = []
    for directory in sorted(
        path for path in workspace.iterdir() if (path / ".git").exists()
    ):
        try:
            repository = origin_repository(directory, run=run)
        except GitHubError:
            skipped.append(Skipped(directory.name, "origin is not a GitHub repository"))
            continue
        if repository == pins.COMMON:
            continue
        if repository.owner != ORGANIZATION:
            skipped.append(Skipped(directory.name, f"belongs to {repository.owner}"))
            continue
        found, _ = pins.scan(directory, run=run)
        if not found:
            skipped.append(Skipped(directory.name, "pins nothing on common"))
            continue
        projects.append(Project(directory.name, directory, repository))
    return projects, skipped


class SelectionError(ValueError):
    """--only or --exclude named projects the workspace does not have."""

    def __init__(self, unknown: Sequence[str]) -> None:
        """Build the error from the project names the workspace lacks."""
        super().__init__(f"no such project in the workspace: {', '.join(unknown)}")
        self.unknown = tuple(unknown)


def select(
    projects: Sequence[Project],
    only: Sequence[str],
    exclude: Sequence[str],
) -> tuple[list[Project], list[Skipped]]:
    """
    Narrow *projects* by --only and --exclude; also return the ones left out.

    Raises SelectionError when either names a project not in *projects*.
    """
    names = {project.name for project in projects}
    unknown = sorted((set(only) | set(exclude)) - names)
    if unknown:
        raise SelectionError(unknown)
    selected = [
        p for p in projects if (not only or p.name in only) and p.name not in exclude
    ]
    left_out = [
        Skipped(p.name, "excluded" if p.name in exclude else "not in --only")
        for p in projects
        if p not in selected
    ]
    return selected, left_out


def missing_checkouts(
    github: GitHub,
    checked_out: set[str],
    excluded: set[str],
) -> list[str]:
    """
    List the organization's repositories that pin common but have no checkout here.

    Searches renovate.json files, since every project that adopts common extends its
    Renovate presets; the search indexes each repository's default branch.
    """
    query = quote(f'"iglootools/common" org:{ORGANIZATION} filename:renovate.json')
    found = github.get(f"/search/code?q={query}&per_page=100")
    names = {item["repository"]["name"] for item in found.get("items", [])}
    return sorted(names - checked_out - excluded - {pins.COMMON.name})


def problems(project: Project, *, run: Run = capture) -> list[str]:
    """
    List what stops *project* from being adopted, without changing it.

    The checkout's own branch and changes do not matter: adopt works in a worktree
    started from GitHub's default branch. Only reaching origin does.
    """
    reach = run(["git", "ls-remote", "-q", "origin", "HEAD"], project.root)
    if reach.returncode == 0:
        return []
    first = (reach.stderr.strip().splitlines() or ["no reason given"])[0]
    return [
        (
            f"cannot reach origin without a prompt ({first}); load your key with "
            "`ssh-add`, or log in to git over HTTPS"
        ),
    ]


def describe(error: BaseException, detail: str) -> str:
    """
    Return *detail* followed by the notes added to *error*, one sentence each.

    A note says, for instance, where a failed adopt kept its worktree.
    """
    return " ".join([detail, *getattr(error, "__notes__", [])])


type Adopt = Callable[
    [Project, Report, Callable[[float], None], AbstractContextManager[object]],
    adopt.Outcome,
]
"""Adopts one project, reporting events, sleeping through the given function, and
pushing inside the given guard."""


def run_all(
    projects: Sequence[Project],
    adopt_one: Adopt,
    *,
    report: Callable[[str, Event], None],
    stop: threading.Event,
) -> dict[str, adopt.Outcome]:
    """
    Adopt every project at once, and return each one's outcome.

    A failure in one project does not stop the others. Setting *stop*, which an
    interrupted run does, ends every project at its next sleep.
    """
    push_guard = threading.Lock()

    def work(project: Project, sleep: parallel.Sleep) -> adopt.Outcome:
        try:
            return adopt_one(
                project,
                lambda event: report(project.name, event),
                sleep,
                push_guard,
            )
        except parallel.CancelledError as error:
            return adopt.Outcome(
                adopt.Result.REFUSED,
                describe(error, "interrupted; run again to resume"),
            )
        except (GitHubError, local.GitStepError) as error:
            return adopt.Outcome(
                adopt.Result.REFUSED,
                describe(error, getattr(error, "detail", str(error))),
            )

    outcomes = parallel.each_interruptible(projects, work, stop=stop)
    return {
        project.name: outcome
        for project, outcome in zip(projects, outcomes, strict=True)
    }

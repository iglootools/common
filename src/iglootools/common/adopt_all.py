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

from iglootools.common import adopt, pins
from iglootools.github import contents, local
from iglootools.github.client import (
    GitHub,
    GitHubError,
    Repository,
    Run,
    capture,
)
from iglootools.github.events import Event, Report
from iglootools.workspace import clone, parallel
from iglootools.workspace.repositories import ORGANIZATION, OrganizationRepository


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


@dataclass(frozen=True)
class Discovery:
    """
    What the workspace holds of the organization.

    The projects that pin common, the repositories passed over with why, and the ones
    with no checkout there, whose pins are read on GitHub instead.
    """

    projects: list[Project]
    skipped: list[Skipped]
    not_checked_out: list[OrganizationRepository]


def discover(
    workspace: Path,
    repositories: Sequence[OrganizationRepository],
    *,
    run: Run = capture,
) -> Discovery:
    """
    Sort the organization's *repositories*, common aside, by what the workspace holds.

    Each is looked for where `workspace clone` puts it, `<workspace>/<name>`. An
    archived one is passed over, as is a checkout whose origin is another repository.
    """
    found = [
        (repository, _classify(workspace, repository, run=run))
        for repository in repositories
        if repository.name != pins.COMMON.name
    ]
    return Discovery(
        projects=[kind for _, kind in found if isinstance(kind, Project)],
        skipped=[kind for _, kind in found if isinstance(kind, Skipped)],
        not_checked_out=[repository for repository, kind in found if kind is None],
    )


def _classify(
    workspace: Path,
    repository: OrganizationRepository,
    *,
    run: Run,
) -> Project | Skipped | None:
    """Return the project, why it is passed over, or None when it is not checked out."""
    path = clone.checkout_path(workspace, repository)
    if repository.archived:
        return Skipped(repository.name, "archived")
    if not clone.is_checkout(path):
        return None
    mismatch = clone.origin_mismatch(path, repository, run=run)
    if mismatch:
        return Skipped(repository.name, mismatch)
    pinned, _ = pins.scan(path, run=run)
    if not pinned:
        return Skipped(repository.name, "pins nothing on common")
    return Project(repository.name, path, repository.repository)


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


RENOVATE_CONFIG = "renovate.json"


@dataclass(frozen=True)
class Unchecked:
    """The organization's repositories with no checkout here, sorted by what to do."""

    missing: list[str]
    """Those that pin common, which the run cannot leave out."""
    passed_over: list[Skipped]
    """Those that do not, with why."""


def find_unchecked(
    github: GitHub,
    repositories: Sequence[OrganizationRepository],
) -> Unchecked:
    """
    Sort *repositories*, which have no checkout here, by whether they pin common.

    A repository pins common when the renovate.json on its default branch extends a
    preset from common, as every project that adopts common does. Raises GitHubError
    when GitHub cannot be asked.
    """
    pinning = {
        repository.name: extends_common(_renovate_config(github, repository.name))
        for repository in repositories
    }
    return Unchecked(
        missing=[name for name, pins_common in pinning.items() if pins_common],
        passed_over=[
            Skipped(
                name,
                f"not checked out, and its {RENOVATE_CONFIG} does not extend "
                f"{pins.COMMON.slug}",
            )
            for name, pins_common in pinning.items()
            if not pins_common
        ],
    )


def extends_common(config: str | None) -> bool:
    """Tell whether a Renovate config, None when there is none, names common."""
    return config is not None and pins.COMMON.slug in config


def _renovate_config(github: GitHub, name: str) -> str | None:
    """Return the renovate.json on *name*'s default branch, None when it has none."""
    return contents.read_text(github, Repository(ORGANIZATION, name), RENOVATE_CONFIG)


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

"""Move every iglootools project in the workspace to a release of common, in parallel.

The workspace is the directory common's checkout sits in. Every project is checked before
any is changed, so a problem in one stops the run while nothing has happened yet. Then each
project runs `adopt`, which is safe to run again, in a thread of its own: the work is
almost all waiting on CI and GitHub, so threads cost nothing. Pushes take turns, so a
credential prompt can never collide with another. Interrupting the run stops every project
at its next poll, and running it again picks up where each one stopped.

No project depends on another today, so they run in any order; docs/internals.md says what
would change if one did.
"""

import threading
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
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

ORGANIZATION = "iglootools"


@dataclass(frozen=True)
class Project:
    name: str
    root: Path
    repository: Repository


@dataclass(frozen=True)
class Skipped:
    name: str
    reason: str


def discover(
    workspace: Path, *, run: Run = capture
) -> tuple[list[Project], list[Skipped]]:
    """The iglootools projects checked out in *workspace* that pin common, and the
    directories passed over, with why."""
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
    """--only or --exclude named a project the workspace does not have."""


def select(
    projects: Sequence[Project], only: Sequence[str], exclude: Sequence[str]
) -> tuple[list[Project], list[Skipped]]:
    """*projects* narrowed by --only and --exclude, and the ones they left out."""
    names = {project.name for project in projects}
    unknown = sorted((set(only) | set(exclude)) - names)
    if unknown:
        raise SelectionError(f"no such project in the workspace: {', '.join(unknown)}")
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
    github: GitHub, checked_out: set[str], excluded: set[str]
) -> list[str]:
    """Repositories of the organization that pin common but have no checkout here.

    Searches renovate.json files, since every project that adopts common extends its
    Renovate presets; the search indexes each repository's default branch.
    """
    query = quote(f'"iglootools/common" org:{ORGANIZATION} filename:renovate.json')
    found = github.get(f"/search/code?q={query}&per_page=100")
    names = {item["repository"]["name"] for item in found.get("items", [])}
    return sorted(names - checked_out - excluded - {pins.COMMON.name})


def problems(project: Project, base: str, *, run: Run = capture) -> list[str]:
    """What stops *project* from being adopted safely, found without changing it."""
    issues: list[str] = []
    try:
        local.require_clean(project.root, run=run)
    except local.GitStepError:
        issues.append("has changes or untracked files; commit, stash or remove them")
    reach = run(["git", "ls-remote", "-q", "origin", "HEAD"], project.root)
    if reach.returncode != 0:
        first = (reach.stderr.strip().splitlines() or ["no reason given"])[0]
        issues.append(
            f"cannot reach origin without a prompt ({first}); load your key with "
            "`ssh-add`, or log in to git over HTTPS"
        )
        return issues
    run(["git", "fetch", "-q", "origin", base], project.root)
    ahead = run(
        ["git", "rev-list", "--count", f"origin/{base}..{base}"], project.root
    ).stdout.strip()
    if ahead not in ("", "0"):
        issues.append(f"its local {base} has {ahead} commit(s) GitHub lacks")
    return issues


class Cancelled(Exception):
    """The run was interrupted; the project stops at its next poll."""


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
    """Adopt every project at once, and return each one's outcome.

    A failure in one project does not stop the others. Setting *stop*, which an
    interrupted run does, ends every project at its next sleep.
    """
    push_guard = threading.Lock()

    def sleep(seconds: float) -> None:
        if stop.wait(seconds):
            raise Cancelled

    def work(project: Project) -> adopt.Outcome:
        try:
            return adopt_one(
                project, lambda event: report(project.name, event), sleep, push_guard
            )
        except Cancelled:
            return adopt.Outcome(
                adopt.Result.REFUSED, "interrupted; run again to resume"
            )
        except (GitHubError, local.GitStepError) as error:
            return adopt.Outcome(
                adopt.Result.REFUSED, getattr(error, "detail", str(error))
            )

    outcomes: dict[str, adopt.Outcome] = {}
    with ThreadPoolExecutor(max_workers=max(len(projects), 1)) as pool:
        futures = {pool.submit(work, project): project for project in projects}
        try:
            for future in as_completed(futures):
                outcomes[futures[future].name] = future.result()
        except KeyboardInterrupt:
            stop.set()
            for future, project in futures.items():
                outcomes[project.name] = future.result()
    return outcomes

"""The `iglootools common` commands: adopt a release, adopt it everywhere, cut one."""

import threading
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.live import Live
from rich.table import Table

from iglootools.cliwiring import ensure, invocation, say, warn
from iglootools.common import adopt as adoption
from iglootools.common import adopt_all as everywhere
from iglootools.common import pins
from iglootools.common import release as releasing
from iglootools.github import pulls
from iglootools.github.cli import REPO_OPTION, github_session
from iglootools.github.client import GitHub, GitHubError
from iglootools.github.events import Event, Report
from iglootools.github.local import GitStepError
from iglootools.preflight import requirements

app = typer.Typer(
    help="Maintain a project's link to iglootools/common.",
    no_args_is_help=True,
)

VERSION_ARGUMENT = typer.Argument(help="The release, as X.Y.Z.")


def _version(version: str) -> str:
    if not pins.VERSION.match(version):
        warn(f"Give the version as X.Y.Z, not {version!r}.")
        raise typer.Exit(2)
    return version


@app.command("adopt")
def adopt(
    ctx: typer.Context,
    version: Annotated[str, VERSION_ARGUMENT],
    repo: Annotated[str | None, REPO_OPTION] = None,
    *,
    no_merge: Annotated[
        bool,
        typer.Option("--no-merge", help="Open the pull request, do not merge it."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Show the pins that would move."),
    ] = False,
) -> None:
    """
    Move every pin on iglootools/common to a release, through a pull request.

    Moves the reusable workflows (to the release's commit), the iglootools command, the
    Renovate presets and IGLOOTOOLS_VERSION, and regenerates uv.lock where there is one.
    Then opens a pull request and merges it once every check has passed, as
    merge-when-green does. Safe to run again: it picks up from the pull request or
    branch an earlier run left, and does nothing once the release is in place. Needs a
    checkout with no changes and no untracked files.
    """
    ensure(ctx, requirements.COMMON)
    version = _version(version)
    root = invocation(ctx).root
    repository, github = github_session(ctx, repo)
    try:
        sha = pins.tag_commit(github, version)
        if dry_run:
            found = adoption.plan(root, version, sha)
            for line in adoption.preview(
                root,
                github,
                repository,
                found,
                merge_it=not no_merge,
            ):
                say(f"[dry-run] {line}")
            return
        outcome = adoption.adopt(
            root,
            github,
            repository,
            version,
            sha,
            merge_it=not no_merge,
            report=lambda event: say(event.detail),
            sleep=time.sleep,
            now=time.monotonic,
        )
    except (GitHubError, GitStepError) as error:
        warn(f"{repository.slug}: {getattr(error, 'detail', error)}")
        raise typer.Exit(1) from None
    where = f"#{outcome.pull_number}" if outcome.pull_number else ""
    if outcome.succeeded:
        say(f"{repository.slug}{where}: {outcome.reason}.")
        return
    warn(f"{repository.slug}{where}: not merged, {outcome.reason}.")
    raise typer.Exit(1)


@app.command("release")
def release(
    ctx: typer.Context,
    version: Annotated[str, VERSION_ARGUMENT],
    *,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Say what it would do, and stop."),
    ] = False,
) -> None:
    """
    Cut a release of iglootools/common: bump, merge once green, tag both ways.

    Run from common's checkout. Opens a pull request bumping .claude-plugin/plugin.json,
    merges it once every check has passed, then tags the merge commit with
    `claude plugin tag` (iglootools--vX.Y.Z) and the plain vX.Y.Z projects pin by, and
    checks both name the same commit.

    Plans from what GitHub already has: a release that stopped half way is resumed
    (tags only), one that is complete changes nothing, and tags that disagree with
    plugin.json are refused.
    """
    ensure(ctx, requirements.COMMON)
    root = invocation(ctx).root
    repository, github = github_session(ctx, None)
    if repository != pins.COMMON:
        warn(f"Releases are cut in {pins.COMMON.slug}, not {repository.slug}.")
        raise typer.Exit(2)
    try:
        found = releasing.plan_from_github(github, version)
    except GitHubError as error:
        warn(f"{repository.slug}: {error.detail}")
        raise typer.Exit(1) from None
    if found.problem:
        warn(f"{found.problem[0].upper()}{found.problem[1:]}.")
        raise typer.Exit(2 if not pins.VERSION.match(version) else 1)
    if not found.stages:
        say(f"{found.reason[0].upper()}{found.reason[1:]}: nothing to do.")
        return
    if dry_run:
        for line in releasing.steps(found, version):
            say(f"[dry-run] {line}")
        return
    try:
        outcome = releasing.release(
            root,
            github,
            repository,
            version,
            found,
            report=lambda event: say(event.detail),
            sleep=time.sleep,
            now=time.monotonic,
        )
    except (GitHubError, GitStepError, releasing.TagMismatchError, ValueError) as error:
        warn(f"{repository.slug}: {getattr(error, 'detail', error)}")
        raise typer.Exit(1) from None
    where = f"#{outcome.pull_number}" if outcome.pull_number else ""
    if not outcome.released:
        warn(f"{repository.slug}{where}: not released, {outcome.reason}.")
        raise typer.Exit(1)
    say(f"{repository.slug}{where}: {outcome.reason}.")


@app.command("check-pins")
def check_pins(ctx: typer.Context) -> None:
    """
    Fail when the project's pins on iglootools/common disagree or adopt would miss one.

    Finds every pin on common in the files git tracks, spelled any way, and fails when
    `common adopt` would not move one, when two name different releases, when a SHA pin
    lacks its `# vX.Y.Z` comment, or when they disagree with what uv.lock resolved. Runs
    offline, so it fits a `lint-common-pins` task.
    """
    ensure(ctx, (requirements.GIT,))
    root = invocation(ctx).root
    found, lock = pins.scan(root)
    issues = pins.problems(found, lock, root)
    for issue in issues:
        warn(issue)
    if issues:
        raise typer.Exit(1)
    versions = sorted({r.version for r in found if r.version})
    if not found:
        say("No pins on iglootools/common.")
        return
    checked = " and uv.lock" if lock else ""
    say(f"{len(found)} pins on iglootools/common, all at v{versions[0]}{checked}.")


@dataclass
class _Row:
    stage: str = "starting"
    pull: int | None = None
    started: float = field(default_factory=time.monotonic)
    finished: float | None = None


class _Board:
    """Each project's latest event, shared by the worker threads and the renderer."""

    def __init__(self, names: list[str], *, live: bool) -> None:
        self.rows = {name: _Row() for name in names}
        self.live = live
        self.lock = threading.Lock()

    def report(self, name: str, event: Event) -> None:
        with self.lock:
            row = self.rows[name]
            row.stage = event.detail
            row.pull = event.pull or row.pull
        if not self.live:
            say(f"[{name}] {event.detail}")

    def finish(self, name: str, outcome: adoption.Outcome) -> None:
        with self.lock:
            row = self.rows[name]
            row.stage = f"{outcome.result}: {outcome.reason}"
            row.pull = outcome.pull_number or row.pull
            row.finished = time.monotonic()

    def table(self) -> Table:
        table = Table(box=None, pad_edge=False)
        for column in ("project", "stage", "PR", "elapsed"):
            table.add_column(column, no_wrap=column != "stage")
        with self.lock:
            for name, row in self.rows.items():
                seconds = int((row.finished or time.monotonic()) - row.started)
                table.add_row(
                    name,
                    row.stage,
                    f"#{row.pull}" if row.pull else "",
                    f"{seconds // 60}:{seconds % 60:02d}",
                )
        return table


@app.command("adopt-all")
def adopt_all(
    ctx: typer.Context,
    version: Annotated[str, VERSION_ARGUMENT],
    only: Annotated[
        list[str] | None,
        typer.Option("--only", help="Adopt only this project; repeat."),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option("--exclude", help="Leave this project out; repeat."),
    ] = None,
    *,
    no_merge: Annotated[
        bool,
        typer.Option("--no-merge", help="Open the pull requests, do not merge them."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Check and plan, change nothing."),
    ] = False,
) -> None:
    """
    Move every iglootools project in the workspace to a release of common, in parallel.

    Run from common's checkout: the workspace is the directory it sits in. Takes every
    checked-out iglootools project that pins common (narrowed by --only and --exclude),
    fails when a repository of the organization pins common but has no checkout here,
    and checks every project (no changes or untracked files, origin reachable without a
    prompt, a default branch GitHub has every commit of) before changing any. Then
    adopts them all at once, as `common adopt` does, and summarises what merged. Safe to
    run again: each project picks up where it stopped.
    """
    ensure(ctx, requirements.COMMON)
    version = _version(version)
    root = invocation(ctx).root
    repository, github = github_session(ctx, None)
    if repository != pins.COMMON:
        warn(
            f"Run adopt-all from {pins.COMMON.slug}'s checkout, "
            f"not {repository.slug}'s.",
        )
        raise typer.Exit(2)
    try:
        sha = pins.tag_commit(github, version)
        projects, skipped = everywhere.discover(root.parent)
        selected, left_out = everywhere.select(projects, only or [], exclude or [])
        missing = everywhere.missing_checkouts(
            github,
            {p.name for p in projects},
            set(exclude or []),
        )
    except everywhere.SelectionError as error:
        warn(f"{error}.")
        raise typer.Exit(2) from None
    except GitHubError as error:
        warn(f"{error.detail}")
        raise typer.Exit(1) from None
    for item in [*skipped, *left_out]:
        say(f"Skipping {item.name}: {item.reason}.")
    _stop_if_blocked(_blockers(github, root.parent, missing, selected))
    if not selected:
        say("No project to adopt.")
        return
    if dry_run:
        _preview_all(github, selected, version, sha, merge_it=not no_merge)
        return
    outcomes = _run_everywhere(github, selected, version, sha, merge_it=not no_merge)
    _summarise(selected, outcomes)
    if not all(outcome.succeeded for outcome in outcomes.values()):
        raise typer.Exit(1)


def _stop_if_blocked(blocked: list[str]) -> None:
    if blocked:
        for issue in blocked:
            warn(issue)
        warn("Nothing was changed.")
        raise typer.Exit(1)


def _blockers(
    github: GitHub,
    workspace: Path,
    missing: list[str],
    selected: list[everywhere.Project],
) -> list[str]:
    """
    List what stops adopt-all from changing anything.

    That is each repository that pins common but has no checkout, and each problem in
    a selected project.
    """
    bases = {p.name: pulls.default_branch(github, p.repository) for p in selected}
    return [
        *(
            f"{name}: pins common on GitHub, but has no checkout in {workspace}; "
            "clone it, or pass --exclude"
            for name in missing
        ),
        *(
            f"{p.name}: {issue}"
            for p in selected
            for issue in everywhere.problems(p, bases[p.name])
        ),
    ]


def _preview_all(
    github: GitHub,
    selected: list[everywhere.Project],
    version: str,
    sha: str,
    *,
    merge_it: bool,
) -> None:
    for p in selected:
        found = adoption.plan(p.root, version, sha)
        for line in adoption.preview(
            p.root,
            github,
            p.repository,
            found,
            merge_it=merge_it,
        ):
            say(f"[dry-run] [{p.name}] {line}")


def _summarise(
    selected: list[everywhere.Project],
    outcomes: dict[str, adoption.Outcome],
) -> None:
    say("")
    for p in selected:
        outcome = outcomes[p.name]
        where = f" #{outcome.pull_number}" if outcome.pull_number else ""
        line = f"{p.name}{where}: {outcome.result}, {outcome.reason}"
        (say if outcome.succeeded else warn)(line)


def _run_everywhere(
    github: GitHub,
    projects: list[everywhere.Project],
    version: str,
    sha: str,
    *,
    merge_it: bool,
) -> dict[str, adoption.Outcome]:
    console = Console(highlight=False)
    board = _Board([p.name for p in projects], live=console.is_terminal)
    stop = threading.Event()

    def adopt_one(
        project: everywhere.Project,
        report: Report,
        sleep: Callable[[float], None],
        push_guard: AbstractContextManager[object],
    ) -> adoption.Outcome:
        outcome = adoption.adopt(
            project.root,
            github,
            project.repository,
            version,
            sha,
            merge_it=merge_it,
            report=report,
            sleep=sleep,
            now=time.monotonic,
            push_guard=push_guard,
        )
        board.finish(project.name, outcome)
        return outcome

    if not board.live:
        return everywhere.run_all(projects, adopt_one, report=board.report, stop=stop)
    with Live(get_renderable=board.table, console=console, refresh_per_second=2):
        return everywhere.run_all(projects, adopt_one, report=board.report, stop=stop)

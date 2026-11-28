"""The `iglootools workspace` commands: work on every project of the organization."""

import dataclasses
import json
import os
import shlex
import shutil
import tempfile
import threading
import time
from collections import Counter
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from iglootools.build import tasks
from iglootools.cliwiring import (
    FILE_OPTION,
    OUTPUT_OPTION,
    Mark,
    OutputFormat,
    emit,
    ensure,
    invocation,
    marked,
    progress,
    resolve_workspace_or_exit,
    say,
    spinning,
    styled,
    tally,
    warn,
)
from iglootools.common import (
    adopt as adoption,
    adopt_all as everywhere,
    cli as common_cli,
    pins,
    plugin,
)
from iglootools.common.plugin import PluginError
from iglootools.github import merge
from iglootools.github.cli import github_client
from iglootools.github.client import GitHub, GitHubError
from iglootools.github.events import Event, Report
from iglootools.preflight import requirements
from iglootools.workspace import (
    clone,
    parallel,
    plugins,
    renovate,
    run,
    status,
    sync,
    toolchain,
)
from iglootools.workspace.location import SENTINEL, cache_dir
from iglootools.workspace.repositories import (
    DEFAULT_MAX_AGE,
    ListingCacheError,
    OrganizationRepository,
    listing,
    parse_max_age,
)

app = typer.Typer(
    help="Work on every repository of the organization, checked out in the workspace.",
    no_args_is_help=True,
)

DRY_RUN_OPTION = typer.Option(
    "--dry-run",
    "-n",
    help="Say what would be done, change nothing.",
)


SKIP_PLUGINS_OPTION = typer.Option(
    "--skip-plugins",
    help="Leave the Claude Code plugins the projects enable as they are.",
)
FORCE_OPTION = typer.Option(
    "--force",
    help="Switch a clean checkout to the default branch even from a branch "
    "that has not merged.",
)
FETCH_OPTION = typer.Option(
    "--fetch/--no-fetch",
    help="Fetch each checkout first, so it is compared with origin as it is.",
)
MERGE_OPTION = typer.Option(
    "--merge",
    help="Merge each one once its checks pass, as merge-when-green does.",
)


CACHE_TTL_OPTION = typer.Option(
    "--cache-ttl",
    help="Reuse the cached repository listing while younger than this: 7d, 12h, "
    "30m; 0 lists the repositories again.",
)
REFRESH_OPTION = typer.Option(
    "--refresh",
    help="List the organization's repositories again, ignoring the cache.",
)


@dataclass(frozen=True)
class _Session:
    """The workspace, a GitHub client, and the repositories to work on."""

    workspace: Path
    github: GitHub
    repositories: list[OrganizationRepository]


def _session(
    ctx: typer.Context,
    *,
    cache_ttl: str,
    refresh: bool,
    announce: Callable[[str], None] = say,
) -> _Session:
    """
    Find the workspace and list the organization's repositories, or exit.

    The listing comes from the workspace's cache while younger than *cache_ttl*, unless
    *refresh*, and is kept there whenever the workspace's marker directory exists.
    Archived repositories are left out, and said so: they take no change.
    *announce* prints that, the workspace found and the listing's age; a command
    printing JSON sends them to stderr, keeping stdout to the JSON.
    """
    ensure(ctx, requirements.GITHUB)
    try:
        max_age = parse_max_age(cache_ttl)
    except ValueError:
        warn(f"--cache-ttl takes 7d, 12h, 30m or 0, not {cache_ttl!r}.")
        raise typer.Exit(2) from None
    workspace = resolve_workspace_or_exit(invocation(ctx).root, announce=announce)
    cache = cache_dir(workspace)
    github = github_client(ctx)
    now = datetime.now(UTC)
    try:
        with spinning("Listing the organization's repositories"):
            listed = listing(github, cache, max_age=max_age, refresh=refresh, now=now)
    except GitHubError as error:
        warn(error.detail)
        raise typer.Exit(1) from None
    except ListingCacheError as error:
        warn(
            f"{error.path} cannot be read ({error.detail}); --refresh lists the "
            "repositories again and rewrites it.",
        )
        raise typer.Exit(1) from None
    if listed.cached:
        announce(
            f"Repositories as listed {_ago(now - listed.listed_at)} ago "
            "(--refresh lists them again).",
        )
    found = listed.repositories
    archived = [repository.name for repository in found if repository.archived]
    if archived:
        announce(f"Skipping archived: {', '.join(archived)}.")
    return _Session(
        workspace,
        github,
        [repository for repository in found if not repository.archived],
    )


def _ago(age: timedelta) -> str:
    """Say how long ago, to the largest whole unit: 3 days, 5 hours, 12 minutes."""
    days, hours, minutes = age.days, age.seconds // 3600, age.seconds // 60 % 60
    found = next(
        (
            (value, name)
            for value, name in ((days, "day"), (hours, "hour"), (minutes, "minute"))
            if value
        ),
        None,
    )
    if found is None:
        return "less than a minute"
    amount, unit = found
    return f"{amount} {unit}{'' if amount == 1 else 's'}"


@app.command("init")
def init_cmd(
    ctx: typer.Context,
    *,
    dry_run: Annotated[bool, DRY_RUN_OPTION] = False,
) -> None:
    """
    Set the current directory, or --root, up as the iglootools workspace.

    Creates .iglootools-workspace/, which marks the workspace and holds what the
    commands reuse, and sets the workspace up as a project without Python of
    its own: a pyproject.toml pinning iglootools to common's newest release and a
    mise.toml from common's, installed with uv, so `iglootools` works there bare. Safe
    to run again; workspace sync keeps the files on the newest release. Refuses inside
    a git checkout, which is a project, not the directory that holds them. Clones
    nothing: `iglootools workspace sync` does, next.
    """
    root = invocation(ctx).root
    if (root / ".git").exists():
        warn(
            f"{root} is a git checkout. Run `iglootools workspace init` in the "
            "directory that holds the checkouts, or pass --root.",
        )
        raise typer.Exit(2)
    ensure(ctx, requirements.GITHUB)
    marker = root / SENTINEL
    created = (
        []
        if marker.is_dir()
        else [f"{'would create' if dry_run else 'created'} {SENTINEL}/"]
    )
    if created and not dry_run:
        marker.mkdir()
    setup = _set_up_workspace(root, github_client(ctx), version=None, dry_run=dry_run)
    _print_setup(
        toolchain.SetupResult([*created, *setup.done], setup.problems),
        "[dry-run] " if dry_run else "",
    )
    if setup.problems:
        raise typer.Exit(1)
    say("Next: `iglootools workspace sync`, to clone the organization's repositories.")


@app.command("clone")
def clone_cmd(
    ctx: typer.Context,
    *,
    cache_ttl: Annotated[str, CACHE_TTL_OPTION] = DEFAULT_MAX_AGE,
    refresh: Annotated[bool, REFRESH_OPTION] = False,
    fetch: Annotated[
        bool,
        typer.Option(
            "--fetch/--no-fetch",
            help="Fetch the repositories already cloned, pruning stale remote refs.",
        ),
    ] = True,
    dry_run: Annotated[bool, DRY_RUN_OPTION] = False,
) -> None:
    """
    Clone every repository of the organization the workspace lacks, and fetch the rest.

    Clones over SSH, or over HTTPS when every checkout already there uses it, into
    <workspace>/<repository>. Reports a directory there that is not a checkout, or
    whose origin is another repository, and leaves it alone. Archived repositories are
    skipped.
    """
    session = _session(ctx, cache_ttl=cache_ttl, refresh=refresh)
    results = clone_all(
        session.workspace,
        session.repositories,
        fetch=fetch,
        dry_run=dry_run,
    )
    if not _print_clone(results, dry_run=dry_run):
        raise typer.Exit(1)


@app.command("sync")
def sync_cmd(
    ctx: typer.Context,
    *,
    cache_ttl: Annotated[str, CACHE_TTL_OPTION] = DEFAULT_MAX_AGE,
    refresh: Annotated[bool, REFRESH_OPTION] = False,
    skip_plugins: Annotated[bool, SKIP_PLUGINS_OPTION] = False,
    force: Annotated[bool, FORCE_OPTION] = False,
    dry_run: Annotated[bool, DRY_RUN_OPTION] = False,
) -> None:
    """
    Bring every checkout in line with GitHub, and report what needs a person.

    Clones and fetches as `clone` does. Then, in each checkout: switches to the default
    branch when the branch it is on merged (with --force, from any branch), never with
    uncommitted changes, and warns of one left on unmerged work; fast-forwards it where
    safe and checks
    it matches origin's, and deletes every branch whose latest pull request merged, on
    GitHub and locally, as `github prune-branches` does; a local branch with commits
    the default branch lacks is kept. Then installs or updates, at project scope, every
    Claude Code plugin each project enables. Lists the branches kept, the other
    worktrees, and every problem; fails if there was any problem.
    """
    session = _session(ctx, cache_ttl=cache_ttl, refresh=refresh)
    if not (session.workspace / SENTINEL).is_dir():
        warn(
            f"{session.workspace} is not set up as a workspace: run `iglootools "
            "workspace init` there first.",
        )
        raise typer.Exit(2)
    setup = _set_up_workspace(
        session.workspace,
        session.github,
        version=None,
        dry_run=dry_run,
    )
    cloned = clone_all(
        session.workspace,
        session.repositories,
        fetch=True,
        dry_run=dry_run,
    )
    present = [
        repository
        for repository, result in zip(session.repositories, cloned, strict=True)
        if result.action != clone.CloneAction.FAILED
        and clone.is_checkout(clone.checkout_path(session.workspace, repository))
    ]
    with progress("Syncing", [r.name for r in present]) as done:
        synced = parallel.each(
            present,
            lambda repository: sync.sync_one(
                clone.checkout_path(session.workspace, repository),
                repository,
                session.github,
                force=force,
                dry_run=dry_run,
            ),
            on_done=lambda repository, _: done(repository.name),
        )
    plugin_sync = (
        plugins.PluginSync([], [])
        if skip_plugins
        else bring_plugins_up_to_date(
            [(r.name, clone.checkout_path(session.workspace, r)) for r in present],
            session.workspace,
            dry_run=dry_run,
        )
    )
    ok = print_sync(setup, cloned, synced, plugin_sync, dry_run=dry_run)
    if not ok:
        raise typer.Exit(1)


def _set_up_workspace(
    workspace: Path,
    github: GitHub,
    *,
    version: str | None,
    dry_run: bool,
) -> toolchain.SetupResult:
    """Put the workspace's iglootools on release *version*; the newest if None."""
    with spinning("Setting up the workspace's own iglootools"):
        try:
            found = (
                toolchain.recommended(github)
                if version is None
                else toolchain.at_release(github, version)
            )
        except GitHubError as error:
            return toolchain.SetupResult(problems=[error.detail])
        except toolchain.ToolchainError as error:
            return toolchain.SetupResult(problems=[_describe_toolchain_error(error)])
        return toolchain.set_up(
            workspace,
            found,
            dry_run=dry_run,
            run=run.captured(run.child_environment(os.environ)),
        )


def _print_setup(setup: toolchain.SetupResult, label: str) -> None:
    """Print what setting the workspace up did, under a `workspace:` header."""
    if setup.done or setup.problems:
        say(f"{label}workspace:")
        for line in setup.done:
            say(marked(Mark.OK, line, indent=1))
        for problem in setup.problems:
            warn(marked(Mark.FAILED, problem, indent=1))


def _describe_toolchain_error(error: toolchain.ToolchainError) -> str:
    match error.kind:
        case toolchain.ToolchainErrorKind.NO_RELEASE:
            return "iglootools/common has no release for the workspace to use"
        case toolchain.ToolchainErrorKind.NO_FILE:
            return f"iglootools/common {error.tag} has no {', '.join(error.missing)}"
        case toolchain.ToolchainErrorKind.MISSING_PIN:
            return f"iglootools/common {error.tag} lacks {', '.join(error.missing)}"


def bring_plugins_up_to_date(
    projects: Sequence[tuple[str, Path]],
    directory: Path,
    *,
    dry_run: bool,
) -> plugins.PluginSync:
    """
    Install or update the plugins each of *projects* enables, as sync does.

    *projects* are (name, checkout) pairs; the commands that concern no single project
    run in *directory*. Without `claude`, or when it cannot list what is installed,
    the step is a problem rather than an error.
    """
    if shutil.which("claude") is None:
        return plugins.PluginSync(
            [],
            [
                (
                    "claude not found, so no plugin was synced: install Claude Code, "
                    "or pass --skip-plugins"
                ),
            ],
        )
    try:
        with spinning("Installing and updating the Claude Code plugins"):
            return plugins.sync_plugins(projects, directory, dry_run=dry_run)
    except PluginError as error:
        return plugins.PluginSync([], [error.detail])


def print_sync(
    setup: toolchain.SetupResult,
    cloned: Sequence[clone.CloneResult],
    synced: Sequence[sync.SyncResult],
    plugin_sync: plugins.PluginSync,
    *,
    dry_run: bool,
) -> bool:
    """Print each repository's block, then a summary; tell whether nothing failed."""
    label = "[dry-run] " if dry_run else ""
    _print_setup(setup, label)
    clone_problems = [f"{r.name}: {r.problem}" for r in cloned if r.problem]
    for result in cloned:
        if result.action == clone.CloneAction.CLONED:
            cloned_it = "Would clone" if dry_run else "Cloned"
            say(Text.assemble(label, marked(Mark.OK, f"{cloned_it} {result.name}")))
    for name in plugin_sync.added:
        added = "Would add" if dry_run else "Added"
        say(Text.assemble(label, marked(Mark.OK, f"{added} the marketplace {name}")))
    steps_by_project = {
        name: [step for step in plugin_sync.steps if step.project == name]
        for name in (result.name for result in synced)
    }
    blocks = [
        _sync_block(result, steps_by_project[result.name], dry_run=dry_run)
        for result in synced
    ]
    for (header, lines, problems), result in zip(blocks, synced, strict=True):
        say(Text.assemble(label, header))
        for line in lines:
            say(f"  {line}")
        for warning in result.warnings:
            warn(marked(Mark.WARNING, warning, indent=1))
        for problem in problems:
            warn(marked(Mark.FAILED, problem, indent=1))
    everything = [
        *setup.problems,
        *clone_problems,
        *plugin_sync.problems,
        *(problem for _, _, problems in blocks for problem in problems),
    ]
    for problem in [*clone_problems, *plugin_sync.problems]:
        warn(marked(Mark.FAILED, problem))
    kept = sum(1 for result in synced if result.kept)
    warnings = sum(len(result.warnings) for result in synced)
    summary = tally(
        [
            (len(synced), "synced", Mark.OK),
            (kept, "with branches kept", Mark.WARNING),
            (warnings, "warning(s)", Mark.WARNING),
            (len(everything), "problem(s)", Mark.FAILED),
        ],
    )
    say(Text.assemble(label, summary, "."))
    return not everything


def _sync_block(
    result: sync.SyncResult,
    steps: Sequence[plugins.PluginStep],
    *,
    dry_run: bool,
) -> tuple[Text, list[str], list[str]]:
    """
    Return a repository's header, its lines, and its problems, ready to print.

    The header's mark is the worst the repository had: a problem, then a warning.
    """
    would = "would " if dry_run else ""
    plugin_lines = [
        f"{would}{step.action} plugin {step.plugin}"
        + (f": {step.version}" if step.version else "")
        for step in steps
        if not step.problem
    ]
    lines = [
        *result.done,
        *(f"kept {b.name} ({b.where}): {b.reason}" for b in result.kept),
        *(f"worktree {w}" for w in result.worktrees),
        *plugin_lines,
    ]
    problems = [
        *result.problems,
        *(f"{step.plugin}: {step.problem}" for step in steps if step.problem),
    ]
    quiet = not (result.done or problems or result.kept or result.warnings)
    mark = Mark.FAILED if problems else Mark.WARNING if result.warnings else Mark.OK
    return (
        marked(mark, f"{result.name}: up to date" if quiet else f"{result.name}:"),
        lines,
        problems,
    )


@app.command("status")
def status_cmd(
    ctx: typer.Context,
    *,
    cache_ttl: Annotated[str, CACHE_TTL_OPTION] = DEFAULT_MAX_AGE,
    refresh: Annotated[bool, REFRESH_OPTION] = False,
    fetch: Annotated[bool, FETCH_OPTION] = True,
    output: OUTPUT_OPTION = OutputFormat.HUMAN,
    file: FILE_OPTION = None,
) -> None:
    """
    Show where every repository stands, changing nothing but fetched refs.

    For each: the branch its checkout is on, its uncommitted changes, its default
    branch's commits ahead of and behind origin's, its other local branches and
    worktrees, and its open pull requests, Renovate's among them. Clones nothing: a
    repository the workspace lacks shows as not cloned. Fails if a status could not
    be read.
    """
    session = _session(
        ctx,
        cache_ttl=cache_ttl,
        refresh=refresh,
        announce=warn if output == OutputFormat.JSON else say,
    )
    with progress(
        "Reading the status",
        [r.name for r in session.repositories],
    ) as done:
        found = parallel.each(
            session.repositories,
            lambda repository: status.read_status(
                clone.checkout_path(session.workspace, repository),
                repository,
                session.github,
                fetch=fetch,
            ),
            on_done=lambda repository, _: done(repository.name),
        )
    match output:
        case OutputFormat.JSON:
            emit(json.dumps([dataclasses.asdict(row) for row in found], indent=2), file)
        case OutputFormat.HUMAN:
            print_status(found, file)
    if any(row.problem for row in found):
        raise typer.Exit(1)


def print_status(found: Sequence[status.RepositoryStatus], file: Path | None) -> None:
    """Print a row per repository, to *file* or the terminal; warn of each problem."""
    table = Table()
    for header in ("repository", "branch"):
        table.add_column(header, no_wrap=True)
    for header in ("changes", "vs origin", "branches", "worktrees", "PRs"):
        table.add_column(header)
    for row in found:
        table.add_row(*_status_cells(row))
    if file is None:
        Console(highlight=False).print(table)
    else:
        with file.open("w", encoding="utf-8") as handle:
            Console(file=handle, highlight=False, width=200).print(table)
    for row in found:
        if row.problem:
            warn(marked(Mark.FAILED, f"{row.name}: {row.problem}"))


def _status_mark(row: status.RepositoryStatus) -> Mark:
    """
    Return how a repository stands at a glance.

    Failed when its status could not be read, skipped when not cloned, a warning when
    its checkout differs from origin's default branch: changes, commits ahead or
    behind, or a detached HEAD.
    """
    match row:
        case status.RepositoryStatus(problem=problem) if problem:
            return Mark.FAILED
        case status.RepositoryStatus(cloned=False):
            return Mark.SKIPPED
        case _ if row.changes or row.ahead or row.behind or not row.branch:
            return Mark.WARNING
        case _:
            return Mark.OK


def _status_cells(row: status.RepositoryStatus) -> list[Text]:
    """Return a status row's cells, as Text: names are not markup."""
    pulls = Text(
        f"{row.open_pulls}"
        + (f" ({row.renovate_pulls} Renovate)" if row.renovate_pulls else ""),
    )
    name = marked(_status_mark(row), row.name)
    if not row.cloned:
        empty = [Text()] * 4
        return [name, styled("not cloned", Mark.SKIPPED), *empty, pulls]
    standing = (
        styled("up to date", Mark.OK)
        if not row.ahead and not row.behind
        else styled(
            ", ".join(
                [
                    *([f"{row.ahead} ahead"] if row.ahead else []),
                    *([f"{row.behind} behind"] if row.behind else []),
                ],
            ),
            Mark.WARNING,
        )
    )
    return [
        name,
        Text(row.branch) if row.branch else styled("detached", Mark.WARNING),
        styled(str(row.changes), Mark.WARNING) if row.changes else Text(),
        standing,
        Text(str(len(row.branches)) if row.branches else ""),
        Text(str(row.worktrees) if row.worktrees else ""),
        pulls,
    ]


@app.command(
    "run",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def run_cmd(
    ctx: typer.Context,
    task: Annotated[str, typer.Argument(help="The mise task to run in each project.")],
    *,
    cache_ttl: Annotated[str, CACHE_TTL_OPTION] = DEFAULT_MAX_AGE,
    refresh: Annotated[bool, REFRESH_OPTION] = False,
    jobs: Annotated[
        int,
        typer.Option(
            "--jobs",
            "-j",
            min=0,
            help="How many projects run at once; 0, the default, runs them all.",
        ),
    ] = 0,
    dry_run: Annotated[bool, DRY_RUN_OPTION] = False,
) -> None:
    """
    Run one mise task in every project of the workspace, and say where it passed.

    Arguments after the task go to it, as `iglootools repo run` passes them. Each
    project's output goes to a log file, named at the end; a failure shows the end of
    its log. A repository that is not cloned, or has no such task, is skipped. The task
    runs in the project's own environment, not common's. Fails if it failed anywhere.
    """
    session = _session(ctx, cache_ttl=cache_ttl, refresh=refresh)
    if dry_run:
        _preview_run(session, task, ctx.args)
        return
    log_dir = Path(tempfile.mkdtemp(prefix="iglootools-run-"))
    runner = run.logged(run.child_environment(os.environ))
    command = shlex.join(tasks.mise_command(task, ctx.args))
    say(f"Running {command} in each project")
    with progress(
        f"Running {command}",
        [r.name for r in session.repositories],
    ) as done:

        def finished(repository: OrganizationRepository, result: run.TaskRun) -> None:
            _print_run(result)
            done(repository.name)

        results = parallel.each(
            session.repositories,
            lambda repository: run.run_in(
                session.workspace,
                repository,
                task,
                ctx.args,
                log_dir,
                run=runner,
            ),
            jobs=jobs or None,
            on_done=finished,
        )
    if not _print_run_summary(results, log_dir):
        raise typer.Exit(1)


def _preview_run(session: _Session, task: str, args: Sequence[str]) -> None:
    command = shlex.join(tasks.mise_command(task, args))
    for repository in session.repositories:
        path = clone.checkout_path(session.workspace, repository)
        if not clone.is_checkout(path):
            say(f"[dry-run] {repository.name}: not cloned, skipped")
            continue
        try:
            has_task = task in {found.name for found in tasks.list_tasks(path)}
        except tasks.TaskListError as error:
            warn(f"[dry-run] {repository.name}: mise: {error}")
            continue
        say(
            f"[dry-run] {repository.name}: would run {command}"
            if has_task
            else f"[dry-run] {repository.name}: has no task {task!r}, skipped",
        )


def _print_run(result: run.TaskRun) -> None:
    """Print how the task ended in one project, with the end of its log if it failed."""
    match result.outcome:
        case run.RunOutcome.PASSED:
            say(marked(Mark.OK, f"{result.name}: passed in {result.seconds:.0f}s"))
        case run.RunOutcome.SKIPPED:
            say(marked(Mark.SKIPPED, f"{result.name}: skipped, {result.detail}"))
        case run.RunOutcome.FAILED:
            warn(marked(Mark.FAILED, f"{result.name}: failed, {result.detail}"))
            for line in result.tail:
                warn(f"  | {line}")


def _print_run_summary(results: Sequence[run.TaskRun], log_dir: Path) -> bool:
    """Print the count of each outcome and the logs' directory; tell if none failed."""
    counts = Counter(result.outcome for result in results)
    summary = tally(
        [
            (counts[run.RunOutcome.PASSED], "passed", Mark.OK),
            (counts[run.RunOutcome.FAILED], "failed", Mark.FAILED),
            (counts[run.RunOutcome.SKIPPED], "skipped", Mark.SKIPPED),
        ],
    )
    say(Text.assemble(summary, f". Logs: {log_dir}"))
    return not counts[run.RunOutcome.FAILED]


@app.command("renovate")
def renovate_cmd(
    ctx: typer.Context,
    *,
    cache_ttl: Annotated[str, CACHE_TTL_OPTION] = DEFAULT_MAX_AGE,
    refresh: Annotated[bool, REFRESH_OPTION] = False,
    merge_them: Annotated[bool, MERGE_OPTION] = False,
    dry_run: Annotated[bool, DRY_RUN_OPTION] = False,
    output: OUTPUT_OPTION = OutputFormat.HUMAN,
    file: FILE_OPTION = None,
) -> None:
    """
    List the open Renovate pull requests across the organization, and merge them.

    Each comes with what merge-when-green would do next: merge, wait for its checks,
    or refuse, and why. With --merge, merges every one it would not refuse, once its
    checks pass, deleting its branch: the repositories at once, the pull requests of
    one repository one after the other. Fails if one could not be read, or was not
    merged.
    """
    session = _session(
        ctx,
        cache_ttl=cache_ttl,
        refresh=refresh,
        announce=warn if output == OutputFormat.JSON else say,
    )
    with progress(
        "Reading the Renovate pull requests",
        [r.name for r in session.repositories],
    ) as done:
        found = parallel.each(
            session.repositories,
            lambda repository: renovate_pulls(session.github, repository),
            on_done=lambda repository, _: done(repository.name),
        )
    pulls = [pull for pulls, _ in found for pull in pulls]
    problems = [problem for _, problem in found if problem]
    match output:
        case OutputFormat.JSON:
            emit(json.dumps([pull_json(pull) for pull in pulls], indent=2), file)
        case OutputFormat.HUMAN:
            print_pulls(pulls, file)
    for problem in [
        *problems,
        *(f"{_pull_name(p)}: {p.problem}" for p in pulls if p.problem),
    ]:
        warn(marked(Mark.FAILED, problem))
    merged_ok = (
        merge_pulls(session.github, pulls, dry_run=dry_run) if merge_them else True
    )
    if problems or any(pull.problem for pull in pulls) or not merged_ok:
        raise typer.Exit(1)


def renovate_pulls(
    github: GitHub,
    repository: OrganizationRepository,
) -> tuple[list[renovate.RenovatePull], str]:
    """Return *repository*'s open Renovate pull requests, or why they are unreadable."""
    try:
        return renovate.find_pulls(github, repository), ""
    except GitHubError as error:
        return [], f"{repository.name}: {error.detail}"


def _pull_name(pull: renovate.RenovatePull) -> str:
    return f"{pull.repository.name}#{pull.number}"


def _verdict_text(pull: renovate.RenovatePull) -> Text:
    """Return what merge-when-green would do next, coloured by how well it goes."""
    if pull.verdict is None:
        return styled("not assessed", Mark.FAILED)
    mark = {
        merge.Action.MERGE: Mark.OK,
        merge.Action.WAIT: Mark.WARNING,
        merge.Action.REFUSE: Mark.FAILED,
        merge.Action.DONE: Mark.SKIPPED,
    }[pull.verdict.action]
    return styled(f"{pull.verdict.action}: {pull.verdict.reason}", mark)


def pull_json(pull: renovate.RenovatePull) -> dict[str, object]:
    """Return a Renovate pull request as the JSON output names its fields."""
    return {
        "repository": pull.repository.name,
        "number": pull.number,
        "title": pull.title,
        "action": str(pull.verdict.action) if pull.verdict else None,
        "reason": pull.verdict.reason if pull.verdict else None,
        "problem": pull.problem,
    }


def print_pulls(pulls: Sequence[renovate.RenovatePull], file: Path | None) -> None:
    """Print the Renovate pull requests and verdicts, to *file* or the terminal."""
    if not pulls:
        emit("No open Renovate pull request.", file)
        return
    table = Table()
    table.add_column("pull request", no_wrap=True)
    table.add_column("title")
    table.add_column("next")
    for pull in pulls:
        table.add_row(Text(_pull_name(pull)), Text(pull.title), _verdict_text(pull))
    if file is None:
        Console(highlight=False).print(table)
    else:
        with file.open("w", encoding="utf-8") as handle:
            Console(file=handle, highlight=False, width=200).print(table)


def merge_pulls(
    github: GitHub,
    pulls: Sequence[renovate.RenovatePull],
    *,
    dry_run: bool,
) -> bool:
    """Merge each pull request not refused, by repository; tell whether all merged."""
    chosen = [pull for pull in pulls if pull.mergeable]
    for pull in pulls:
        if not pull.mergeable and pull.verdict is not None:
            say(
                marked(
                    Mark.SKIPPED,
                    f"Leaving {_pull_name(pull)}: {pull.verdict.reason}.",
                ),
            )
    if dry_run:
        for pull in chosen:
            say(f"[dry-run] Would merge {_pull_name(pull)} once its checks pass.")
        return True
    groups = [
        [pull for pull in chosen if pull.repository.name == name]
        for name in dict.fromkeys(pull.repository.name for pull in chosen)
    ]

    def merge_group(
        group: list[renovate.RenovatePull],
        sleep: parallel.Sleep,
    ) -> list[tuple[renovate.RenovatePull, merge.Outcome | str]]:
        try:
            return renovate.merge_all(
                github,
                group,
                sleep=sleep,
                now=time.monotonic,
                report=lambda pull: (
                    lambda event: say(
                        f"[{_pull_name(pull)}] {event.detail}",
                    )
                ),
            )
        except parallel.CancelledError:
            return [(pull, "interrupted; run again to resume") for pull in group]

    results = [
        result
        for group in parallel.each_interruptible(
            groups,
            merge_group,
            stop=threading.Event(),
        )
        for result in group
    ]
    for pull, outcome in results:
        match outcome:
            case merge.Outcome(merged=True):
                say(marked(Mark.OK, f"{_pull_name(pull)}: merged."))
            case merge.Outcome(reason=reason) | (str() as reason):
                warn(marked(Mark.FAILED, f"{_pull_name(pull)}: not merged, {reason}."))
    return all(
        isinstance(outcome, merge.Outcome) and outcome.merged for _, outcome in results
    )


def clone_all(
    workspace: Path,
    repositories: Sequence[OrganizationRepository],
    *,
    fetch: bool,
    dry_run: bool,
) -> list[clone.CloneResult]:
    """Clone or fetch each of *repositories* at once, as the clone command does."""
    protocol = clone.infer_protocol(clone.existing_origins(workspace, repositories))
    with progress(
        "Cloning and fetching" if fetch else "Cloning",
        [r.name for r in repositories],
    ) as done:
        return parallel.each(
            repositories,
            lambda repository: clone.clone_one(
                workspace,
                repository,
                protocol,
                fetch=fetch,
                dry_run=dry_run,
            ),
            on_done=lambda repository, _: done(repository.name),
        )


def _print_clone(results: Sequence[clone.CloneResult], *, dry_run: bool) -> bool:
    """Print what clone did to each repository; tell whether none failed."""
    label = "[dry-run] " if dry_run else ""
    for result in results:
        match result.action:
            case clone.CloneAction.CLONED:
                did = "Would clone" if dry_run else "Cloned"
                say(Text.assemble(label, marked(Mark.OK, f"{did} {result.name}")))
            case clone.CloneAction.FETCHED:
                did = "Would fetch" if dry_run else "Fetched"
                say(Text.assemble(label, marked(Mark.OK, f"{did} {result.name}")))
            case clone.CloneAction.PRESENT:
                say(marked(Mark.SKIPPED, f"{result.name}: already cloned"))
            case clone.CloneAction.FAILED:
                warn(marked(Mark.FAILED, f"{result.name}: {result.problem}"))
    counts = Counter(result.action for result in results)
    summary = tally(
        [
            (counts[clone.CloneAction.CLONED], "cloned", Mark.OK),
            (counts[clone.CloneAction.FETCHED], "fetched", Mark.OK),
            (counts[clone.CloneAction.FAILED], "failed", Mark.FAILED),
        ],
    )
    say(Text.assemble(label, summary, "."))
    return not counts[clone.CloneAction.FAILED]


@dataclass
class _Row:
    """
    One project's line on the board: a spinner while it runs, its mark once done.

    The spinner is kept from one redraw to the next, as it animates from when it was
    first drawn.
    """

    stage: str = "starting"
    pull: int | None = None
    started: float = field(default_factory=time.monotonic)
    finished: float | None = None
    mark: Mark | None = None
    spinner: Spinner = field(default_factory=lambda: Spinner("dots"))


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
            row.mark = _adopt_mark(outcome)

    def table(self) -> Table:
        table = Table(box=None, pad_edge=False)
        for column in ("project", "stage", "PR", "elapsed"):
            table.add_column(column, no_wrap=column != "stage")
        with self.lock:
            for name, row in self.rows.items():
                seconds = int((row.finished or time.monotonic()) - row.started)
                table.add_row(
                    _board_project(name, row),
                    Text(row.stage)
                    if row.mark is None
                    else styled(row.stage, row.mark),
                    f"#{row.pull}" if row.pull else "",
                    f"{seconds // 60}:{seconds % 60:02d}",
                )
        return table


def _board_project(name: str, row: _Row) -> Spinner | Text:
    """Return the project's cell: its spinner while it runs, then its mark."""
    if row.mark is None:
        row.spinner.update(text=Text(name))
        return row.spinner
    return marked(row.mark, name)


def _adopt_mark(outcome: adoption.Outcome) -> Mark:
    """Return the mark of how an adopt ended: refused failed, a release reached ok."""
    match outcome.result:
        case adoption.Result.REFUSED:
            return Mark.FAILED
        case adoption.Result.OPENED:
            return Mark.WARNING
        case adoption.Result.MERGED | adoption.Result.UP_TO_DATE:
            return Mark.OK


@app.command("adopt-common")
def adopt_common_cmd(
    ctx: typer.Context,
    version: Annotated[str | None, common_cli.ADOPTED_VERSION_ARGUMENT] = None,
    only: Annotated[
        list[str] | None,
        typer.Option("--only", help="Adopt only this project; repeat."),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option("--exclude", help="Leave this project out; repeat."),
    ] = None,
    *,
    cache_ttl: Annotated[str, CACHE_TTL_OPTION] = DEFAULT_MAX_AGE,
    refresh: Annotated[bool, REFRESH_OPTION] = False,
    no_merge: Annotated[
        bool,
        typer.Option("--no-merge", help="Open the pull requests, do not merge them."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Check and plan, change nothing."),
    ] = False,
    skip_plugin: Annotated[bool, common_cli.SKIP_PLUGIN_OPTION] = False,
    latest: Annotated[bool, common_cli.LATEST_OPTION] = False,
    keep_worktree: Annotated[bool, common_cli.KEEP_WORKTREE_OPTION] = False,
    skip_fast_forward: Annotated[bool, common_cli.SKIP_FAST_FORWARD_OPTION] = False,
) -> None:
    """
    Move every project of the workspace to a release of iglootools/common, at once.

    Also puts the workspace's own iglootools on the release, as workspace sync does
    for the newest. Takes every checked-out project that pins common, common itself
    aside (narrowed by
    --only and --exclude), fails when a repository of the organization pins common but
    has no checkout in the workspace,
    and checks that every project's origin is reachable without a prompt before
    changing any. Then adopts them all at once, as `repo adopt-common` does, each in a
    temporary worktree, so the checkouts are left to whoever works in them; summarises
    what merged, and updates the Claude Code plugin in each project on the release that
    enables it. Safe to run again: each project picks up where it stopped.
    """
    workplace = adoption.Workplace(
        keep_worktree=keep_worktree,
        skip_fast_forward=skip_fast_forward,
    )
    ensure(ctx, requirements.COMMON)
    session = _session(ctx, cache_ttl=cache_ttl, refresh=refresh)
    github, workspace = session.github, session.workspace
    version = common_cli.adopted_version_or_exit(github, version, latest=latest)
    try:
        with spinning("Finding the projects that pin iglootools/common"):
            sha = pins.tag_commit(github, version)
            found = everywhere.discover(workspace, session.repositories)
            selected, left_out = everywhere.select(
                found.projects,
                only or [],
                exclude or [],
            )
            unchecked = everywhere.find_unchecked(
                github,
                [r for r in found.not_checked_out if r.name not in (exclude or [])],
            )
    except everywhere.SelectionError as error:
        warn(f"{error}.")
        raise typer.Exit(2) from None
    except GitHubError as error:
        warn(f"{error.detail}")
        raise typer.Exit(1) from None
    _report_skips([*found.skipped, *left_out], unchecked.passed_over)
    _stop_if_blocked(_blockers(workspace, unchecked.missing, selected))
    projects_ok = _adopt_projects(
        github,
        selected,
        version,
        sha,
        merge_it=not no_merge,
        skip_plugin=skip_plugin,
        workplace=workplace,
        dry_run=dry_run,
    )
    setup = _set_up_workspace(
        session.workspace,
        session.github,
        version=version,
        dry_run=dry_run,
    )
    _print_setup(setup, "[dry-run] " if dry_run else "")
    if not projects_ok or setup.problems:
        raise typer.Exit(1)


def _adopt_projects(
    github: GitHub,
    selected: list[everywhere.Project],
    version: str,
    sha: str,
    *,
    merge_it: bool,
    skip_plugin: bool,
    workplace: adoption.Workplace,
    dry_run: bool,
) -> bool:
    """Adopt *version* in every selected project, or preview it; tell if all did."""
    if not selected:
        say("No project to adopt.")
        return True
    if dry_run:
        _preview_all(
            github,
            selected,
            version,
            sha,
            merge_it=merge_it,
            skip_plugin=skip_plugin,
            workplace=workplace,
        )
        return True
    outcomes = _run_everywhere(
        github,
        selected,
        version,
        sha,
        merge_it=merge_it,
        workplace=workplace,
    )
    return _report_all(selected, outcomes, version, skip_plugin=skip_plugin)


def _report_skips(
    local: Sequence[everywhere.Skipped],
    remote: Sequence[everywhere.Skipped],
) -> None:
    """
    Say which checkouts are passed over, and warn of each repository not checked out.

    A repository with no checkout is warned of, so that one meant to pin common but
    missing the preset is seen rather than silently left on its old release.
    """
    for item in local:
        say(marked(Mark.SKIPPED, f"Skipping {item.name}: {item.reason}."))
    for item in remote:
        warn(marked(Mark.WARNING, f"Skipping {item.name}: {item.reason}."))


def _stop_if_blocked(blocked: list[str]) -> None:
    if blocked:
        for issue in blocked:
            warn(marked(Mark.FAILED, issue))
        warn("Nothing was changed.")
        raise typer.Exit(1)


def _blockers(
    workspace: Path,
    missing: list[str],
    selected: list[everywhere.Project],
) -> list[str]:
    """
    List what stops adopt-common from changing anything.

    That is each repository that pins common but has no checkout, and each problem in
    a selected project.
    """
    return [
        *(
            f"{name}: pins common on GitHub, but has no checkout in {workspace}; "
            "clone it, or pass --exclude"
            for name in missing
        ),
        *(f"{p.name}: {issue}" for p in selected for issue in everywhere.problems(p)),
    ]


def _preview_all(
    github: GitHub,
    selected: list[everywhere.Project],
    version: str,
    sha: str,
    *,
    merge_it: bool,
    skip_plugin: bool,
    workplace: adoption.Workplace,
) -> None:
    for p in selected:
        found = adoption.plan(p.root, version, sha)
        try:
            update_plugin = not skip_plugin and plugin.is_enabled(p.root)
        except plugin.PluginError as error:
            warn(f"[{p.name}] {error.detail}")
            update_plugin = False
        for line in adoption.preview(
            p.root,
            github,
            p.repository,
            found,
            merge_it=merge_it,
            update_plugin=update_plugin,
            workplace=workplace,
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
        line = marked(
            _adopt_mark(outcome),
            f"{p.name}{where}: {outcome.result}, {outcome.reason}",
        )
        (say if outcome.succeeded else warn)(line)


def _run_everywhere(
    github: GitHub,
    projects: list[everywhere.Project],
    version: str,
    sha: str,
    *,
    merge_it: bool,
    workplace: adoption.Workplace,
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
            workplace=workplace,
        )
        board.finish(project.name, outcome)
        return outcome

    if not board.live:
        return everywhere.run_all(projects, adopt_one, report=board.report, stop=stop)
    with Live(get_renderable=board.table, console=console, refresh_per_second=2):
        return everywhere.run_all(projects, adopt_one, report=board.report, stop=stop)


def _report_all(
    selected: list[everywhere.Project],
    outcomes: dict[str, adoption.Outcome],
    version: str,
    *,
    skip_plugin: bool,
) -> bool:
    """
    Summarise each outcome, then update the plugin in each project on the release.

    Tell whether every project adopted and every plugin update worked.
    """
    _summarise(selected, outcomes)
    on_release = [(p.name, p.root) for p in selected if outcomes[p.name].on_release]
    plugins_ok = skip_plugin or common_cli.update_plugins(on_release, version)
    return plugins_ok and all(outcome.succeeded for outcome in outcomes.values())

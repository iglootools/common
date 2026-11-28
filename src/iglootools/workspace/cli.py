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
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from iglootools.build import tasks
from iglootools.cliwiring import (
    FILE_OPTION,
    OUTPUT_OPTION,
    OutputFormat,
    emit,
    ensure,
    invocation,
    resolve_workspace_or_exit,
    say,
    warn,
)
from iglootools.common.plugin import PluginError
from iglootools.github import merge
from iglootools.github.cli import github_client
from iglootools.github.client import GitHub, GitHubError
from iglootools.preflight import requirements
from iglootools.workspace import (
    clone,
    parallel,
    plugins,
    renovate,
    run,
    status,
    sync,
)
from iglootools.workspace.location import cache_dir
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
    synced = parallel.each(
        present,
        lambda repository: sync.sync_one(
            clone.checkout_path(session.workspace, repository),
            repository,
            session.github,
            force=force,
            dry_run=dry_run,
        ),
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
    ok = print_sync(cloned, synced, plugin_sync, dry_run=dry_run)
    if not ok:
        raise typer.Exit(1)


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
        return plugins.sync_plugins(projects, directory, dry_run=dry_run)
    except PluginError as error:
        return plugins.PluginSync([], [error.detail])


def print_sync(
    cloned: Sequence[clone.CloneResult],
    synced: Sequence[sync.SyncResult],
    plugin_sync: plugins.PluginSync,
    *,
    dry_run: bool,
) -> bool:
    """Print each repository's block, then a summary; tell whether nothing failed."""
    label = "[dry-run] " if dry_run else ""
    clone_problems = [f"{r.name}: {r.problem}" for r in cloned if r.problem]
    for result in cloned:
        if result.action == clone.CloneAction.CLONED:
            say(f"{label}{'Would clone' if dry_run else 'Cloned'} {result.name}")
    for name in plugin_sync.added:
        say(f"{label}{'Would add' if dry_run else 'Added'} the marketplace {name}")
    steps_by_project = {
        name: [step for step in plugin_sync.steps if step.project == name]
        for name in (result.name for result in synced)
    }
    blocks = [
        _sync_block(result, steps_by_project[result.name], dry_run=dry_run)
        for result in synced
    ]
    for (header, lines, problems), result in zip(blocks, synced, strict=True):
        say(f"{label}{header}")
        for line in lines:
            say(f"  {line}")
        for warning in result.warnings:
            warn(f"  warning: {warning}")
        for problem in problems:
            warn(f"  ! {problem}")
    everything = [
        *clone_problems,
        *plugin_sync.problems,
        *(problem for _, _, problems in blocks for problem in problems),
    ]
    for problem in [*clone_problems, *plugin_sync.problems]:
        warn(problem)
    kept = sum(1 for result in synced if result.kept)
    warnings = sum(len(result.warnings) for result in synced)
    say(
        f"{label}{len(synced)} synced, {kept} with branches kept, "
        f"{warnings} warning(s), {len(everything)} problem(s).",
    )
    return not everything


def _sync_block(
    result: sync.SyncResult,
    steps: Sequence[plugins.PluginStep],
    *,
    dry_run: bool,
) -> tuple[str, list[str], list[str]]:
    """Return a repository's header, its lines, and its problems, ready to print."""
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
    return (
        f"{result.name}: up to date" if quiet else f"{result.name}:",
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
    found = parallel.each(
        session.repositories,
        lambda repository: status.read_status(
            clone.checkout_path(session.workspace, repository),
            repository,
            session.github,
            fetch=fetch,
        ),
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
            warn(f"{row.name}: {row.problem}")


def _status_cells(row: status.RepositoryStatus) -> list[str]:
    """Return a status row's cells, as plain text: names are not markup."""
    pulls = f"{row.open_pulls}" + (
        f" ({row.renovate_pulls} Renovate)" if row.renovate_pulls else ""
    )
    if not row.cloned:
        return [row.name, "not cloned", "", "", "", "", pulls]
    standing = (
        "up to date"
        if not row.ahead and not row.behind
        else ", ".join(
            [
                *([f"{row.ahead} ahead"] if row.ahead else []),
                *([f"{row.behind} behind"] if row.behind else []),
            ],
        )
    )
    return [
        row.name,
        row.branch or "detached",
        str(row.changes) if row.changes else "",
        standing,
        str(len(row.branches)) if row.branches else "",
        str(row.worktrees) if row.worktrees else "",
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

    Arguments after the task go to it, as `iglootools build` passes them. Each
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
    say(f"Running {shlex.join(tasks.mise_command(task, ctx.args))} in each project")
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
    )
    if not _print_runs(results, log_dir):
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


def _print_runs(results: Sequence[run.TaskRun], log_dir: Path) -> bool:
    """Print each project's outcome and the logs' directory; tell if all passed."""
    for result in results:
        match result.outcome:
            case run.RunOutcome.PASSED:
                say(f"{result.name}: passed in {result.seconds:.0f}s")
            case run.RunOutcome.SKIPPED:
                say(f"{result.name}: skipped, {result.detail}")
            case run.RunOutcome.FAILED:
                warn(f"{result.name}: failed, {result.detail}")
                for line in result.tail:
                    warn(f"  | {line}")
    failed = [r.name for r in results if r.outcome == run.RunOutcome.FAILED]
    passed = sum(1 for r in results if r.outcome == run.RunOutcome.PASSED)
    say(f"{passed} passed, {len(failed)} failed. Logs: {log_dir}")
    return not failed


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
    found = parallel.each(
        session.repositories,
        lambda repository: renovate_pulls(session.github, repository),
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
        warn(problem)
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


def _verdict_text(pull: renovate.RenovatePull) -> str:
    if pull.verdict is None:
        return "not assessed"
    return f"{pull.verdict.action}: {pull.verdict.reason}"


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
        table.add_row(_pull_name(pull), pull.title, _verdict_text(pull))
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
            say(f"Leaving {_pull_name(pull)}: {pull.verdict.reason}.")
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
                say(f"{_pull_name(pull)}: merged.")
            case merge.Outcome(reason=reason):
                warn(f"{_pull_name(pull)}: not merged, {reason}.")
            case str() as reason:
                warn(f"{_pull_name(pull)}: not merged, {reason}.")
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
    return parallel.each(
        repositories,
        lambda repository: clone.clone_one(
            workspace,
            repository,
            protocol,
            fetch=fetch,
            dry_run=dry_run,
        ),
    )


def _print_clone(results: Sequence[clone.CloneResult], *, dry_run: bool) -> bool:
    """Print what clone did to each repository; tell whether none failed."""
    prefix = "[dry-run] Would " if dry_run else ""
    for result in results:
        match result.action:
            case clone.CloneAction.CLONED:
                say(f"{prefix}{'clone' if dry_run else 'Cloned'} {result.name}")
            case clone.CloneAction.FETCHED:
                say(f"{prefix}{'fetch' if dry_run else 'Fetched'} {result.name}")
            case clone.CloneAction.PRESENT:
                say(f"{result.name}: already cloned")
            case clone.CloneAction.FAILED:
                warn(f"{result.name}: {result.problem}")
    counts = Counter(result.action for result in results)
    say(
        f"{'[dry-run] ' if dry_run else ''}{counts[clone.CloneAction.CLONED]} cloned, "
        f"{counts[clone.CloneAction.FETCHED]} fetched, "
        f"{counts[clone.CloneAction.FAILED]} failed.",
    )
    return not counts[clone.CloneAction.FAILED]

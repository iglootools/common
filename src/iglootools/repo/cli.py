"""
The `iglootools repo` commands: work on the repository checked out at --root.

Each is the one-repository form of a workspace command, on the same core and options:
`repo adopt-common` of `workspace adopt-common`, `repo sync` of `workspace sync`, and
likewise status, renovate and run. The workspace commands run them on every repository
of the organization at once.
"""

import dataclasses
import json
import time
from pathlib import Path
from typing import Annotated

import typer

from iglootools.build import cli as build_cli
from iglootools.cliwiring import (
    FILE_OPTION,
    OUTPUT_OPTION,
    Mark,
    OutputFormat,
    emit,
    ensure,
    invocation,
    marked,
    say,
    spinning,
    warn,
)
from iglootools.common import (
    adopt as adoption,
    adopt_all as everywhere,
    cli as common_cli,
    pins,
    plugin,
)
from iglootools.github.cli import REPO_OPTION, github_session
from iglootools.github.client import GitHub, GitHubError
from iglootools.github.local import GitStepError
from iglootools.preflight import requirements
from iglootools.workspace import (
    cli as workspace_cli,
    clone,
    plugins,
    status,
    sync,
    toolchain,
)
from iglootools.workspace.repositories import OrganizationRepository, get_repository

app = typer.Typer(
    help="Work on the repository at --root, as workspace does on every one.",
    no_args_is_help=True,
)
app.command(
    "run",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)(build_cli.build)


@app.command("adopt-common")
def adopt_common_cmd(
    ctx: typer.Context,
    version: Annotated[str | None, common_cli.ADOPTED_VERSION_ARGUMENT] = None,
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
    skip_plugin: Annotated[bool, common_cli.SKIP_PLUGIN_OPTION] = False,
    latest: Annotated[bool, common_cli.LATEST_OPTION] = False,
    keep_worktree: Annotated[bool, common_cli.KEEP_WORKTREE_OPTION] = False,
    skip_fast_forward: Annotated[bool, common_cli.SKIP_FAST_FORWARD_OPTION] = False,
) -> None:
    """
    Move every pin on iglootools/common to a release, through a pull request.

    Moves the reusable workflows (to the release's commit), the iglootools command and
    the Renovate presets, and regenerates uv.lock, in a temporary worktree started from
    GitHub's default branch: the checkout is left as it is, whatever branch it is on
    and whatever changes it has. Then opens a pull request and merges it once every
    check has passed, as merge-when-green does, and fast-forwards the checkout's default
    branch where that is safe. Once the project is on the release, updates the Claude
    Code plugin installed for it, when its .claude/settings.json enables the plugin.
    Safe to run again: it picks up from the pull request or branch an earlier run left,
    and does nothing once the release is in place. To finish the branch by hand, pass
    --no-merge and check the branch out in any worktree.
    """
    ensure(ctx, requirements.COMMON)
    workplace = adoption.Workplace(
        keep_worktree=keep_worktree,
        skip_fast_forward=skip_fast_forward,
    )
    root = invocation(ctx).root
    repository, github = github_session(ctx, repo)
    version = common_cli.adopted_version_or_exit(github, version, latest=latest)
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
                update_plugin=not skip_plugin and plugin.is_enabled(root),
                workplace=workplace,
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
            workplace=workplace,
        )
    except (GitHubError, GitStepError, plugin.PluginError) as error:
        detail = everywhere.describe(error, str(getattr(error, "detail", error)))
        warn(marked(Mark.FAILED, f"{repository.slug}: {detail}"))
        raise typer.Exit(1) from None
    where = f"#{outcome.pull_number}" if outcome.pull_number else ""
    if not outcome.succeeded:
        warn(
            marked(
                Mark.FAILED,
                f"{repository.slug}{where}: not merged, {outcome.reason}.",
            ),
        )
        raise typer.Exit(1)
    say(marked(Mark.OK, f"{repository.slug}{where}: {outcome.reason}."))
    on_release = [(repository.name, root)] if outcome.on_release else []
    if not skip_plugin and not common_cli.update_plugins(on_release, version):
        raise typer.Exit(1)


@app.command("lint-common-pins")
def lint_common_pins_cmd(ctx: typer.Context) -> None:
    """
    Fail when the project's pins on iglootools/common disagree or adopt would miss one.

    Finds every pin on common in the files git tracks, spelled any way, and fails when
    `repo adopt-common` would not move one, when two name different releases, when a SHA
    pin lacks its `# vX.Y.Z` comment, or when they disagree with what uv.lock resolved.
    Runs offline, as the `lint-common-pins` task it is named after does in `lint`.
    """
    ensure(ctx, (requirements.GIT,))
    root = invocation(ctx).root
    found, lock = pins.scan(root)
    issues = pins.problems(found, lock, root)
    for issue in issues:
        warn(marked(Mark.FAILED, issue))
    if issues:
        raise typer.Exit(1)
    versions = sorted({r.version for r in found if r.version})
    if not found:
        say("No pins on iglootools/common.")
        return
    checked = " and uv.lock" if lock else ""
    say(
        marked(
            Mark.OK,
            f"{len(found)} pins on iglootools/common, all at v{versions[0]}{checked}.",
        ),
    )


def _this_repository(ctx: typer.Context) -> tuple[GitHub, OrganizationRepository, Path]:
    """
    Return a GitHub client, the repository checked out at --root, and its checkout.

    The repository is the checkout's origin; exits 2 when that is no GitHub
    repository, and 1 when GitHub cannot describe it.
    """
    ensure(ctx, requirements.GITHUB)
    root = invocation(ctx).root
    repository, github = github_session(ctx, None)
    try:
        return github, get_repository(github, repository), root
    except GitHubError as error:
        warn(f"{repository.slug}: {error.detail}")
        raise typer.Exit(1) from None


@app.command("sync")
def sync_cmd(
    ctx: typer.Context,
    *,
    skip_plugins: Annotated[bool, workspace_cli.SKIP_PLUGINS_OPTION] = False,
    force: Annotated[bool, workspace_cli.FORCE_OPTION] = False,
    dry_run: Annotated[bool, workspace_cli.DRY_RUN_OPTION] = False,
) -> None:
    """
    Bring this checkout in line with GitHub, as workspace sync does for every one.

    Fetches, then switches to the default branch when the branch the checkout is on
    merged (with --force, from any branch), never with uncommitted changes;
    fast-forwards it where safe and checks it matches origin's; deletes every branch
    whose latest pull request merged, on GitHub and locally; and installs or updates the
    Claude Code
    plugins the project enables. Lists the branches kept, the other worktrees and every
    problem; fails if there was any problem.
    """
    github, repository, root = _this_repository(ctx)
    with spinning(f"Syncing {repository.name}"):
        fetched = "" if dry_run else clone.fetch_origin(root)
        synced = (
            []
            if fetched
            else [
                sync.sync_one(root, repository, github, force=force, dry_run=dry_run),
            ]
        )
    cloned = [
        clone.CloneResult(
            repository.name,
            clone.CloneAction.FAILED if fetched else clone.CloneAction.FETCHED,
            fetched,
        ),
    ]
    plugin_sync = (
        plugins.PluginSync([], [])
        if skip_plugins
        else workspace_cli.bring_plugins_up_to_date(
            [(repository.name, root)],
            root,
            dry_run=dry_run,
        )
    )
    if not workspace_cli.print_sync(
        toolchain.SetupResult(),
        cloned,
        synced,
        plugin_sync,
        dry_run=dry_run,
    ):
        raise typer.Exit(1)


@app.command("status")
def status_cmd(
    ctx: typer.Context,
    *,
    fetch: Annotated[bool, workspace_cli.FETCH_OPTION] = True,
    output: OUTPUT_OPTION = OutputFormat.HUMAN,
    file: FILE_OPTION = None,
) -> None:
    """
    Show where this repository stands, as workspace status does for every one.

    The branch the checkout is on, its uncommitted changes, its default branch's
    commits ahead of and behind origin's, its other local branches and worktrees, and
    its open pull requests, Renovate's among them. Changes nothing but fetched refs.
    Fails if the status could not be read.
    """
    github, repository, root = _this_repository(ctx)
    with spinning(f"Reading the status of {repository.name}"):
        found = status.read_status(root, repository, github, fetch=fetch)
    match output:
        case OutputFormat.JSON:
            emit(json.dumps(dataclasses.asdict(found), indent=2), file)
        case OutputFormat.HUMAN:
            workspace_cli.print_status([found], file)
    if found.problem:
        raise typer.Exit(1)


@app.command("renovate")
def renovate_cmd(
    ctx: typer.Context,
    *,
    merge_them: Annotated[bool, workspace_cli.MERGE_OPTION] = False,
    dry_run: Annotated[bool, workspace_cli.DRY_RUN_OPTION] = False,
    output: OUTPUT_OPTION = OutputFormat.HUMAN,
    file: FILE_OPTION = None,
) -> None:
    """
    List this repository's open Renovate pull requests, and merge them.

    As workspace renovate does for every repository: each comes with what
    merge-when-green would do next, and --merge merges every one it would not refuse,
    once its checks pass, one after the other. Fails if one could not be read, or was
    not merged.
    """
    github, repository, _ = _this_repository(ctx)
    with spinning(f"Reading the Renovate pull requests of {repository.name}"):
        pulls, problem = workspace_cli.renovate_pulls(github, repository)
    match output:
        case OutputFormat.JSON:
            emit(
                json.dumps([workspace_cli.pull_json(p) for p in pulls], indent=2),
                file,
            )
        case OutputFormat.HUMAN:
            workspace_cli.print_pulls(pulls, file)
    for line in [problem, *(f"#{p.number}: {p.problem}" for p in pulls if p.problem)]:
        if line:
            warn(marked(Mark.FAILED, line))
    merged = (
        workspace_cli.merge_pulls(github, pulls, dry_run=dry_run)
        if merge_them
        else True
    )
    if problem or any(p.problem for p in pulls) or not merged:
        raise typer.Exit(1)

"""The `iglootools common` commands, for common itself, and what adopting it shares."""

import time
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated

import typer

from iglootools.cliwiring import (
    ensure,
    invocation,
    say,
    warn,
)
from iglootools.common import (
    indexes,
    pins,
    plugin,
    release as releasing,
)
from iglootools.github.cli import github_session
from iglootools.github.client import GitHub, GitHubError
from iglootools.github.local import GitStepError
from iglootools.preflight import requirements
from iglootools.workspace import plugins

app = typer.Typer(
    help="Maintain a project's link to iglootools/common.",
    no_args_is_help=True,
)

VERSION_ARGUMENT = typer.Argument(help="The release, as X.Y.Z.")
ADOPTED_VERSION_ARGUMENT = typer.Argument(
    help="The release to adopt, as X.Y.Z; or pass --latest.",
)
LATEST_OPTION = typer.Option(
    "--latest",
    help="Adopt the newest release of common, rather than one named.",
)
SKIP_PLUGIN_OPTION = typer.Option(
    "--skip-plugin",
    help="Leave the Claude Code plugin installed for the project as it is.",
)
KEEP_WORKTREE_OPTION = typer.Option(
    "--keep-worktree",
    help="Keep the temporary worktree when a step in it fails, to inspect.",
)
SKIP_FAST_FORWARD_OPTION = typer.Option(
    "--skip-fast-forward",
    help="Leave the checkout's default branch as it is once the pull request merges.",
)


def adopted_version_or_exit(
    github: GitHub,
    version: str | None,
    *,
    latest: bool,
) -> str:
    """
    Return the release to adopt: *version*, or common's newest with --latest.

    Exits 2 unless exactly one of them is given, and 1 when common has no release.
    """
    match version, latest:
        case None, True:
            try:
                newest = pins.latest_release(github)
            except GitHubError as error:
                warn(error.detail)
                raise typer.Exit(1) from None
            if newest is None:
                warn(f"{pins.COMMON.slug} has no release to adopt.")
                raise typer.Exit(1)
            say(f"Adopting the newest release of {pins.COMMON.slug}: {newest}.")
            return newest
        case str() as named, False:
            return _version(named)
        case _:
            warn("Give the release to adopt as X.Y.Z, or pass --latest; not both.")
            raise typer.Exit(2)


def _version(version: str) -> str:
    if not pins.VERSION.match(version):
        warn(f"Give the version as X.Y.Z, not {version!r}.")
        raise typer.Exit(2)
    return version


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


@app.command("check-indexes")
def check_indexes(ctx: typer.Context) -> None:
    """
    Fail when a shared guideline is missing from its directory's index (in common only).

    Each guidelines/<dir>/README.md must link to every tracked file under its directory,
    and guidelines/README.md to every directory's README.md and every top-level
    guideline: the plugin loads the indexes into every session, not the guidelines.
    """
    ensure(ctx, (requirements.GIT,))
    root = invocation(ctx).root
    top = root / indexes.GUIDELINES_DIR / indexes.INDEX
    if not top.exists():
        warn(f"{top} not found. Run it from iglootools/common, or pass --root.")
        raise typer.Exit(2)
    unlisted = indexes.find_unlisted(root)
    for item in unlisted:
        state = (
            "does not list"
            if (root / item.index).exists()
            else "is missing; add it, listing"
        )
        warn(f"{item.index} {state} {item.entry}")
    if unlisted:
        warn(
            "Add a row for each, as guidelines/documentation/writing-guidelines.md › "
            "Register a new or renamed guideline in its directory's index describes.",
        )
        raise typer.Exit(1)
    say("Every guideline is listed in its directory's index.")


def update_plugins(projects: Sequence[tuple[str, Path]], version: str) -> bool:
    """
    Bring the plugins each project enables up to date; tell whether nothing failed.

    As workspace sync does: each marketplace refreshed once, then every enabled plugin
    updated, or installed where it is missing, one project at a time. The iglootools
    plugin is then checked against the adopted *version*.
    """
    if not projects:
        return True
    try:
        synced = plugins.sync_plugins(projects, projects[0][1], dry_run=False)
    except plugin.PluginError as error:
        warn(f"Claude Code plugins not updated anywhere: {error.detail}")
        return False
    for name in synced.added:
        say(f"Added the Claude Code marketplace {name}.")
    for problem in synced.problems:
        warn(f"Claude Code plugins: {problem}")
    reported = [_report_plugin_step(step, version) for step in synced.steps]
    return not synced.problems and all(reported)


def _report_plugin_step(step: plugins.PluginStep, version: str) -> bool:
    """Say where one project's plugin ended up; tell whether that is fine."""
    name = step.project
    if step.problem:
        warn(f"{name}: {step.plugin} not updated: {step.problem}")
        return False
    if step.plugin != plugin.PLUGIN:
        say(f"{name}: {step.plugin} at {step.version}.")
        return True
    result = plugin.classify_sync(step.version, version)
    match result.sync:
        case plugin.Sync.CURRENT:
            say(
                f"{name}: Claude Code plugin at {result.installed}; restart Claude Code"
                " there, or run /reload-plugins, to load it.",
            )
            return True
        case plugin.Sync.OTHER_VERSION:
            warn(
                f"{name}: Claude Code plugin at {result.installed}, not {version}: the"
                " marketplace serves the newest release on common's default branch.",
            )
            return True
        case plugin.Sync.NOT_INSTALLED:
            warn(
                f"{name}: the Claude Code plugin was {step.action}d, but Claude Code"
                " does not list it for the project afterwards.",
            )
            return False

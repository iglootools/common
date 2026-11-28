"""The `iglootools common` commands: adopt a release, adopt it everywhere, cut one."""

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
    adopt as adoption,
    adopt_all as everywhere,
    indexes,
    pins,
    plugin,
    release as releasing,
)
from iglootools.github.cli import REPO_OPTION, github_session
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


@app.command("adopt")
def adopt(
    ctx: typer.Context,
    version: Annotated[str | None, ADOPTED_VERSION_ARGUMENT] = None,
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
    skip_plugin: Annotated[bool, SKIP_PLUGIN_OPTION] = False,
    latest: Annotated[bool, LATEST_OPTION] = False,
    in_place: Annotated[
        bool,
        typer.Option(
            "--in-place",
            help="Work in this checkout instead of a temporary worktree, to finish the "
            "branch by hand. Needs no changes and no untracked files.",
        ),
    ] = False,
    keep_worktree: Annotated[bool, KEEP_WORKTREE_OPTION] = False,
    skip_fast_forward: Annotated[bool, SKIP_FAST_FORWARD_OPTION] = False,
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
    and does nothing once the release is in place.
    """
    ensure(ctx, requirements.COMMON)
    workplace = _workplace(
        in_place=in_place,
        keep_worktree=keep_worktree,
        skip_fast_forward=skip_fast_forward,
    )
    root = invocation(ctx).root
    repository, github = github_session(ctx, repo)
    version = adopted_version_or_exit(github, version, latest=latest)
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
        warn(f"{repository.slug}: {detail}")
        raise typer.Exit(1) from None
    where = f"#{outcome.pull_number}" if outcome.pull_number else ""
    if not outcome.succeeded:
        warn(f"{repository.slug}{where}: not merged, {outcome.reason}.")
        raise typer.Exit(1)
    say(f"{repository.slug}{where}: {outcome.reason}.")
    on_release = [(repository.name, root)] if outcome.on_release else []
    if not skip_plugin and not update_plugins(on_release, version):
        raise typer.Exit(1)


def _workplace(
    *,
    in_place: bool,
    keep_worktree: bool,
    skip_fast_forward: bool,
) -> adoption.Workplace:
    """Exit 2 when --in-place comes with an option only a worktree has."""
    clashing = [
        flag
        for flag, given in (
            ("--keep-worktree", keep_worktree),
            ("--skip-fast-forward", skip_fast_forward),
        )
        if given
    ]
    if in_place and clashing:
        one = len(clashing) == 1
        warn(
            f"{' and '.join(clashing)} {'acts' if one else 'act'} on the temporary "
            "worktree, which --in-place does not make: drop "
            f"{'it' if one else 'them'}, or --in-place.",
        )
        raise typer.Exit(2)
    return adoption.Workplace(
        in_place=in_place,
        keep_worktree=keep_worktree,
        skip_fast_forward=skip_fast_forward,
    )


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

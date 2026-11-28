"""
The `iglootools repo` commands: work on the repository checked out at --root.

Each is the one-repository form of a workspace command, on the same core and options:
`repo adopt-common` of `workspace adopt-common`, `repo run` of `workspace run`. The
workspace commands run them on every repository of the organization at once.
"""

import time
from typing import Annotated

import typer

from iglootools.build import cli as build_cli
from iglootools.cliwiring import ensure, invocation, say, warn
from iglootools.common import (
    adopt as adoption,
    adopt_all as everywhere,
    cli as common_cli,
    pins,
    plugin,
)
from iglootools.github.cli import REPO_OPTION, github_session
from iglootools.github.client import GitHubError
from iglootools.github.local import GitStepError
from iglootools.preflight import requirements

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
    in_place: Annotated[
        bool,
        typer.Option(
            "--in-place",
            help="Work in this checkout instead of a temporary worktree, to finish the "
            "branch by hand. Needs no changes and no untracked files.",
        ),
    ] = False,
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
        warn(f"{repository.slug}: {detail}")
        raise typer.Exit(1) from None
    where = f"#{outcome.pull_number}" if outcome.pull_number else ""
    if not outcome.succeeded:
        warn(f"{repository.slug}{where}: not merged, {outcome.reason}.")
        raise typer.Exit(1)
    say(f"{repository.slug}{where}: {outcome.reason}.")
    on_release = [(repository.name, root)] if outcome.on_release else []
    if not skip_plugin and not common_cli.update_plugins(on_release, version):
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
        warn(issue)
    if issues:
        raise typer.Exit(1)
    versions = sorted({r.version for r in found if r.version})
    if not found:
        say("No pins on iglootools/common.")
        return
    checked = " and uv.lock" if lock else ""
    say(f"{len(found)} pins on iglootools/common, all at v{versions[0]}{checked}.")

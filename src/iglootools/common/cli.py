import time
from typing import Annotated

import typer

from iglootools.cliwiring import display_path, invocation, say, warn
from iglootools.common import adopt as adoption
from iglootools.common import pins
from iglootools.github.cli import REPO_OPTION, github_session
from iglootools.github.client import GitHubError
from iglootools.github.local import GitStepError

app = typer.Typer(
    help="Maintain a project's link to iglootools/common.", no_args_is_help=True
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
    no_merge: Annotated[
        bool, typer.Option("--no-merge", help="Open the pull request, do not merge it.")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", "-n", help="Show the pins that would move.")
    ] = False,
) -> None:
    """Move every pin on iglootools/common to a release, through a pull request.

    Moves the reusable workflows (to the release's commit), the iglootools command, the
    Renovate presets and IGLOOTOOLS_VERSION, and regenerates uv.lock where there is one.
    Then opens a pull request and merges it once every check has passed, as
    merge-when-green does.
    """
    version = _version(version)
    root = invocation(ctx).root
    repository, github = github_session(ctx, repo)
    try:
        found = adoption.plan(root, github, version)
        if not found.changed:
            say(f"Already on iglootools {version}: nothing to move.")
            return
        for path, rewritten in found.files.items():
            label = "[dry-run] Would move" if dry_run else "Moving"
            say(f"{label} {rewritten.changed} pin(s) in {display_path(path, root)}")
        if dry_run:
            for line in adoption.steps(root, found, merge_it=not no_merge):
                say(f"[dry-run] {line}")
            return
        outcome = adoption.adopt(
            root,
            github,
            repository,
            found,
            merge_it=not no_merge,
            report=say,
            sleep=time.sleep,
            now=time.monotonic,
        )
    except (GitHubError, GitStepError) as error:
        warn(f"{repository.slug}: {getattr(error, 'detail', error)}")
        raise typer.Exit(1) from None
    if no_merge or outcome.merged:
        say(f"{repository.slug}#{outcome.pull_number}: {outcome.reason}.")
        return
    warn(f"{repository.slug}#{outcome.pull_number}: not merged, {outcome.reason}.")
    raise typer.Exit(1)

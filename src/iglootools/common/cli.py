import time
from typing import Annotated

import typer

from iglootools.cliwiring import ensure, invocation, say, warn
from iglootools.common import adopt as adoption
from iglootools.common import pins
from iglootools.common import release as releasing
from iglootools.github.cli import REPO_OPTION, github_session
from iglootools.github.client import GitHubError
from iglootools.github.local import GitStepError
from iglootools.preflight import requirements

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
    merge-when-green does. Safe to run again: it picks up from the pull request or branch
    an earlier run left, and does nothing once the release is in place. Needs a checkout
    with no changes and no untracked files.
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
                root, github, repository, found, merge_it=not no_merge
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
    dry_run: Annotated[
        bool, typer.Option("--dry-run", "-n", help="Say what it would do, and stop.")
    ] = False,
) -> None:
    """Cut a release of iglootools/common: bump, merge once green, tag both ways.

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
    except (GitHubError, GitStepError, ValueError) as error:
        warn(f"{repository.slug}: {getattr(error, 'detail', error)}")
        raise typer.Exit(1) from None
    where = f"#{outcome.pull_number}" if outcome.pull_number else ""
    if not outcome.released:
        warn(f"{repository.slug}{where}: not released, {outcome.reason}.")
        raise typer.Exit(1)
    say(f"{repository.slug}{where}: {outcome.reason}.")


@app.command("check-pins")
def check_pins(ctx: typer.Context) -> None:
    """Fail when the project's pins on iglootools/common disagree or adopt would miss one.

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

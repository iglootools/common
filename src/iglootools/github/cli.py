import os
import time
from typing import Annotated

import typer

from iglootools.cliwiring import invocation, say, warn
from iglootools.github import local, merge
from iglootools.github.client import (
    GitHub,
    GitHubError,
    Repository,
    origin_repository,
    parse_slug,
    resolve_token,
)

app = typer.Typer(
    help="Work with the project's GitHub repository.", no_args_is_help=True
)

REPO_OPTION = typer.Option(
    "--repo", help="owner/name of the repository; default: the origin remote."
)


def _repository(ctx: typer.Context, slug: str | None) -> Repository:
    if slug is not None:
        match parse_slug(slug):
            case None:
                warn(f"--repo takes owner/name, not {slug!r}.")
                raise typer.Exit(2)
            case repository:
                return repository
    try:
        return origin_repository(invocation(ctx).root)
    except GitHubError as error:
        warn(f"{error.detail}.")
        raise typer.Exit(2) from None


def _preview_merge(
    github: GitHub, repository: Repository, pr: int, *, delete_branch: bool
) -> None:
    try:
        found = merge.preview(github, repository, pr)
    except GitHubError as error:
        warn(f"{repository.slug}#{pr}: {error.detail}")
        raise typer.Exit(1) from None
    for line in merge.describe(found, delete_branch=delete_branch):
        say(f"[dry-run] {repository.slug}#{pr}: {line}")
    if found.verdict.action == merge.Action.REFUSE:
        raise typer.Exit(1)


def _is_origin(ctx: typer.Context, repository: Repository) -> bool:
    """Whether the checkout under --root is a clone of *repository*."""
    try:
        return origin_repository(invocation(ctx).root) == repository
    except GitHubError:
        return False


def _github(ctx: typer.Context) -> GitHub:
    try:
        return GitHub(resolve_token(invocation(ctx).root, environ=os.environ))
    except GitHubError as error:
        warn(f"No GitHub token: {error.detail}.")
        raise typer.Exit(2) from None


@app.command("merge-when-green")
def merge_when_green(
    ctx: typer.Context,
    pr: Annotated[int, typer.Argument(help="Number of the pull request.", min=1)],
    repo: Annotated[str | None, REPO_OPTION] = None,
    timeout: Annotated[
        int, typer.Option(help="Give up after this many seconds.", min=1)
    ] = 1800,
    keep_branch: Annotated[
        bool, typer.Option("--keep-branch", help="Do not delete the branch.")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", "-n", help="Say what it would do, and stop.")
    ] = False,
) -> None:
    """Merge a pull request once every check has passed, then delete its branch.

    Waits until every check on the head commit has reported, including the ones a
    ruleset requires that have not started yet. Refuses when a check fails or GitHub
    blocks the merge for another reason. Merges with a merge commit, deletes the branch
    on GitHub, and, when the checkout has it, locally too.
    """
    repository = _repository(ctx, repo)
    github = _github(ctx)
    if dry_run:
        _preview_merge(github, repository, pr, delete_branch=not keep_branch)
        return
    try:
        outcome = merge.merge_when_green(
            github,
            repository,
            pr,
            sleep=time.sleep,
            now=time.monotonic,
            report=lambda reason: say(f"{repository.slug}#{pr}: {reason}"),
            timeout=timeout,
            delete_branch=not keep_branch,
        )
    except GitHubError as error:
        warn(f"{repository.slug}#{pr}: {error.detail}")
        raise typer.Exit(1) from None
    if not outcome.merged:
        warn(f"{repository.slug}#{pr}: not merged, {outcome.reason}.")
        raise typer.Exit(1)
    say(f"{repository.slug}#{pr}: {outcome.reason}.")
    if outcome.branch_deleted:
        say(f"Deleted {outcome.pull.head_ref} on GitHub.")
    if outcome.branch_deleted and _is_origin(ctx, repository):
        cleanup = local.clean_local(
            invocation(ctx).root, outcome.pull.head_ref, outcome.pull.base_ref
        )
        if cleanup.switched_to_base:
            say(f"Switched to an up-to-date {outcome.pull.base_ref}.")
        if cleanup.deleted:
            say(f"Deleted the local {outcome.pull.head_ref}.")
        if cleanup.problem:
            warn(f"Local cleanup stopped: {cleanup.problem}")

"""The `iglootools workspace` commands: work on every project of the organization."""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from iglootools.cliwiring import (
    ensure,
    invocation,
    resolve_workspace_or_exit,
    say,
    warn,
)
from iglootools.github.cli import github_client
from iglootools.github.client import GitHub, GitHubError
from iglootools.preflight import requirements
from iglootools.workspace import clone, parallel
from iglootools.workspace.repositories import (
    OrganizationRepository,
    list_repositories,
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


@dataclass(frozen=True)
class _Session:
    """The workspace, a GitHub client, and the repositories to work on."""

    workspace: Path
    github: GitHub
    repositories: list[OrganizationRepository]


def _session(ctx: typer.Context) -> _Session:
    """
    Find the workspace and list the organization's repositories, or exit.

    Archived repositories are left out, and said so: they take no change.
    """
    ensure(ctx, requirements.GITHUB)
    workspace = resolve_workspace_or_exit(invocation(ctx).root)
    github = github_client(ctx)
    try:
        found = list_repositories(github)
    except GitHubError as error:
        warn(error.detail)
        raise typer.Exit(1) from None
    archived = [repository.name for repository in found if repository.archived]
    if archived:
        say(f"Skipping archived: {', '.join(archived)}.")
    return _Session(
        workspace,
        github,
        [repository for repository in found if not repository.archived],
    )


@app.command("clone")
def clone_cmd(
    ctx: typer.Context,
    *,
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
    session = _session(ctx)
    results = clone_all(
        session.workspace,
        session.repositories,
        fetch=fetch,
        dry_run=dry_run,
    )
    if not _print_clone(results, dry_run=dry_run):
        raise typer.Exit(1)


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

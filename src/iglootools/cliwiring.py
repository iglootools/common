"""What every sub-command shares: the invocation, output, the project and preflight."""

import os
import shlex
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from iglootools.preflight import requirements
from iglootools.project import Project, ProjectError, ProjectErrorKind, load_project
from iglootools.workspace.location import (
    ENVIRONMENT_VARIABLE,
    SENTINEL,
    WorkspaceError,
    WorkspaceErrorKind,
    WorkspaceSource,
    resolve_workspace,
)

console = Console(highlight=False)


class OutputFormat(StrEnum):
    """What a command that prints a result prints it as."""

    HUMAN = "human"
    JSON = "json"


OUTPUT_OPTION = Annotated[
    OutputFormat,
    typer.Option("--output", "-o", help="Print the result as human text or JSON."),
]
FILE_OPTION = Annotated[
    Path | None,
    typer.Option("--file", "-f", help="Write the result to this file, not stdout."),
]


def emit(text: str, file: Path | None) -> None:
    """Write *text* to *file*, as UTF-8 with a final newline, or print it as is."""
    if file is None:
        say(text)
    else:
        file.write_text(f"{text}\n", encoding="utf-8")


err_console = Console(stderr=True, highlight=False)


@dataclass(frozen=True)
class Invocation:
    """What the root command was given, shared with every subcommand."""

    root: Path


class MissingInvocationError(RuntimeError):
    """The root callback did not store an Invocation before a subcommand ran."""

    def __init__(self, obj: object) -> None:
        """Build the error from what ctx.obj held instead of an Invocation."""
        super().__init__(f"root callback did not run: ctx.obj is {obj!r}")
        self.obj = obj


def invocation(ctx: typer.Context) -> Invocation:
    """
    Return what the root command stored for *ctx*'s sub-command.

    Raises MissingInvocationError when the root callback did not run.
    """
    match ctx.find_root().obj:
        case Invocation() as found:
            return found
        case other:
            raise MissingInvocationError(other)


def display_path(path: Path, root: Path) -> str:
    """*path* relative to *root* when it is inside it, as given otherwise."""
    return str(path.relative_to(root)) if path.is_relative_to(root) else str(path)


def say(text: str) -> None:
    """
    Print plain text as is.

    No markup, because paths and names may contain square brackets, which Rich would
    read as tags and drop. No wrapping, because a path broken across two lines can no
    longer be copied and pasted.
    """
    console.print(text, markup=False, soft_wrap=True)


def warn(text: str) -> None:
    """Print plain text as is to stderr, without markup or wrapping, as say() does."""
    err_console.print(text, markup=False, soft_wrap=True)


def project(ctx: typer.Context) -> Project:
    """
    Return the project under --root.

    Exits 1, saying what is wrong with its pyproject.toml, when it cannot be loaded.
    """
    root = invocation(ctx).root
    try:
        return load_project(root)
    except ProjectError as error:
        warn(_describe_project_error(error, root))
        raise typer.Exit(1) from None


def _describe_project_error(error: ProjectError, root: Path) -> str:
    where = display_path(error.path, root)
    match error.kind:
        case ProjectErrorKind.NO_PYPROJECT:
            return (
                f"{where} not found. Run iglootools from the project root, "
                "or pass --root."
            )
        case ProjectErrorKind.NO_PROJECT_NAME:
            return (
                f"{where} has no [project] name. Set [tool.iglootools] package to the "
                "import name of the project's package."
            )
        case ProjectErrorKind.INVALID_SETTING:
            return f"{where}: {error.setting} in [tool.iglootools] has the wrong type."


def ensure(ctx: typer.Context, needed: Sequence[requirements.Requirement]) -> None:
    """
    Exit 1, saying how to fix each, unless every one of *needed* is met.

    Called by a subsystem's commands before their first change, so a missing tool stops
    them before any branch, pull request or tag exists.
    """
    missing = [
        result
        for result in requirements.check(
            needed,
            invocation(ctx).root,
            environ=os.environ,
        )
        if not result.ok
    ]
    for result in missing:
        warn(
            f"Missing {result.requirement.name} ({result.detail}): it "
            f"{result.requirement.purpose}. Fix: {result.requirement.fix}.",
        )
    if missing:
        warn("Run `iglootools preflight` to check everything.")
        raise typer.Exit(1)


def resolve_workspace_or_exit(
    root: Path,
    *,
    announce: Callable[[str], None] = say,
) -> Path:
    """Return the workspace, saying what named it; exit 2, saying how to name one."""
    try:
        found = resolve_workspace(root, environ=os.environ)
    except WorkspaceError as error:
        warn(_describe_workspace_error(error))
        raise typer.Exit(2) from None
    named_by = {
        WorkspaceSource.ENVIRONMENT: f"${ENVIRONMENT_VARIABLE}",
        WorkspaceSource.SENTINEL: f"its {SENTINEL} directory",
    }[found.source]
    announce(f"Workspace: {found.path} (from {named_by}).")
    return found.path


def _describe_workspace_error(error: WorkspaceError) -> str:
    """Say why there is no workspace, and how to name one, with a path to copy."""
    # The projects most likely sit beside common, so its parent is the suggestion.
    suggested = shlex.quote(str(error.start.parent))
    # The directory first and always: an agent's shell, or an editor's task runner,
    # does not read the shell profile the variable lives in, so it sees only the
    # directory.
    mark = (
        "Mark the directory your iglootools projects are checked out in:\n"
        f"  mkdir -p {suggested}/{SENTINEL}"
    )
    override = (
        f"Optionally, to point a shell at another workspace, set "
        f"{ENVIRONMENT_VARIABLE}, which wins over the directory:\n"
        f"  export {ENVIRONMENT_VARIABLE}={suggested}"
    )
    match error.kind:
        case WorkspaceErrorKind.NOT_FOUND:
            return (
                f"No iglootools workspace: neither {error.start} nor any directory "
                f"above it holds a {SENTINEL} directory, and "
                f"${ENVIRONMENT_VARIABLE} is not set.\n{mark}\n{override}"
            )
        case WorkspaceErrorKind.RELATIVE:
            return (
                f"${ENVIRONMENT_VARIABLE} is {error.configured!r}, a relative path. "
                f"Set it to an absolute one, or unset it to use the {SENTINEL} "
                f"directory:\n  export {ENVIRONMENT_VARIABLE}={suggested}\n{mark}"
            )
        case WorkspaceErrorKind.NOT_A_DIRECTORY:
            return (
                f"${ENVIRONMENT_VARIABLE} is {error.configured!r}, which is not a "
                f"directory. Point it at the workspace, or unset it to use the "
                f"{SENTINEL} directory.\n{mark}"
            )

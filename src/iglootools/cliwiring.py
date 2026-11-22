"""What every sub-command shares: the invocation, output, the project and preflight."""

import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console

from iglootools.preflight import requirements
from iglootools.project import Project, ProjectError, ProjectErrorKind, load_project

console = Console(highlight=False)
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

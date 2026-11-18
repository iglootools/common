from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console

from iglootools.project import Project, ProjectError, ProjectErrorKind, load_project

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)


@dataclass(frozen=True)
class Invocation:
    """What the root command was given, shared with every subcommand."""

    root: Path


def invocation(ctx: typer.Context) -> Invocation:
    match ctx.find_root().obj:
        case Invocation() as found:
            return found
        case other:
            raise RuntimeError(f"root callback did not run: ctx.obj is {other!r}")


def display_path(path: Path, root: Path) -> str:
    """*path* relative to *root* when it is inside it, as given otherwise."""
    return str(path.relative_to(root)) if path.is_relative_to(root) else str(path)


def say(text: str) -> None:
    """Print plain text as is.

    No markup, because paths and names may contain square brackets, which Rich would read
    as tags and drop. No wrapping, because a path broken across two lines can no longer be
    copied and pasted.
    """
    console.print(text, markup=False, soft_wrap=True)


def warn(text: str) -> None:
    err_console.print(text, markup=False, soft_wrap=True)


def project(ctx: typer.Context) -> Project:
    """The project under --root, or exit 1 saying what is wrong with its pyproject.toml."""
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
            return f"{where} not found. Run iglootools from the project root, or pass --root."
        case ProjectErrorKind.NO_PROJECT_NAME:
            return (
                f"{where} has no [project] name. Set [tool.iglootools] package to the "
                "import name of the project's package."
            )
        case ProjectErrorKind.INVALID_SETTING:
            return f"{where}: {error.setting} in [tool.iglootools] has the wrong type."

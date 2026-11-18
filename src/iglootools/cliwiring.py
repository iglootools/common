from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console

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

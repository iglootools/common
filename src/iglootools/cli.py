from importlib.metadata import version
from pathlib import Path
from typing import Annotated

import typer

from iglootools.build import cli as build_cli
from iglootools.cliwiring import Invocation, say
from iglootools.common import cli as common_cli
from iglootools.demo import cli as demo_cli
from iglootools.docs import cli as docs_cli
from iglootools.github import cli as github_cli
from iglootools.mise import cli as mise_cli
from iglootools.python import cli as python_cli
from iglootools.shell import cli as shell_cli

app = typer.Typer(
    name="iglootools",
    help="Shared build and documentation tools for iglootools projects.",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(docs_cli.app, name="docs")
app.add_typer(python_cli.app, name="python")
app.add_typer(demo_cli.app, name="demo")
app.add_typer(mise_cli.app, name="mise")
app.add_typer(shell_cli.app, name="shell")
app.add_typer(github_cli.app, name="github")
app.add_typer(common_cli.app, name="common")
app.command(
    "build",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)(build_cli.build)


def _print_version(requested: bool) -> None:
    if requested:
        say(f"iglootools {version('iglootools')}")
        raise typer.Exit()


@app.callback()
def _root(
    ctx: typer.Context,
    root: Annotated[
        Path,
        typer.Option(
            "--root",
            help="Project root to work on.",
            exists=True,
            file_okay=False,
            resolve_path=True,
        ),
    ] = Path("."),
    _version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Print the version and exit.",
            callback=_print_version,
            is_eager=True,
        ),
    ] = False,
) -> None:
    ctx.obj = Invocation(root=root)


def main() -> None:
    app()

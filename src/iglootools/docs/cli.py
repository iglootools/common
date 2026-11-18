from pathlib import Path
from typing import Annotated

import typer

from iglootools.cliwiring import display_path, invocation, say, warn
from iglootools.docs import toc as tocs

app = typer.Typer(
    help="Generate documentation from the project and check that it is up to date.",
    no_args_is_help=True,
)


def _describe_toc_error(error: tocs.TocError, root: Path) -> str:
    where = display_path(error.path, root) if error.path else "<input>"
    match error.kind:
        case tocs.TocErrorKind.NO_SECTIONS:
            return f"{where}: no ## or ### heading to put a table of contents before."


@app.command()
def toc(
    ctx: typer.Context,
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help="List out-of-date tables of contents and exit 1; change nothing.",
        ),
    ] = False,
    add: Annotated[
        list[Path] | None,
        typer.Option(
            "--add",
            metavar="FILE",
            help="Give FILE an empty table of contents first. Repeat for several files.",
        ),
    ] = None,
) -> None:
    """Regenerate the tables of contents between <!-- toc --> and <!-- tocstop -->.

    Every Markdown file git tracks under the project root that carries the markers is
    updated from its ## and ### headings.
    """
    root = invocation(ctx).root
    if check and add:
        raise typer.BadParameter(
            "--add changes files, so it cannot be used with --check."
        )
    try:
        for path in add or []:
            tocs.add_block(path)
    except tocs.TocError as error:
        warn(_describe_toc_error(error, root))
        raise typer.Exit(1) from None

    files = tocs.files_with_toc(root)
    if check:
        out_of_date = tocs.stale(files)
        for path in out_of_date:
            warn(f"Out of date: {display_path(path, root)}")
        if out_of_date:
            warn("Run `iglootools docs toc` to regenerate.")
            raise typer.Exit(1)
        say(f"{len(files)} table(s) of contents up to date.")
    else:
        changed = tocs.regenerate(files)
        for path in changed:
            say(f"Updated {display_path(path, root)}")
        if not changed:
            say(f"{len(files)} table(s) of contents already up to date.")

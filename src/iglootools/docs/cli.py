from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from iglootools.cliwiring import display_path, invocation, project, say, warn
from iglootools.docs import depgraph as depgraphs
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


class GraphFormat(StrEnum):
    MERMAID = "mermaid"
    ASCII = "ascii"


def _describe_depgraph_error(error: depgraphs.DepgraphError, document: str) -> str:
    match error.kind:
        case depgraphs.DepgraphErrorKind.GRAPHVIZ_MISSING:
            return (
                "graphviz is not installed; pydeps needs its `dot`.\n"
                "  macOS:  brew install graphviz\n"
                "  Linux:  apt install graphviz"
            )
        case depgraphs.DepgraphErrorKind.PACKAGE_NOT_FOUND:
            return (
                f"Package {error.detail} is not importable here. Run iglootools in the "
                "project's environment (uv run), or set [tool.iglootools] package."
            )
        case depgraphs.DepgraphErrorKind.PYDEPS_FAILED:
            return f"pydeps failed:\n{error.detail}"
        case depgraphs.DepgraphErrorKind.MARKERS_MISSING:
            return (
                f"{document} has no Module Overview markers. Add these two lines where "
                f"the section goes:\n  {depgraphs.BEGIN_MARKER}\n  {depgraphs.END_MARKER}"
            )


@app.command()
def depgraph(
    ctx: typer.Context,
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help="Exit 1 if the Module Overview is out of date; change nothing.",
        ),
    ] = False,
    fmt: Annotated[
        GraphFormat | None,
        typer.Option("--format", "-f", help="Print the graph in this format instead."),
    ] = None,
) -> None:
    """Regenerate the Module Overview graph in the architecture document from pydeps.

    Needs graphviz installed, and runs in the project's environment so that pydeps can
    import the package.
    """
    proj = project(ctx)
    document = proj.docs.architecture
    shown = display_path(document, proj.root)
    try:
        package_dir = depgraphs.package_directory(proj.package)
        excludes = [
            *proj.docs.depgraph_exclude,
            *depgraphs.third_party_imports(proj.requirements),
        ]
        dot = depgraphs.run_pydeps(depgraphs.pydeps_command(package_dir, excludes))
        mermaid = depgraphs.to_mermaid(
            depgraphs.parse_dot(dot),
            is_package=lambda label: (package_dir / label / "__init__.py").exists(),
        )
        match fmt:
            case GraphFormat.MERMAID:
                say(mermaid)
                return
            case GraphFormat.ASCII:
                say(depgraphs.to_ascii(mermaid))
                return
            case None:
                pass
        current = document.read_text(encoding="utf-8") if document.exists() else ""
        expected = depgraphs.splice(current, depgraphs.module_overview(mermaid))
    except depgraphs.DepgraphError as error:
        warn(_describe_depgraph_error(error, shown))
        raise typer.Exit(1) from None

    if check:
        if current != expected:
            warn(f"The Module Overview in {shown} is out of date.")
            warn("Run `iglootools docs depgraph` to regenerate.")
            raise typer.Exit(1)
        say(f"The Module Overview in {shown} is up to date.")
    elif current != expected:
        document.write_text(expected, encoding="utf-8")
        say(f"Updated the Module Overview in {shown}")
    else:
        say(f"The Module Overview in {shown} is already up to date.")

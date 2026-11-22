"""The `iglootools docs` commands: the CLI reference, the module graph, the TOCs."""

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from iglootools.cliwiring import display_path, invocation, project, say, warn
from iglootools.docs import clidocs
from iglootools.docs import depgraph as depgraphs
from iglootools.docs import toc as tocs
from iglootools.project import Project

app = typer.Typer(
    help="Generate documentation from the project and check that it is up to date.",
    no_args_is_help=True,
)


class AddWithCheckError(typer.BadParameter):
    """--add was given with --check, which changes nothing."""

    def __init__(self) -> None:
        """Build the error; it has no fields."""
        super().__init__("--add changes files, so it cannot be used with --check.")


def _describe_toc_error(error: tocs.TocError, root: Path) -> str:
    where = display_path(error.path, root) if error.path else "<input>"
    match error.kind:
        case tocs.TocErrorKind.NO_SECTIONS:
            return f"{where}: no ## or ### heading to put a table of contents before."


@app.command()
def toc(
    ctx: typer.Context,
    *,
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help="List missing, duplicated and out-of-date tables of contents and "
            "exit 1; change nothing.",
        ),
    ] = False,
    add: Annotated[
        list[Path] | None,
        typer.Option(
            "--add",
            metavar="FILE",
            help="Give FILE an empty table of contents first, even if it is exempt. "
            "Repeat for several files.",
        ),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option(
            "--exclude",
            metavar="GLOB",
            help="Let files matching GLOB, relative to the project root, go without a "
            "table of contents (`content/**`). Repeat for several globs.",
        ),
    ] = None,
    min_lines: Annotated[
        int,
        typer.Option(
            "--min-lines",
            metavar="N",
            help="Require a table of contents only in documents of at least N lines.",
        ),
    ] = tocs.MIN_LINES,
) -> None:
    """
    Give every Markdown document a table of contents, and keep each one up to date.

    Every Markdown file git tracks under the project root that has a ## or ### heading
    and runs to --min-lines lines needs one block between <!-- toc --> and <!-- tocstop
    -->, filled from those headings. A shorter file's block, if it has one, is kept up
    to date. Exempt: AGENTS.md, CLAUDE.md and SKILL.md, which agents read whole; whole
    generated files, which start with <!-- AUTO-GENERATED; and files matching --exclude.
    Without --check, a missing block is added.
    """
    root = invocation(ctx).root
    if check and add:
        raise AddWithCheckError
    try:
        for path in add or []:
            tocs.add_block(path)
    except tocs.TocError as error:
        warn(_describe_toc_error(error, root))
        raise typer.Exit(1) from None

    found = tocs.survey(root, exclude or [], min_lines)
    for path in found.duplicated:
        warn(
            f"More than one table of contents: {display_path(path, root)}; "
            "remove all but the first.",
        )
    if check:
        out_of_date = tocs.stale(found.with_toc)
        for path in found.missing:
            warn(f"No table of contents: {display_path(path, root)}")
        for path in out_of_date:
            warn(f"Out of date: {display_path(path, root)}")
        if found.missing or out_of_date:
            warn(
                "Run `iglootools docs toc` to add and regenerate them, or exempt a "
                "file with --exclude.",
            )
        if found.missing or out_of_date or found.duplicated:
            raise typer.Exit(1)
        say(f"{len(found.with_toc)} table(s) of contents up to date.")
    else:
        for path in found.missing:
            tocs.add_block(path)
            say(f"Added a table of contents to {display_path(path, root)}")
        changed = tocs.regenerate([*found.with_toc, *found.missing])
        for path in changed:
            if path not in found.missing:
                say(f"Updated {display_path(path, root)}")
        if not changed:
            say(f"{len(found.with_toc)} table(s) of contents already up to date.")
        if found.duplicated:
            raise typer.Exit(1)


class GraphFormat(StrEnum):
    """How `docs depgraph` prints the module graph."""

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
                f"the section goes:\n  {depgraphs.BEGIN_MARKER}"
                f"\n  {depgraphs.END_MARKER}"
            )


@app.command()
def depgraph(
    ctx: typer.Context,
    *,
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
    """
    Regenerate the Module Overview graph in the architecture document from pydeps.

    Needs graphviz installed, and runs in the project's environment so that pydeps can
    import the package.
    """
    proj = project(ctx)
    document = proj.docs.architecture
    shown = display_path(document, proj.root)
    try:
        mermaid = _module_graph(proj)
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


def _module_graph(proj: Project) -> str:
    """Draw the package's module graph, as Mermaid, from pydeps."""
    package_dir = depgraphs.package_directory(proj.package)
    excludes = [
        *proj.docs.depgraph_exclude,
        *depgraphs.third_party_imports(proj.requirements),
    ]
    dot = depgraphs.run_pydeps(depgraphs.pydeps_command(package_dir, excludes))
    return depgraphs.to_mermaid(
        depgraphs.parse_dot(dot),
        is_package=lambda label: (package_dir / label / "__init__.py").exists(),
    )


@app.command("cli")
def cli_reference(
    ctx: typer.Context,
    *,
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help="Exit 1 if the CLI reference is out of date; change nothing.",
        ),
    ] = False,
) -> None:
    """
    Regenerate the CLI reference from the project's Typer app.

    Runs `typer <cli-module> utils docs` in the project's environment, so the module
    must be importable there.
    """
    proj = project(ctx)
    document = proj.docs.cli_reference
    shown = display_path(document, proj.root)
    try:
        expected = clidocs.generate(
            clidocs.typer_docs_command(proj.docs.cli_module, proj.docs.cli_name),
        )
    except clidocs.ClidocsError as error:
        warn(f"typer utils docs failed for {proj.docs.cli_module}:\n{error.detail}")
        raise typer.Exit(1) from None
    current = document.read_text(encoding="utf-8") if document.exists() else ""

    if check:
        if current != expected:
            warn(f"The CLI reference in {shown} is out of date.")
            warn("Run `iglootools docs cli` to regenerate.")
            raise typer.Exit(1)
        say(f"The CLI reference in {shown} is up to date.")
    elif current != expected:
        document.parent.mkdir(parents=True, exist_ok=True)
        document.write_text(expected, encoding="utf-8")
        say(f"Updated {shown}")
    else:
        say(f"{shown} is already up to date.")

"""The `iglootools python` commands: build, clean, reinstall, versions."""

from datetime import UTC, datetime
from pathlib import Path
from textwrap import indent
from typing import Annotated

import typer

from iglootools.cliwiring import display_path, invocation, project, say, warn
from iglootools.python import devversion, environment, verifyversion

app = typer.Typer(
    help="Build and check a Python project managed with uv.",
    no_args_is_help=True,
)


def _describe_error(error: verifyversion.VerifyVersionError, root: Path) -> str:
    wheel = display_path(error.wheel, root)
    match error.kind:
        case verifyversion.VerifyVersionErrorKind.NO_METADATA:
            return f"{wheel} has no .dist-info/METADATA; it is not a valid wheel."
        case verifyversion.VerifyVersionErrorKind.NO_VERSION_FIELD:
            return f"{wheel}: its METADATA has no Version field."


@app.command("verify-version")
def verify_version(
    ctx: typer.Context,
    dist_dir: Annotated[
        Path,
        typer.Option("--dist-dir", help="Directory holding the built wheels."),
    ] = Path("dist"),
) -> None:
    """
    Fail if a built wheel carries the dynamic-versioning fallback version.

    The fallback is [tool.uv-dynamic-versioning] fallback-version in pyproject.toml. A
    wheel that carries it was built without git history or tags.
    """
    proj = project(ctx)
    if proj.fallback_version is None:
        warn(
            "pyproject.toml sets no [tool.uv-dynamic-versioning] fallback-version, "
            "so there is no fallback version to guard against.",
        )
        raise typer.Exit(1)
    directory = dist_dir if dist_dir.is_absolute() else proj.root / dist_dir
    shown = display_path(directory, proj.root)
    try:
        versions = verifyversion.wheel_versions(directory)
    except verifyversion.VerifyVersionError as error:
        warn(_describe_error(error, proj.root))
        raise typer.Exit(1) from None

    # An empty directory fails rather than passing silently, or the guard is defeated by
    # the very situation it exists to catch: a build that did not produce its wheels.
    if not versions:
        warn(f"No wheel found in {shown}/, so there is nothing to verify.")
        raise typer.Exit(1)
    for found in versions:
        say(f"{found.wheel.name}: {found.version}")
    fallbacks = [f for f in versions if f.version == proj.fallback_version]
    if fallbacks:
        warn(
            f"\n{len(fallbacks)} wheel(s) carry fallback-version "
            f"{proj.fallback_version}, so the build could not see git tags or history:",
        )
        warn(
            indent(
                "\n".join(display_path(f.wheel, proj.root) for f in fallbacks),
                "  ",
            ),
        )
        warn(
            "\nCheck that the checkout has full history and tags "
            "(fetch-depth: 0, fetch-tags: true).",
        )
        raise typer.Exit(1)


def _failed(error: environment.EnvironmentCommandError) -> typer.Exit:
    warn(f"{' '.join(error.command)} failed with exit status {error.status}.")
    return typer.Exit(1)


@app.command()
def build(ctx: typer.Context) -> None:
    """
    Build the sdist and wheel into an emptied dist/.

    Check the result with `iglootools python verify-version`.
    """
    proj = project(ctx)
    try:
        built = environment.build(proj.root)
    except environment.EnvironmentCommandError as error:
        raise _failed(error) from None
    for path in built:
        say(f"Built {display_path(path, proj.root)}")


@app.command()
def clean(ctx: typer.Context) -> None:
    """Delete build/, dist/, *.egg-info and Python bytecode outside .venv."""
    root = project(ctx).root
    artifacts = environment.build_artifacts(root)
    environment.remove(artifacts)
    say(f"Removed {len(artifacts)} build artifact(s).")


@app.command()
def reinstall(ctx: typer.Context) -> None:
    """
    Delete .venv and reinstall the locked dependencies from scratch.

    Only needed for an environment changed by hand, such as with `uv pip install`; mise
    already re-syncs whenever uv.lock or pyproject.toml changes.
    """
    proj = project(ctx)
    try:
        environment.reinstall(proj.root)
    except environment.EnvironmentCommandError as error:
        raise _failed(error) from None
    say("Reinstalled .venv from uv.lock.")


@app.command("dev-version")
def dev_version_cmd(ctx: typer.Context) -> None:
    """
    Print a throwaway version for a Test PyPI rehearsal: <last release>.dev<UTC time>.

    The last release is the nearest v* tag reachable from HEAD, 0.0.0 without one.
    publish-test.yml passes it to the build as UV_DYNAMIC_VERSIONING_BYPASS.
    """
    root = invocation(ctx).root
    say(
        devversion.compute_dev_version(
            devversion.latest_release_tag(root),
            datetime.now(UTC),
        ),
    )

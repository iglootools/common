import tempfile
from pathlib import Path
from typing import Annotated

import typer

from iglootools.cliwiring import display_path, project, say, warn
from iglootools.demo import upload as uploads
from iglootools.project import DemoSettings

app = typer.Typer(help="Publish the project's terminal demo.", no_args_is_help=True)


def _describe(error: uploads.DemoError, settings: DemoSettings) -> str:
    command = " ".join(error.command)
    match error.kind:
        case uploads.DemoErrorKind.TOOL_MISSING:
            return (
                f"{error.command[0]} not found. Install it, usually through mise.toml."
            )
        case uploads.DemoErrorKind.COMMAND_FAILED:
            return f"{command} failed:\n{error.detail}"
        case uploads.DemoErrorKind.NO_SUCCESSFUL_RUN:
            return (
                f"No successful run of {settings.workflow} found. Trigger one with "
                f"`gh workflow run {settings.workflow}`, or record locally and upload "
                "with `asciinema upload`."
            )
        case uploads.DemoErrorKind.NO_CAST_IN_ARTIFACT:
            return (
                f"No {settings.cast} in the {settings.artifact} artifact of run "
                f"{error.detail}."
            )
        case uploads.DemoErrorKind.UPLOAD_FAILED:
            return (
                f"asciinema upload failed:\n{error.detail}\n"
                "If it timed out, check that this machine can reach asciinema.org: "
                "GitHub-hosted runners cannot, which is why this command exists."
            )


@app.command("upload")
def upload_command(
    ctx: typer.Context,
    run_id: Annotated[
        str | None,
        typer.Option(
            "--run-id", help="Upload from this workflow run instead of the newest."
        ),
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Download and report; do not upload.")
    ] = False,
    update_readme: Annotated[
        bool,
        typer.Option(
            "--readme/--no-readme",
            help="Point the README's asciicast embed at the new recording.",
        ),
    ] = True,
    commit: Annotated[
        bool, typer.Option("--commit/--no-commit", help="Commit the README change.")
    ] = True,
) -> None:
    """Download the demo recorded by CI and upload it to asciinema.org.

    Takes the newest successful run of the demo workflow, preferring main, uploads its cast,
    then points the README's embed at the recording and commits that file alone.
    """
    proj = project(ctx)
    settings = proj.demo
    readme = settings.readme
    shown = display_path(readme, proj.root)
    try:
        readme_was_dirty = (
            update_readme
            and commit
            and uploads.has_uncommitted_changes(readme, proj.root)
        )
        workflow_run = (
            uploads.view_run(run_id) if run_id else uploads.latest_run(settings)
        )
        say(
            f"Run {workflow_run.run_id}:\n  {workflow_run.created_at}  "
            f"{workflow_run.branch}  {workflow_run.title}"
        )
        with tempfile.TemporaryDirectory() as workdir:
            cast = uploads.download_cast(settings, workflow_run, Path(workdir))
            say(f"Title: {uploads.cast_title(cast) or '(none)'}")
            if dry_run:
                say(f"Dry run: not uploading {cast.name}.")
                return
            output = uploads.upload(cast)
        say(output.rstrip("\n"))
    except uploads.DemoError as error:
        warn(_describe(error, settings))
        raise typer.Exit(1) from None

    if not update_readme:
        return
    url = uploads.recording_url(output)
    if url is None:
        warn(
            "The upload succeeded, but asciinema's output holds no recording URL, so "
            f"{shown} was left alone. Update its embed by hand."
        )
        raise typer.Exit(1)
    _repoint_readme(readme, shown, url)
    if not commit:
        say(f"Not committing: `git add {shown}` and commit when ready.")
        return
    if readme_was_dirty:
        warn(
            f"{shown} had uncommitted changes before this run, so it was not committed: "
            "a pathspec commit would take those too. Review the diff and commit it."
        )
        raise typer.Exit(1)
    try:
        say(f"Committed {uploads.commit_readme(readme, url, workflow_run, proj.root)}")
    except uploads.DemoError as error:
        warn(_describe(error, settings))
        raise typer.Exit(1) from None


def _repoint_readme(readme: Path, shown: str, url: str) -> None:
    if not readme.exists():
        warn(
            f"{shown} not found, so the embed cannot be updated. The upload succeeded."
        )
        raise typer.Exit(1)
    result = uploads.apply_embed(readme.read_text(encoding="utf-8"), url)
    if not result.found:
        warn(
            f"No asciicast embed in {shown}; expected a line like\n"
            f"  {uploads.render_embed(url)}\n"
            "The upload succeeded: add or fix that line by hand."
        )
        raise typer.Exit(1)
    if not result.changed:
        say(f"{shown} already points at this recording.")
        raise typer.Exit(0)
    readme.write_text(result.content, encoding="utf-8")
    say(f"Updated {shown}")

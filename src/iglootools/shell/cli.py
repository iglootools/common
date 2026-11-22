"""The `iglootools shell` commands: lint the project's shell scripts."""

import typer

from iglootools.cliwiring import invocation, say, warn
from iglootools.shell import lint

app = typer.Typer(help="Check the project's shell scripts.", no_args_is_help=True)


@app.command("lint")
def lint_command(ctx: typer.Context) -> None:
    """
    Run shellcheck on every tracked shell script.

    Finds .sh and .bash files and files with an sh or bash shebang, such as mise file
    tasks, and skips files marked linguist-vendored or linguist-generated.
    """
    root = invocation(ctx).root
    scripts = lint.shell_scripts(root)
    if not scripts:
        say("No shell scripts to lint.")
        return
    say(f"Linting {len(scripts)} shell script(s) with shellcheck")
    try:
        status = lint.run_in(lint.shellcheck_command(scripts), root)
    except FileNotFoundError:
        warn('shellcheck not found. Pin it in mise.toml: shellcheck = "0.11.0".')
        raise typer.Exit(1) from None
    if status != 0:
        raise typer.Exit(status)

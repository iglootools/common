import typer

from iglootools.cliwiring import invocation, say, warn
from iglootools.mise import lockcheck

app = typer.Typer(help="Check a project's mise configuration.", no_args_is_help=True)


@app.command("lock-check")
def lock_check(ctx: typer.Context) -> None:
    """Fail if the staged mise.lock is not what `mise lock` makes of the staged mise.toml.

    Regenerates in a scratch directory, so nothing in the project changes. Stage your
    mise.toml and mise.lock first: the check reads them from the git index.
    """
    try:
        comparison = lockcheck.compare(invocation(ctx).root)
    except lockcheck.LockCheckError as error:
        match error.kind:
            case lockcheck.LockCheckErrorKind.NOT_STAGED:
                warn(
                    f"{error.detail} is not in the git index. Stage it with `git add`."
                )
            case lockcheck.LockCheckErrorKind.MISE_LOCK_FAILED:
                warn(f"mise lock failed:\n{error.detail}")
        raise typer.Exit(1) from None
    if not comparison.up_to_date:
        warn("".join(comparison.diff()).rstrip("\n"))
        warn("mise.lock is out of date. Run `mise lock` and commit the result.")
        raise typer.Exit(1)
    say("mise.lock is up to date.")

import os

import typer

from iglootools.cliwiring import invocation, say
from iglootools.preflight import requirements


def preflight(ctx: typer.Context) -> None:
    """Check that every program and credential the iglootools commands use is there.

    Each subsystem checks its own before its first change; this checks them all at once,
    with what each is for, which commands need it, and how to fix what is missing.
    """
    results = requirements.check(
        requirements.ALL, invocation(ctx).root, environ=os.environ
    )
    for result in results:
        mark = "✓" if result.ok else "✗"
        needed = ", ".join(requirements.needed_by(result.requirement))
        say(
            f"{mark} {result.requirement.name:<13} {result.detail}"
            f" — {result.requirement.purpose} (iglootools {needed})"
        )
        if not result.ok:
            say(f"  Fix: {result.requirement.fix}")
    if not all(result.ok for result in results):
        raise typer.Exit(1)

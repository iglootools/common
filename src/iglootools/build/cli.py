"""The `iglootools build` command, which runs a project's mise task by name."""

import os
import shlex
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated

import typer

from iglootools.build import tasks
from iglootools.cliwiring import ensure, invocation, say, warn
from iglootools.preflight import requirements


def build(
    ctx: typer.Context,
    task: Annotated[
        str | None,
        typer.Argument(help="The mise task to run; omit to list them."),
    ] = None,
    *,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            "-n",
            help="Print the mise command instead of running it.",
        ),
    ] = False,
    fix: Annotated[
        bool,
        typer.Option(
            "--fix",
            help="Run fmt first, so formatting alone never fails the task.",
        ),
    ] = False,
) -> None:
    """
    Run one of the project's mise tasks: preflight, lint-*, test-*, fmt, ci-*, ….

    Delegates to `mise run <task>`, passing any further arguments on, and exits with the
    task's status. With no task, lists the project's tasks by family. Options for
    iglootools build itself, such as -n and --fix, go before the task; everything after
    it goes to the task. `iglootools build --fix preflight` formats the files first, so
    formatting alone never fails preflight.
    """
    ensure(ctx, requirements.BUILD)
    root = invocation(ctx).root
    try:
        available = tasks.list_tasks(root)
    except tasks.TaskListError as error:
        warn(f"Could not list the mise tasks: {error}")
        raise typer.Exit(1) from None
    if task is None:
        for title, members in tasks.by_family(available):
            say(f"{title}:")
            for member in members:
                say(f"  {member.name:<22} {member.description}")
        return
    names = {member.name for member in available}
    if task not in names:
        warn(f"No mise task named {task!r}. Run `iglootools build` to list them.")
        raise typer.Exit(2)
    if fix and tasks.FIX_TASK not in names:
        warn(f"--fix runs the mise task {tasks.FIX_TASK!r}, which this project lacks.")
        raise typer.Exit(2)
    if dry_run:
        _show(task, ctx.args, fix=fix)
        return
    raise typer.Exit(_run(root, task, ctx.args, fix=fix))


def _show(task: str, args: Sequence[str], *, fix: bool) -> None:
    if fix:
        fmt = shlex.join(tasks.mise_command(tasks.FIX_TASK, []))
        say(f"[dry-run] Would run: {fmt}")
    say(f"[dry-run] Would run: {shlex.join(tasks.mise_command(task, args))}")


def _run(root: Path, task: str, args: Sequence[str], *, fix: bool) -> int:
    if not fix:
        return tasks.run_task(root, task, args)
    fixed = tasks.run_task_fixing(root, task, args)
    _report(root, fixed.reformatted)
    return fixed.status


def _report(root: Path, reformatted: tuple[Path, ...] | None) -> None:
    match reformatted:
        case None:
            warn(
                f"{tasks.FIX_TASK} may have rewritten files; outside a git working"
                " tree, iglootools cannot tell which.",
            )
        case ():
            pass
        case files:
            warn(f"{tasks.FIX_TASK} reformatted {len(files)} file(s); commit them:")
            for file in files:
                warn(f"  {os.path.relpath(file, root)}")

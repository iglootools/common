import shlex
from typing import Annotated

import typer

from iglootools.build import tasks
from iglootools.cliwiring import invocation, say, warn


def build(
    ctx: typer.Context,
    task: Annotated[
        str | None, typer.Argument(help="The mise task to run; omit to list them.")
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", "-n", help="Print the mise command instead of running it."
        ),
    ] = False,
) -> None:
    """Run one of the project's mise tasks: preflight, lint-*, test-*, fmt, ci-*, ….

    Delegates to `mise run <task>`, passing any further arguments on, and exits with the
    task's status. With no task, lists the project's tasks by family. Options for
    iglootools build itself, such as -n, go before the task; everything after it goes to
    the task.
    """
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
    if task not in {member.name for member in available}:
        warn(f"No mise task named {task!r}. Run `iglootools build` to list them.")
        raise typer.Exit(2)
    if dry_run:
        say(f"[dry-run] Would run: {shlex.join(tasks.mise_command(task, ctx.args))}")
        return
    raise typer.Exit(tasks.run_task(root, task, ctx.args))

"""
Run one mise task in every checkout of the workspace, and say where it passed.

Each task's output goes to a log file of its own rather than the terminal, where
several running at once would interleave; a failure shows the end of its log. A
repository that is not cloned, or whose project has no such task, is skipped.

The task runs in its project's environment, not in the one `iglootools` itself runs
in: that one is common's, and its virtual environment's `bin`, first on PATH, would
otherwise put common's Python and tools ahead of the project's own.
"""

import os
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from iglootools.build import tasks
from iglootools.github.client import Run
from iglootools.workspace import clone
from iglootools.workspace.repositories import OrganizationRepository

TAIL_LINES = 20

type RunLogged = Callable[[Sequence[str], Path, Path], int]
"""Runs a command in a directory, its output to a log file; returns its status."""


class RunOutcome(StrEnum):
    """How a task ended in one repository."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class TaskRun:
    """
    How a task ended in one repository.

    *detail* says why it was skipped or could not start; *log* is where its output
    went, and *tail* the end of it for a failure.
    """

    name: str
    outcome: RunOutcome
    detail: str = ""
    seconds: float = 0.0
    log: Path | None = None
    tail: list[str] = field(default_factory=list[str])


def child_environment(environ: Mapping[str, str]) -> dict[str, str]:
    """
    Return *environ* without the virtual environment and mise state of this process.

    Drops VIRTUAL_ENV and its `bin` from PATH, uv's recursion counter, and mise's
    record of the shell's activation (`__MISE_*`), so mise builds each project's
    environment from its own configuration.
    """
    venv = environ.get("VIRTUAL_ENV", "")
    path = os.pathsep.join(
        entry
        for entry in environ.get("PATH", "").split(os.pathsep)
        if not (venv and Path(entry) == Path(venv) / "bin")
    )
    return {
        **{
            key: value
            for key, value in environ.items()
            if key not in {"VIRTUAL_ENV", "UV_RUN_RECURSION_DEPTH"}
            and not key.startswith("__MISE_")
        },
        "PATH": path,
    }


def captured(environ: Mapping[str, str]) -> Run:
    """Return a runner that captures a command's output, in *environ*."""

    def run(
        command: Sequence[str],
        directory: Path,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            cwd=directory,
            capture_output=True,
            text=True,
            env=dict(environ),
            check=False,
        )

    return run


def logged(environ: Mapping[str, str]) -> RunLogged:
    """Return a runner that sends a command's output to a log, in *environ*."""

    def run(command: Sequence[str], directory: Path, log: Path) -> int:
        with log.open("w", encoding="utf-8") as handle:
            return subprocess.run(
                command,
                cwd=directory,
                stdout=handle,
                stderr=subprocess.STDOUT,
                env=dict(environ),
                check=False,
            ).returncode

    return run


def run_in(
    workspace: Path,
    repository: OrganizationRepository,
    task: str,
    args: Sequence[str],
    log_dir: Path,
    *,
    run: RunLogged,
    list_tasks: Callable[[Path], list[tasks.Task]] = tasks.list_tasks,
    now: Callable[[], float] = time.monotonic,
) -> TaskRun:
    """
    Run *task* with *args* through mise in *repository*'s checkout, if it has the task.

    Its output goes to `<log_dir>/<repository>.log`. Never raises for the task or
    mise: a failure is the outcome of the result.
    """
    path = clone.checkout_path(workspace, repository)
    if not clone.is_checkout(path):
        return TaskRun(repository.name, RunOutcome.SKIPPED, "not cloned")
    try:
        names = {found.name for found in list_tasks(path)}
    except tasks.TaskListError as error:
        return TaskRun(repository.name, RunOutcome.FAILED, f"mise: {error}")
    if task not in names:
        return TaskRun(repository.name, RunOutcome.SKIPPED, f"has no task {task!r}")
    log = log_dir / f"{repository.name}.log"
    started = now()
    status = run(tasks.mise_command(task, args), path, log)
    seconds = now() - started
    if status == 0:
        return TaskRun(repository.name, RunOutcome.PASSED, seconds=seconds, log=log)
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    return TaskRun(
        repository.name,
        RunOutcome.FAILED,
        f"exited {status}",
        seconds=seconds,
        log=log,
        tail=lines[-TAIL_LINES:],
    )

"""The project's mise tasks, by family, and running one.

The tasks are the project's own: `iglootools build` only names them uniformly and runs them
through mise, so a contributor or an agent reaches `preflight`, `lint-types` or `test` the
same way in every project. Their families follow guidelines/project-setup/mise.md › Name
tasks by family.
"""

import json
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

FAMILIES = (
    ("preflight", "Preflight"),
    ("lint", "Lint"),
    ("test", "Test"),
    ("fmt", "Format"),
    ("ci", "CI"),
)
OTHER = "Other"


@dataclass(frozen=True)
class Task:
    name: str
    description: str

    @property
    def family(self) -> str:
        return next(
            (
                title
                for prefix, title in FAMILIES
                if self.name == prefix or self.name.startswith(f"{prefix}-")
            ),
            OTHER,
        )


def parse(listing: str) -> list[Task]:
    """The visible tasks in `mise tasks ls --json` output."""
    return [
        Task(item["name"], item.get("description") or "")
        for item in json.loads(listing)
        if not item.get("hide")
    ]


def by_family(tasks: Sequence[Task]) -> list[tuple[str, list[Task]]]:
    """*tasks* grouped by family, families in their usual order, names sorted within."""
    titles = [title for _, title in FAMILIES] + [OTHER]
    return [
        (title, sorted((task for task in tasks if task.family == title), key=_name))
        for title in titles
        if any(task.family == title for task in tasks)
    ]


def _name(task: Task) -> str:
    return task.name


type Run = Callable[[Sequence[str], Path], subprocess.CompletedProcess[str]]
type Delegate = Callable[[Sequence[str], Path], int]


def capture(
    command: Sequence[str], directory: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, cwd=directory, capture_output=True, text=True, check=False
    )


def passthrough(command: Sequence[str], directory: Path) -> int:
    """Run *command* with the terminal's own output, and return its exit status."""
    return subprocess.run(command, cwd=directory, check=False).returncode


class TaskListError(RuntimeError):
    """mise could not list the project's tasks; the message is mise's."""


def list_tasks(root: Path, *, run: Run = capture) -> list[Task]:
    result = run(["mise", "tasks", "ls", "--json"], root)
    if result.returncode != 0:
        raise TaskListError(result.stderr.strip() or "mise tasks ls failed")
    return parse(result.stdout)


def run_task(
    root: Path, task: str, args: Sequence[str], *, delegate: Delegate = passthrough
) -> int:
    """Run the project's *task* through mise, passing *args* on, and return its status."""
    return delegate(mise_command(task, args), root)


def mise_command(task: str, args: Sequence[str]) -> list[str]:
    return ["mise", "run", task, *args]

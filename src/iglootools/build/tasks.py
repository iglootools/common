"""
The project's mise tasks, by family, and running one.

The tasks are the project's own: `iglootools build` only names them uniformly and runs
them through mise, so a contributor or an agent reaches `preflight`, `lint-types` or
`test` the same way in every project. Their families follow
guidelines/project-setup/mise.md › Name tasks by family.
"""

import hashlib
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
    """A mise task, as `mise tasks ls` lists it."""

    name: str
    description: str

    @property
    def family(self) -> str:
        """Return the title of the family the task's name prefix puts it in."""
        return next(
            (
                title
                for prefix, title in FAMILIES
                if self.name == prefix or self.name.startswith(f"{prefix}-")
            ),
            OTHER,
        )


def parse(listing: str) -> list[Task]:
    """Parse the visible tasks from `mise tasks ls --json` output."""
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
    command: Sequence[str],
    directory: Path,
) -> subprocess.CompletedProcess[str]:
    """Run *command* in *directory*, capturing its text output, whatever its status."""
    return subprocess.run(
        command,
        cwd=directory,
        capture_output=True,
        text=True,
        check=False,
    )


def passthrough(command: Sequence[str], directory: Path) -> int:
    """Run *command* with the terminal's own output, and return its exit status."""
    return subprocess.run(command, cwd=directory, check=False).returncode


class TaskListError(RuntimeError):
    """mise could not list the project's tasks; the message is mise's."""


def list_tasks(root: Path, *, run: Run = capture) -> list[Task]:
    """
    Return the project's visible mise tasks.

    Raises TaskListError, with mise's message, when mise cannot list them.
    """
    result = run(["mise", "tasks", "ls", "--json"], root)
    if result.returncode != 0:
        raise TaskListError(result.stderr.strip() or "mise tasks ls failed")
    return parse(result.stdout)


def run_task(
    root: Path,
    task: str,
    args: Sequence[str],
    *,
    delegate: Delegate = passthrough,
) -> int:
    """Run the project's *task* through mise, passing *args* on; return its status."""
    return delegate(mise_command(task, args), root)


FIX_TASK = "fmt"

type Snapshot = dict[Path, str]


@dataclass(frozen=True)
class Fixed:
    """
    What `iglootools build --fix` did: the last status, and the files `fmt` rewrote.

    *reformatted* is None when the project is not in a git working tree, so the files
    `fmt` rewrote could not be told apart from the ones already changed.
    """

    status: int
    reformatted: tuple[Path, ...] | None


def run_task_fixing(
    root: Path,
    task: str,
    args: Sequence[str],
    *,
    delegate: Delegate = passthrough,
    run: Run = capture,
) -> Fixed:
    """
    Run `fmt`, then *task*; return the task's status, or `fmt`'s if it fails.

    `fmt` leaves formatted files alone, so it rewrites only what `lint-fmt` or
    `lint-markdown` would have failed on: formatting first costs one `fmt` run, where
    running *task* and formatting only after a failure would run *task* twice. The
    working tree is snapshotted around `fmt` to name the files it rewrote, which then
    need committing.
    """
    before = snapshot(root, run=run)
    formatted = run_task(root, FIX_TASK, [], delegate=delegate)
    after = snapshot(root, run=run)
    rewritten = None if before is None or after is None else reformatted(before, after)
    status = (
        formatted if formatted != 0 else run_task(root, task, args, delegate=delegate)
    )
    return Fixed(status, rewritten)


def snapshot(root: Path, *, run: Run = capture) -> Snapshot | None:
    """
    Hash every file git reports as changed or untracked, by absolute path.

    A clean file is left out: if `fmt` rewrites it, it appears in the next snapshot.
    Returns None outside a git working tree.
    """
    top = run(["git", "rev-parse", "--show-toplevel"], root)
    status = run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        root,
    )
    if top.returncode != 0 or status.returncode != 0:
        return None
    base = Path(top.stdout.strip())
    files = (base / path for path in changed_paths(status.stdout))
    return {file: _digest(file) for file in files if file.is_file()}


def changed_paths(porcelain: str) -> list[str]:
    """
    Return the paths in `git status --porcelain=v1 -z` output, relative to the top.

    A rename or copy entry is followed by its source path, which is skipped: only the
    destination is in the working tree.
    """
    fields = porcelain.split("\0")
    sources = {
        index + 1 for index, field in enumerate(fields) if field[:1] in {"R", "C"}
    }
    return [
        field[3:]
        for index, field in enumerate(fields)
        if field and index not in sources
    ]


def reformatted(before: Snapshot, after: Snapshot) -> tuple[Path, ...]:
    """Return the files whose content differs from *before* to *after*, sorted."""
    return tuple(
        sorted(file for file, digest in after.items() if before.get(file) != digest),
    )


def _digest(file: Path) -> str:
    return hashlib.sha256(file.read_bytes()).hexdigest()


def mise_command(task: str, args: Sequence[str]) -> list[str]:
    """Return the `mise run` command that runs *task* with *args*."""
    return ["mise", "run", task, *args]

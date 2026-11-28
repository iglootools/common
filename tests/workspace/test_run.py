import os
from collections.abc import Callable, Sequence
from pathlib import Path

from iglootools.build import tasks
from iglootools.workspace import run
from iglootools.workspace.repositories import OrganizationRepository
from iglootools.workspace.run import RunOutcome, TaskRun

NBKP = OrganizationRepository(
    "nbkp",
    archived=False,
    default_branch="main",
    ssh_url="",
    https_url="",
)


def test_the_child_environment_drops_this_process_s_venv_and_mise_state() -> None:
    venv = "/w/common/.venv"
    environ = {
        "VIRTUAL_ENV": venv,
        "PATH": os.pathsep.join([f"{venv}/bin", "/w/nbkp/.venv/bin", "/usr/bin"]),
        "UV_RUN_RECURSION_DEPTH": "1",
        "__MISE_DIFF": "x",
        "__MISE_SESSION": "y",
        "MISE_TRUSTED_CONFIG_PATHS": "/w",
        "HOME": "/home/me",
    }
    assert run.child_environment(environ) == {
        "PATH": os.pathsep.join(["/w/nbkp/.venv/bin", "/usr/bin"]),
        "MISE_TRUSTED_CONFIG_PATHS": "/w",
        "HOME": "/home/me",
    }


class FakeRun:
    """Write the given output to the log, and return the given status."""

    def __init__(self, status: int, output: str) -> None:
        self.status = status
        self.output = output
        self.commands: list[list[str]] = []

    def __call__(self, command: Sequence[str], _directory: Path, log: Path) -> int:
        self.commands.append(list(command))
        log.write_text(self.output, encoding="utf-8")
        return self.status


def _checkout(tmp_path: Path) -> Path:
    (tmp_path / "nbkp" / ".git").mkdir(parents=True)
    (tmp_path / "logs").mkdir()
    return tmp_path


def _listing(*names: str) -> Callable[[Path], list[tasks.Task]]:
    def list_tasks(_root: Path) -> list[tasks.Task]:
        return [tasks.Task(name, "") for name in names]

    return list_tasks


def _run_in(workspace: Path, fake: FakeRun, *names: str) -> TaskRun:
    clock = iter([10.0, 13.0])
    return run.run_in(
        workspace,
        NBKP,
        "preflight",
        ["--verbose"],
        workspace / "logs",
        run=fake,
        list_tasks=_listing(*names),
        now=lambda: next(clock),
    )


def test_a_passing_task_is_timed_and_logged(tmp_path: Path) -> None:
    workspace = _checkout(tmp_path)
    fake = FakeRun(0, "ok\n")
    result = _run_in(workspace, fake, "preflight")
    assert result == TaskRun(
        "nbkp",
        RunOutcome.PASSED,
        seconds=3.0,
        log=workspace / "logs" / "nbkp.log",
    )
    assert fake.commands == [["mise", "run", "preflight", "--verbose"]]


def test_a_failing_task_shows_the_end_of_its_log(tmp_path: Path) -> None:
    workspace = _checkout(tmp_path)
    output = "".join(f"line {n}\n" for n in range(30))
    result = _run_in(workspace, FakeRun(1, output), "preflight")
    assert (result.outcome, result.detail) == (RunOutcome.FAILED, "exited 1")
    assert result.tail == [f"line {n}" for n in range(10, 30)]


def test_a_project_without_the_task_is_skipped(tmp_path: Path) -> None:
    fake = FakeRun(0, "")
    result = _run_in(_checkout(tmp_path), fake, "lint")
    assert result == TaskRun("nbkp", RunOutcome.SKIPPED, "has no task 'preflight'")
    assert fake.commands == []


def test_a_repository_not_cloned_is_skipped(tmp_path: Path) -> None:
    result = _run_in(tmp_path, FakeRun(0, ""), "preflight")
    assert result == TaskRun("nbkp", RunOutcome.SKIPPED, "not cloned")

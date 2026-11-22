import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from iglootools.build import tasks
from iglootools.build.tasks import Task

LISTING = json.dumps(
    [
        {"name": "test", "description": "Run the tests"},
        {"name": "lint-types", "description": "Type-check"},
        {"name": "preflight-quick", "description": "Lints and fast tests"},
        {"name": "ci-preflight", "description": "What CI runs"},
        {"name": "fmt", "description": "Format"},
        {"name": "toc", "description": "Tables of contents"},
        {"name": "lint", "description": "Every lint"},
        {"name": "secret-helper", "description": "Hidden", "hide": True},
        {"name": "testkit", "description": "Not a test-* task"},
    ],
)


def test_hidden_tasks_are_left_out() -> None:
    assert "secret-helper" not in {task.name for task in tasks.parse(LISTING)}


@pytest.mark.parametrize(
    ("name", "family"),
    [
        ("preflight", "Preflight"),
        ("preflight-quick", "Preflight"),
        ("lint-fmt-ruff", "Lint"),
        ("test-integration", "Test"),
        ("fmt", "Format"),
        ("ci-build", "CI"),
        ("testkit", "Other"),
        ("toc", "Other"),
    ],
)
def test_a_task_s_family_follows_its_name(name: str, family: str) -> None:
    assert Task(name, "").family == family


def test_families_come_in_their_usual_order_with_names_sorted() -> None:
    grouped = tasks.by_family(tasks.parse(LISTING))
    assert [(title, [task.name for task in members]) for title, members in grouped] == [
        ("Preflight", ["preflight-quick"]),
        ("Lint", ["lint", "lint-types"]),
        ("Test", ["test"]),
        ("Format", ["fmt"]),
        ("CI", ["ci-preflight"]),
        ("Other", ["testkit", "toc"]),
    ]


def test_a_task_runs_through_mise_with_its_arguments_and_status(tmp_path: Path) -> None:
    seen: list[list[str]] = []

    def delegate(command: Sequence[str], _directory: Path) -> int:
        seen.append(list(command))
        return 3

    assert (
        tasks.run_task(tmp_path, "toc", ["--add", "docs/new.md"], delegate=delegate)
        == 3
    )
    assert seen == [["mise", "run", "toc", "--add", "docs/new.md"]]


def test_a_failing_listing_is_an_error(tmp_path: Path) -> None:
    def run(
        command: Sequence[str],
        _directory: Path,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, "", "mise: no config")

    with pytest.raises(tasks.TaskListError, match="no config"):
        tasks.list_tasks(tmp_path, run=run)


def test_the_dry_run_command_is_the_one_a_run_would_use() -> None:
    assert tasks.mise_command("test", ["-k", "slugs"]) == [
        "mise",
        "run",
        "test",
        "-k",
        "slugs",
    ]

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


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _repository(root: Path) -> None:
    _git(root, "init", "-q")
    (root / "clean.md").write_text("clean\n", encoding="utf-8")
    (root / "edited.md").write_text("edited\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(
        root,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-qm",
        "init",
    )
    (root / "edited.md").write_text("edited by hand\n", encoding="utf-8")


def _formatting(
    root: Path,
    rewrites: Sequence[str],
    statuses: dict[str, int],
    seen: list[str],
) -> tasks.Delegate:
    def delegate(command: Sequence[str], _directory: Path) -> int:
        seen.append(command[2])
        if command[2] == "fmt":
            for name in rewrites:
                (root / name).write_text("formatted\n", encoding="utf-8")
        return statuses[command[2]]

    return delegate


def test_fixing_formats_then_runs_the_task_once(tmp_path: Path) -> None:
    _repository(tmp_path)
    seen: list[str] = []
    fixed = tasks.run_task_fixing(
        tmp_path,
        "preflight",
        [],
        delegate=_formatting(tmp_path, [], {"fmt": 0, "preflight": 4}, seen),
    )
    assert (fixed, seen) == (tasks.Fixed(4, ()), ["fmt", "preflight"])


def test_a_failing_fmt_stops_before_the_task(tmp_path: Path) -> None:
    _repository(tmp_path)
    seen: list[str] = []
    fixed = tasks.run_task_fixing(
        tmp_path,
        "preflight",
        [],
        delegate=_formatting(tmp_path, [], {"fmt": 2, "preflight": 0}, seen),
    )
    assert (fixed.status, seen) == (2, ["fmt"])


def test_fixing_names_the_files_fmt_rewrote_clean_or_already_edited(
    tmp_path: Path,
) -> None:
    _repository(tmp_path)
    (tmp_path / "untouched.md").write_text("new\n", encoding="utf-8")
    fixed = tasks.run_task_fixing(
        tmp_path,
        "preflight",
        [],
        delegate=_formatting(
            tmp_path,
            ["clean.md", "edited.md"],
            {"fmt": 0, "preflight": 0},
            [],
        ),
    )
    root = tmp_path.resolve()
    assert fixed.reformatted == (root / "clean.md", root / "edited.md")


def test_outside_git_the_rewritten_files_are_unknown(tmp_path: Path) -> None:
    fixed = tasks.run_task_fixing(
        tmp_path,
        "preflight",
        [],
        delegate=_formatting(tmp_path, [], {"fmt": 0, "preflight": 0}, []),
    )
    assert fixed == tasks.Fixed(0, None)


def test_a_rename_s_source_path_is_not_listed() -> None:
    porcelain = " M a.py\0R  new.md\0old.md\0?? dir/b.md\0"
    assert tasks.changed_paths(porcelain) == ["a.py", "new.md", "dir/b.md"]


def test_only_files_whose_content_changed_are_reformatted() -> None:
    before = {Path("/r/a"): "1", Path("/r/b"): "2"}
    after = {Path("/r/a"): "1", Path("/r/b"): "3", Path("/r/c"): "4"}
    assert tasks.reformatted(before, after) == (Path("/r/b"), Path("/r/c"))

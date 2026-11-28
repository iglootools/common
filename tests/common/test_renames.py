from pathlib import Path

import pytest

from iglootools.common import renames
from tests.conftest import track


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (
            'run = "uv run --no-sync iglootools common check-pins"',
            'run = "uv run --no-sync iglootools repo lint-common-pins"',
        ),
        (
            "fix with `iglootools common adopt`",
            "fix with `iglootools repo adopt-common`",
        ),
        (
            "iglootools common adopt-all --latest",
            "iglootools workspace adopt-common --latest",
        ),
        ("iglootools build --fix preflight", "iglootools repo run --fix preflight"),
        ("iglootools python build", "iglootools python build"),
        ("iglootools common release 2.5.0", "iglootools common release 2.5.0"),
        ("iglootools common adoption", "iglootools common adoption"),
    ],
)
def test_rename_replaces_whole_command_names_only(before: str, after: str) -> None:
    assert renames.rename(before)[0] == after


def test_rename_counts_every_old_name() -> None:
    text = "iglootools build; iglootools common adopt; iglootools common adopt-all\n"
    assert renames.rename(text) == (
        (
            "iglootools repo run; iglootools repo adopt-common; "
            "iglootools workspace adopt-common\n"
        ),
        3,
    )


def test_candidates_are_the_tracked_files_naming_a_command(git_repo: Path) -> None:
    task = 'run = "uv run --no-sync iglootools common check-pins"\n'
    track(git_repo, "mise.toml", task)
    track(git_repo, "README.md", "# A project\n")
    track(git_repo, "uv.lock", "iglootools build\n")
    (git_repo / "notes.md").write_text("iglootools build\n", encoding="utf-8")
    assert renames.candidate_files(git_repo) == [git_repo / "mise.toml"]

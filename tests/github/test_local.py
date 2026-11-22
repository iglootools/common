import subprocess
from collections.abc import Sequence
from pathlib import Path

from iglootools.github import local


class FakeGit:
    def __init__(
        self, current: str, has_branch: bool = True, delete_status: int = 0
    ) -> None:
        self.current = current
        self.has_branch = has_branch
        self.delete_status = delete_status
        self.commands: list[list[str]] = []

    def __call__(
        self, command: Sequence[str], directory: Path
    ) -> subprocess.CompletedProcess[str]:
        self.commands.append(list(command))
        match list(command):
            case ["git", "branch", "--show-current"]:
                return subprocess.CompletedProcess(command, 0, f"{self.current}\n", "")
            case ["git", "show-ref", *_]:
                return subprocess.CompletedProcess(
                    command, 0 if self.has_branch else 1, "", ""
                )
            case ["git", "branch", "-q", "-d", _]:
                return subprocess.CompletedProcess(
                    command, self.delete_status, "", "error: not fully merged"
                )
            case _:
                return subprocess.CompletedProcess(command, 0, "", "")


def test_leaves_the_merged_branch_for_an_updated_base_then_deletes_it(
    tmp_path: Path,
) -> None:
    git = FakeGit(current="docs/x")
    cleanup = local.clean_local(tmp_path, "docs/x", "main", run=git)
    assert cleanup == local.LocalCleanup(switched_to_base=True, deleted=True)
    assert git.commands[1:4] == [
        ["git", "switch", "-q", "main"],
        ["git", "pull", "-q", "--ff-only"],
        ["git", "show-ref", "-q", "--verify", "refs/heads/docs/x"],
    ]


def test_a_branch_with_unmerged_commits_is_kept_and_reported(tmp_path: Path) -> None:
    cleanup = local.clean_local(
        tmp_path, "docs/x", "main", run=FakeGit(current="main", delete_status=1)
    )
    assert not cleanup.deleted and "not fully merged" in cleanup.problem


def test_a_branch_never_checked_out_needs_nothing(tmp_path: Path) -> None:
    cleanup = local.clean_local(
        tmp_path, "docs/x", "main", run=FakeGit(current="main", has_branch=False)
    )
    assert cleanup == local.LocalCleanup(switched_to_base=False, deleted=False)

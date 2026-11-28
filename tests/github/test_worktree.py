from pathlib import Path

import pytest

from iglootools.github import local, worktree
from iglootools.github.worktree import FastForwardAction
from tests.conftest import advance_origin, commit, git


def _dirs(tmp_path: Path) -> worktree.MakeDirFn:
    def make(prefix: str) -> Path:
        path = tmp_path / f"{prefix}x"
        path.mkdir()
        return path

    return make


class TestTemporaryWorktree:
    def test_the_worktree_is_removed_and_the_checkout_untouched(
        self,
        clone: Path,
        tmp_path: Path,
    ) -> None:
        (clone / "notes.txt").write_text("work in progress", encoding="utf-8")
        with worktree.temporary_worktree(
            clone,
            "origin/main",
            name="adopt-nbkp",
            keep_on_failure=False,
            make_dir_fn=_dirs(tmp_path),
        ) as path:
            assert path.name == "iglootools-adopt-nbkp-x"
            assert (path / "first").is_file()
            git(path, "switch", "-q", "-c", "chore/x")
        assert not path.exists()
        assert "chore/x" in git(clone, "branch")
        assert git(clone, "branch", "--show-current").strip() == "main"
        assert (clone / "notes.txt").is_file()

    def test_a_failure_removes_the_worktree_by_default(
        self,
        clone: Path,
        tmp_path: Path,
    ) -> None:
        with (
            pytest.raises(RuntimeError) as raised,
            worktree.temporary_worktree(
                clone,
                "origin/main",
                name="adopt",
                keep_on_failure=False,
                make_dir_fn=_dirs(tmp_path),
            ) as path,
        ):
            raise RuntimeError
        assert not path.exists()
        assert not getattr(raised.value, "__notes__", [])

    def test_a_failure_keeps_the_worktree_when_asked_and_says_where(
        self,
        clone: Path,
        tmp_path: Path,
    ) -> None:
        with (
            pytest.raises(RuntimeError) as raised,
            worktree.temporary_worktree(
                clone,
                "origin/main",
                name="adopt",
                keep_on_failure=True,
                make_dir_fn=_dirs(tmp_path),
            ) as path,
        ):
            raise RuntimeError
        assert (path / "first").is_file()
        assert raised.value.__notes__ == [f"The worktree is kept at {path}."]

    def test_a_start_git_cannot_check_out_leaves_no_directory(
        self,
        clone: Path,
        tmp_path: Path,
    ) -> None:
        with (
            pytest.raises(local.GitStepError),
            worktree.temporary_worktree(
                clone,
                "origin/no-such-branch",
                name="adopt",
                keep_on_failure=False,
                make_dir_fn=_dirs(tmp_path),
            ),
        ):
            pass
        assert not (tmp_path / "iglootools-adopt-x").exists()


@pytest.mark.parametrize(
    ("up_to_date", "behind_only", "checked_out", "clean", "action"),
    [
        (True, True, True, False, FastForwardAction.UP_TO_DATE),
        (False, False, False, True, FastForwardAction.DIVERGED),
        (False, True, False, False, FastForwardAction.MOVE_REF),
        (False, True, True, True, FastForwardAction.MERGE),
        (False, True, True, False, FastForwardAction.HAS_CHANGES),
    ],
)
def test_plan_fast_forward_moves_only_what_holds_no_one_s_work(
    *,
    up_to_date: bool,
    behind_only: bool,
    checked_out: bool,
    clean: bool,
    action: FastForwardAction,
) -> None:
    assert (
        worktree.plan_fast_forward(
            up_to_date=up_to_date,
            behind_only=behind_only,
            checked_out=checked_out,
            clean=clean,
        )
        == action
    )


class TestFastForward:
    def test_a_clean_checkout_on_main_is_merged_forward(self, clone: Path) -> None:
        head = advance_origin(clone)
        result = worktree.fast_forward(clone, "main")
        assert result.action == FastForwardAction.MERGE
        assert git(clone, "rev-parse", "main").strip() == head
        assert (clone / "second").is_file()

    def test_main_checked_out_nowhere_has_only_its_ref_moved(self, clone: Path) -> None:
        head = advance_origin(clone)
        git(clone, "switch", "-q", "-c", "feature")
        result = worktree.fast_forward(clone, "main")
        assert result == worktree.FastForward(FastForwardAction.MOVE_REF)
        assert git(clone, "rev-parse", "main").strip() == head
        assert not (clone / "second").exists()

    def test_a_checkout_with_changes_is_left_alone(self, clone: Path) -> None:
        advance_origin(clone)
        before = git(clone, "rev-parse", "main")
        (clone / "first").write_text("edited", encoding="utf-8")
        result = worktree.fast_forward(clone, "main")
        assert result.action == FastForwardAction.HAS_CHANGES
        assert result.checkout is not None
        assert result.checkout.resolve() == clone.resolve()
        assert git(clone, "rev-parse", "main") == before

    def test_main_with_commits_origin_lacks_is_left_alone(self, clone: Path) -> None:
        advance_origin(clone)
        commit(clone, "local")
        before = git(clone, "rev-parse", "main")
        assert worktree.fast_forward(clone, "main").action == FastForwardAction.DIVERGED
        assert git(clone, "rev-parse", "main") == before

    def test_main_already_on_origin_s_is_up_to_date(self, clone: Path) -> None:
        assert (
            worktree.fast_forward(clone, "main").action == FastForwardAction.UP_TO_DATE
        )

    def test_a_dry_run_says_what_it_would_do_and_moves_nothing(
        self,
        clone: Path,
    ) -> None:
        advance_origin(clone)
        git(clone, "fetch", "-q", "origin")
        before = git(clone, "rev-parse", "main")
        result = worktree.fast_forward(clone, "main", dry_run=True)
        assert result.action == FastForwardAction.MERGE
        assert git(clone, "rev-parse", "main") == before

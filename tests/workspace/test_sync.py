import json
from collections.abc import Mapping
from pathlib import Path

from iglootools.github.client import GitHub
from iglootools.workspace import sync
from iglootools.workspace.repositories import OrganizationRepository
from iglootools.workspace.sync import KeptBranch
from tests.conftest import UnexpectedCallError, commit, git

REPOSITORY = OrganizationRepository(
    "nbkp",
    archived=False,
    default_branch="main",
    ssh_url="",
    https_url="",
)


class FakeGitHub:
    """Answers what prune.gather and prune.delete_remote ask, from a table of pulls."""

    def __init__(
        self,
        remote: list[str],
        pulls: Mapping[str, Mapping[str, object]],
    ) -> None:
        self.remote = remote
        self.pulls = pulls
        self.deleted: list[str] = []

    def __call__(
        self,
        method: str,
        url: str,
        _headers: Mapping[str, str],
        _body: bytes | None,
    ) -> tuple[int, bytes]:
        path = url.removeprefix("https://api.github.com/repos/iglootools/nbkp")
        if (method, path) == ("GET", ""):
            return 200, b'{"default_branch": "main"}'
        if method == "GET" and path.startswith("/branches?"):
            names = ["main", *self.remote] if path.endswith("page=1") else []
            return 200, json.dumps([{"name": name} for name in names]).encode()
        if method == "GET" and path.startswith("/pulls?"):
            branch = path.split("head=iglootools:", 1)[1].split("&", 1)[0]
            found = self.pulls.get(branch)
            return 200, json.dumps([found] if found else []).encode()
        if method == "GET" and path.startswith("/compare/"):
            return 200, b'{"ahead_by": 0}'
        if method == "DELETE" and path.startswith("/git/refs/heads/"):
            self.deleted.append(path.removeprefix("/git/refs/heads/"))
            return 204, b""
        raise UnexpectedCallError((method, path))


MERGED: Mapping[str, object] = {
    "number": 7,
    "state": "closed",
    "merged_at": "2026-11-27T00:00:00Z",
}
OPEN: Mapping[str, object] = {"number": 8, "state": "open", "merged_at": None}


def _merged_branch(clone: Path, name: str) -> None:
    """Push *name* with a commit, then merge it into origin's main from elsewhere."""
    git(clone, "switch", "-q", "-c", name)
    commit(clone, name.replace("/", "-"))
    git(clone, "push", "-q", "-u", "origin", name)
    merger = clone.parent / f"merger-{name.replace('/', '-')}"
    git(clone.parent, "clone", "-q", str(clone.parent / "origin.git"), str(merger))
    git(merger, "merge", "-q", "--ff-only", f"origin/{name}")
    git(merger, "push", "-q", "origin", "main")


def _sync(
    clone: Path,
    github: FakeGitHub,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> sync.SyncResult:
    return sync.sync_one(
        clone,
        REPOSITORY,
        GitHub("t", transport=github),
        force=force,
        dry_run=dry_run,
    )


def test_a_merged_branch_is_left_for_an_up_to_date_main_and_deleted(
    clone: Path,
) -> None:
    _merged_branch(clone, "feat/x")
    github = FakeGitHub(["feat/x"], {"feat/x": MERGED})
    result = _sync(clone, github)
    assert result.done == [
        "switched from feat/x to main",
        "fast-forwarded main",
        "deleted feat/x on GitHub (#7 merged)",
        "deleted the local feat/x (#7 merged)",
    ]
    assert result.problems == []
    assert github.deleted == ["feat/x"]
    assert git(clone, "branch", "--show-current").strip() == "main"
    assert git(clone, "rev-parse", "main") == git(clone, "rev-parse", "origin/main")
    assert "feat/x" not in git(clone, "branch")


def test_a_dry_run_says_the_same_and_changes_nothing(clone: Path) -> None:
    _merged_branch(clone, "feat/x")
    git(clone, "fetch", "-q", "origin")
    github = FakeGitHub(["feat/x"], {"feat/x": MERGED})
    result = _sync(clone, github, dry_run=True)
    assert result.done == [
        "would switch from feat/x to main",
        "would fast-forward main",
        "would delete feat/x on GitHub (#7 merged)",
        "would delete the local feat/x (#7 merged)",
    ]
    assert github.deleted == []
    assert git(clone, "branch", "--show-current").strip() == "feat/x"


def test_uncommitted_changes_keep_the_checkout_where_it_is(clone: Path) -> None:
    _merged_branch(clone, "feat/x")
    (clone / "notes.txt").write_text("wip", encoding="utf-8")
    github = FakeGitHub(["feat/x"], {"feat/x": MERGED})
    result = _sync(clone, github)
    assert git(clone, "branch", "--show-current").strip() == "feat/x"
    assert result.problems == [
        "has uncommitted changes on feat/x; left as it is",
        "kept the local feat/x: it is checked out",
    ]
    assert "fast-forwarded main" in result.done


def test_a_branch_with_an_open_pull_request_is_kept_and_reported(
    clone: Path,
) -> None:
    git(clone, "switch", "-q", "-c", "feat/y")
    commit(clone, "y")
    git(clone, "switch", "-q", "main")
    github = FakeGitHub([], {"feat/y": OPEN})
    result = _sync(clone, github)
    assert result.kept == [KeptBranch("feat/y", "local", "#8 open")]
    assert result.done == []
    assert result.problems == []


def test_a_merged_branch_with_local_commits_is_kept_locally(clone: Path) -> None:
    _merged_branch(clone, "feat/x")
    commit(clone, "unpushed")
    git(clone, "switch", "-q", "main")
    github = FakeGitHub(["feat/x"], {"feat/x": MERGED})
    result = _sync(clone, github)
    assert "deleted feat/x on GitHub (#7 merged)" in result.done
    assert any(
        problem.startswith("kept the local feat/x: ") for problem in result.problems
    )
    assert "feat/x" in git(clone, "branch")


def test_other_worktrees_are_listed_relative_to_the_checkout(clone: Path) -> None:
    git(clone, "worktree", "add", "-q", "-b", "agent", ".claude/worktrees/a")
    git(clone, "worktree", "lock", ".claude/worktrees/a")
    result = _sync(clone, FakeGitHub([], {}))
    assert result.worktrees == [".claude/worktrees/a on agent (locked)"]
    assert result.kept == [KeptBranch("agent", "local", "no pull request")]


def test_a_clean_checkout_on_unmerged_work_stays_with_a_warning(clone: Path) -> None:
    git(clone, "switch", "-q", "-c", "feat/y")
    commit(clone, "y")
    result = _sync(clone, FakeGitHub([], {"feat/y": OPEN}))
    assert git(clone, "branch", "--show-current").strip() == "feat/y"
    assert result.warnings == [
        "left on feat/y (#8 open), which has not merged; --force switches it to main",
    ]
    assert result.problems == []


def test_force_switches_a_clean_checkout_off_unmerged_work(clone: Path) -> None:
    git(clone, "switch", "-q", "-c", "feat/y")
    commit(clone, "y")
    result = _sync(clone, FakeGitHub([], {"feat/y": OPEN}), force=True)
    assert git(clone, "branch", "--show-current").strip() == "main"
    assert result.done[0] == "switched from feat/y to main"
    assert result.kept == [KeptBranch("feat/y", "local", "#8 open")]

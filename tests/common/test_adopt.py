import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from iglootools.common import adopt
from iglootools.common.adopt import Result, Start
from iglootools.github.client import GitHub, Repository
from iglootools.github.events import Event
from iglootools.github.local import GitStepError, GitStepFailureKind
from tests.conftest import UnexpectedCallError, commit, git

REPO = Repository("iglootools", "nbkp")
SHA = "b" * 40
OLD = "a" * 40
BRANCH = "chore/iglootools-1.33.1"


@pytest.mark.parametrize(
    ("local_branch", "remote_branch", "start"),
    [
        (False, False, Start.NEW),
        (True, False, Start.LOCAL),
        (False, True, Start.REMOTE),
        (True, True, Start.REMOTE),
    ],
)
def test_a_run_picks_up_from_the_branch_an_earlier_run_left(
    *,
    local_branch: bool,
    remote_branch: bool,
    start: Start,
) -> None:
    assert (
        adopt.where_to_start(local_branch=local_branch, remote_branch=remote_branch)
        == start
    )


class FakeGitHub:
    def __init__(self, pulls: list[dict[str, object]] | None = None) -> None:
        self.pulls = pulls or []
        self.opened: dict[str, str] = {}

    def __call__(
        self,
        method: str,
        url: str,
        _headers: Mapping[str, str],
        body: bytes | None,
    ) -> tuple[int, bytes]:
        path = url.removeprefix("https://api.github.com")
        if (method, path) == ("GET", "/repos/iglootools/nbkp"):
            return 200, b'{"default_branch": "main"}'
        if method == "GET" and path.startswith("/repos/iglootools/nbkp/pulls?"):
            assert f"head=iglootools:{BRANCH}" in path
            return 200, json.dumps(self.pulls).encode()
        if (method, path) == ("POST", "/repos/iglootools/nbkp/pulls"):
            self.opened = json.loads(body or b"{}")
            return 201, b'{"number": 42}'
        raise UnexpectedCallError((method, path))


class FakeTools:
    """Fake git and uv on a project whose files the test writes; record each command."""

    def __init__(
        self,
        *,
        status: str = "",
        local_branch: bool = False,
        remote_branch: bool = False,
        hijacked: str | None = None,
    ) -> None:
        self.status = status
        self.local_branch = local_branch
        self.remote_branch = remote_branch
        self.hijacked = hijacked
        self.current = "main"
        self.commands: list[list[str]] = []
        self.directories: list[tuple[list[str], Path]] = []

    def ran_in(self, directory: Path) -> list[list[str]]:
        """Return the commands run in *directory*."""
        return [command for command, where in self.directories if where == directory]

    def __call__(
        self,
        command: Sequence[str],
        directory: Path,
    ) -> subprocess.CompletedProcess[str]:
        self.commands.append(list(command))
        self.directories.append((list(command), directory))
        match list(command):
            case ["git", "status", "--porcelain"]:
                return subprocess.CompletedProcess(command, 0, self.status, "")
            case ["git", "switch", *_, branch] | ["git", "switch", *_, branch, _]:
                self.current = branch.removeprefix("origin/")
                return subprocess.CompletedProcess(command, 0, "", "")
            case ["git", "branch", "--show-current"]:
                current = self.hijacked if self.hijacked is not None else self.current
                return subprocess.CompletedProcess(command, 0, f"{current}\n", "")
            case ["git", "show-ref", *_]:
                return subprocess.CompletedProcess(
                    command,
                    0 if self.local_branch else 1,
                    "",
                    "",
                )
            case ["git", "ls-remote", "--heads", "origin", _]:
                out = f"{OLD}\trefs/heads/{BRANCH}\n" if self.remote_branch else ""
                return subprocess.CompletedProcess(command, 0, out, "")
            case ["git", "ls-files", "-z"]:
                names = [
                    p.relative_to(directory).as_posix()
                    for p in directory.rglob("*")
                    if p.is_file()
                ]
                return subprocess.CompletedProcess(command, 0, "\0".join(names), "")
            case ["git", "diff", "--cached", "--quiet"]:
                return subprocess.CompletedProcess(command, 1, "", "")
            case _:
                return subprocess.CompletedProcess(command, 0, "", "")


def _project(tmp_path: Path, version: str = "1.33.0") -> Path:
    (tmp_path / "renovate.json").write_text(
        f'"github>iglootools/common//renovate/base#v{version}"\n',
    )
    (tmp_path / "uv.lock").write_text("lock")
    return tmp_path


IN_PLACE = adopt.Workplace(in_place=True)


def _adopt(
    root: Path,
    github: FakeGitHub,
    tools: FakeTools,
    events: list[Event],
    *,
    workplace: adopt.Workplace = IN_PLACE,
    worktree_dir: Path | None = None,
) -> adopt.Outcome:
    def make_dir(_prefix: str) -> Path:
        assert worktree_dir is not None, "an in-place adopt made a worktree"
        return worktree_dir

    return adopt.adopt(
        root,
        GitHub("t", transport=github),
        REPO,
        "1.33.1",
        SHA,
        merge_it=False,
        report=events.append,
        sleep=lambda _seconds: None,
        now=lambda: 0.0,
        run=tools,
        workplace=workplace,
        make_dir_fn=make_dir,
    )


def test_a_first_run_branches_moves_locks_pushes_and_opens(tmp_path: Path) -> None:
    root = _project(tmp_path)
    github, tools = FakeGitHub(), FakeTools()
    events: list[Event] = []
    outcome = _adopt(root, github, tools, events)
    assert outcome == adopt.Outcome(
        Result.OPENED,
        "opened, not merged (--no-merge)",
        42,
    )
    assert "v1.33.1" in (root / "renovate.json").read_text()
    assert ["git", "switch", "-q", "-c", BRANCH] in tools.commands
    assert ["git", "add", "--", "renovate.json", "uv.lock"] in tools.commands
    assert ["git", "push", "-q", "-u", "origin", BRANCH] in tools.commands
    assert github.opened["head"] == BRANCH
    assert github.opened["base"] == "main"


def test_a_merged_pull_request_means_nothing_left_to_do(tmp_path: Path) -> None:
    github = FakeGitHub(
        [{"number": 9, "state": "closed", "merged_at": "2026-11-22T00:00:00Z"}],
    )
    tools = FakeTools()
    outcome = _adopt(_project(tmp_path), github, tools, [])
    assert outcome == adopt.Outcome(Result.UP_TO_DATE, "already merged in #9", 9)
    assert not [
        c for c in tools.commands if c[:2] in (["git", "switch"], ["git", "push"])
    ]


def test_a_pull_request_closed_without_merging_is_refused(tmp_path: Path) -> None:
    github = FakeGitHub([{"number": 9, "state": "closed", "merged_at": None}])
    outcome = _adopt(_project(tmp_path), github, FakeTools(), [])
    assert outcome.result == Result.REFUSED
    assert "closed without merging" in outcome.reason


def test_an_open_pull_request_is_resumed_without_touching_the_branch(
    tmp_path: Path,
) -> None:
    github = FakeGitHub([{"number": 9, "state": "open", "merged_at": None}])
    tools = FakeTools()
    outcome = _adopt(_project(tmp_path), github, tools, [])
    assert outcome == adopt.Outcome(Result.OPENED, "opened, not merged (--no-merge)", 9)
    assert not [
        c for c in tools.commands if c[:2] in (["git", "switch"], ["git", "push"])
    ]


def test_a_branch_pushed_by_an_earlier_run_is_continued(tmp_path: Path) -> None:
    tools = FakeTools(remote_branch=True)
    outcome = _adopt(_project(tmp_path), FakeGitHub(), tools, [])
    assert outcome.result == Result.OPENED
    assert ["git", "fetch", "-q", "origin", BRANCH] in tools.commands
    assert ["git", "switch", "-q", "-C", BRANCH, f"origin/{BRANCH}"] in tools.commands


def test_a_project_already_on_a_newer_release_is_not_moved_back(tmp_path: Path) -> None:
    tools = FakeTools()
    outcome = _adopt(_project(tmp_path, version="1.34.0"), FakeGitHub(), tools, [])
    assert outcome.result == Result.REFUSED
    assert "newer 1.34.0" in outcome.reason
    assert not [c for c in tools.commands if c[:2] == ["git", "push"]]


def test_untracked_files_stop_it_before_anything_changes(tmp_path: Path) -> None:
    with pytest.raises(GitStepError) as raised:
        _adopt(_project(tmp_path), FakeGitHub(), FakeTools(status="?? notes.txt\n"), [])
    assert raised.value.kind == GitStepFailureKind.UNCLEAN_CHECKOUT


def test_a_checkout_switched_away_mid_run_is_neither_committed_nor_pushed(
    tmp_path: Path,
) -> None:
    tools = FakeTools(hijacked="chore/nuxt")
    with pytest.raises(GitStepError) as raised:
        _adopt(_project(tmp_path), FakeGitHub(), tools, [])
    assert (raised.value.kind, raised.value.branch, raised.value.current) == (
        GitStepFailureKind.SWITCHED_BRANCH,
        BRANCH,
        "chore/nuxt",
    )
    assert not [
        c for c in tools.commands if c[:2] in (["git", "commit"], ["git", "push"])
    ]


class TestInWorktree:
    """The default: the work happens in a worktree, and the checkout is left alone."""

    def _checkout_and_worktree(self, tmp_path: Path) -> tuple[Path, Path]:
        # The fake git adds no files, so the worktree directory starts as a copy.
        (tmp_path / "checkout").mkdir()
        (tmp_path / "worktree").mkdir()
        return _project(tmp_path / "checkout"), _project(tmp_path / "worktree")

    def test_the_pins_move_in_the_worktree_and_the_checkout_is_untouched(
        self,
        tmp_path: Path,
    ) -> None:
        root, work = self._checkout_and_worktree(tmp_path)
        tools = FakeTools(status="?? notes.txt\n")
        outcome = _adopt(
            root,
            FakeGitHub(),
            tools,
            [],
            workplace=adopt.IN_WORKTREE,
            worktree_dir=work,
        )
        assert outcome.result == Result.OPENED
        assert "v1.33.1" in (work / "renovate.json").read_text()
        assert "v1.33.0" in (root / "renovate.json").read_text()
        assert tools.ran_in(root) == [
            ["git", "fetch", "-q", "origin", "main"],
            ["git", "worktree", "add", "-q", "--detach", str(work), "origin/main"],
            ["git", "worktree", "remove", "--force", str(work)],
        ]
        assert ["git", "switch", "-q", "-c", BRANCH] in tools.ran_in(work)
        assert ["git", "push", "-q", "-u", "origin", BRANCH] in tools.ran_in(work)

    def test_uv_lock_runs_with_the_worktree_trusted_by_mise(
        self,
        tmp_path: Path,
    ) -> None:
        root, work = self._checkout_and_worktree(tmp_path)
        tools = FakeTools()
        _adopt(
            root,
            FakeGitHub(),
            tools,
            [],
            workplace=adopt.IN_WORKTREE,
            worktree_dir=work,
        )
        assert [
            "env",
            f"MISE_TRUSTED_CONFIG_PATHS={work}",
            "mise",
            "exec",
            "--",
            "uv",
            "lock",
            "--upgrade-package",
            "iglootools",
        ] in tools.ran_in(work)

    def test_a_failure_in_the_worktree_removes_it(self, tmp_path: Path) -> None:
        root, work = self._checkout_and_worktree(tmp_path)
        tools = FakeTools(hijacked="chore/nuxt")
        with pytest.raises(GitStepError) as raised:
            _adopt(
                root,
                FakeGitHub(),
                tools,
                [],
                workplace=adopt.IN_WORKTREE,
                worktree_dir=work,
            )
        assert ["git", "worktree", "remove", "--force", str(work)] in tools.commands
        assert not getattr(raised.value, "__notes__", [])

    def test_a_failure_keeps_the_worktree_when_asked(self, tmp_path: Path) -> None:
        root, work = self._checkout_and_worktree(tmp_path)
        tools = FakeTools(hijacked="chore/nuxt")
        with pytest.raises(GitStepError) as raised:
            _adopt(
                root,
                FakeGitHub(),
                tools,
                [],
                workplace=adopt.Workplace(keep_worktree=True),
                worktree_dir=work,
            )
        assert not [c for c in tools.commands if c[:3] == ["git", "worktree", "remove"]]
        assert raised.value.__notes__ == [f"The worktree is kept at {work}."]

    def test_an_open_pull_request_is_resumed_without_a_worktree(
        self,
        tmp_path: Path,
    ) -> None:
        github = FakeGitHub([{"number": 9, "state": "open", "merged_at": None}])
        tools = FakeTools()
        outcome = _adopt(
            _project(tmp_path),
            github,
            tools,
            [],
            workplace=adopt.IN_WORKTREE,
        )
        assert outcome.pull_number == 9
        assert not [c for c in tools.commands if c[:2] == ["git", "worktree"]]


@pytest.mark.parametrize(
    ("workplace", "present", "absent"),
    [
        (
            adopt.IN_WORKTREE,
            [
                (
                    f"Would create {BRANCH} from the default branch, up to date, "
                    "in a temporary worktree."
                ),
                "Would remove the worktree.",
                "Would fast-forward the checkout's default branch, where that is safe.",
            ],
            [],
        ),
        (
            adopt.Workplace(keep_worktree=True, skip_fast_forward=True),
            ["Would remove the worktree, or keep it if a step fails."],
            ["Would fast-forward the checkout's default branch, where that is safe."],
        ),
        (
            IN_PLACE,
            [f"Would create {BRANCH} from the default branch, up to date."],
            [
                "Would remove the worktree.",
                "Would fast-forward the checkout's default branch, where that is safe.",
            ],
        ),
    ],
)
def test_the_preview_says_where_the_work_happens(
    tmp_path: Path,
    workplace: adopt.Workplace,
    present: list[str],
    absent: list[str],
) -> None:
    root = _project(tmp_path)
    tools = FakeTools()
    lines = adopt.preview(
        root,
        GitHub("t", transport=FakeGitHub()),
        REPO,
        adopt.plan(root, "1.33.1", SHA, run=tools),
        merge_it=True,
        update_plugin=False,
        workplace=workplace,
        run=tools,
    )
    assert all(line in lines for line in present), lines
    assert not [line for line in absent if line in lines], lines


def _merged_on_origin(clone: Path, branch: str) -> str:
    """Push *branch* from *clone*, then merge and delete it on origin; return main."""
    git(clone, "switch", "-q", "-c", branch)
    commit(clone, "pins")
    git(clone, "push", "-q", "-u", "origin", branch)
    git(clone, "switch", "-q", "main")
    merger = clone.parent / "merger"
    git(clone.parent, "clone", "-q", str(clone.parent / "origin.git"), str(merger))
    git(merger, "merge", "-q", "--ff-only", f"origin/{branch}")
    git(merger, "push", "-q", "origin", "main", f":{branch}")
    return git(merger, "rev-parse", "HEAD").strip()


class TestTidyAfterMerge:
    def test_the_branch_goes_and_main_is_fast_forwarded(self, clone: Path) -> None:
        head = _merged_on_origin(clone, BRANCH)
        said = adopt.tidy_after_merge(
            clone,
            BRANCH,
            "main",
            adopt.IN_WORKTREE,
            branch_deleted=True,
        )
        assert said == "fast-forwarded main"
        assert git(clone, "rev-parse", "main").strip() == head
        assert BRANCH not in git(clone, "branch")

    def test_a_checkout_on_the_branch_keeps_it_and_is_not_switched(
        self,
        clone: Path,
    ) -> None:
        head = _merged_on_origin(clone, BRANCH)
        git(clone, "switch", "-q", BRANCH)
        said = adopt.tidy_after_merge(
            clone,
            BRANCH,
            "main",
            adopt.IN_WORKTREE,
            branch_deleted=True,
        )
        assert said == "fast-forwarded main"
        assert git(clone, "branch", "--show-current").strip() == BRANCH
        assert git(clone, "rev-parse", "main").strip() == head

    def test_main_with_changes_in_its_checkout_is_left_alone(
        self,
        clone: Path,
    ) -> None:
        _merged_on_origin(clone, BRANCH)
        before = git(clone, "rev-parse", "main")
        (clone / "first").write_text("edited", encoding="utf-8")
        said = adopt.tidy_after_merge(
            clone,
            BRANCH,
            "main",
            adopt.IN_WORKTREE,
            branch_deleted=True,
        )
        assert said.startswith("main left alone: ")
        assert said.endswith(" has changes")
        assert git(clone, "rev-parse", "main") == before

    def test_skip_fast_forward_leaves_main_and_says_nothing(self, clone: Path) -> None:
        _merged_on_origin(clone, BRANCH)
        before = git(clone, "rev-parse", "main")
        said = adopt.tidy_after_merge(
            clone,
            BRANCH,
            "main",
            adopt.Workplace(skip_fast_forward=True),
            branch_deleted=True,
        )
        assert said == ""
        assert git(clone, "rev-parse", "main") == before
        assert BRANCH not in git(clone, "branch")


def test_adopting_renames_the_commands_the_release_renamed(tmp_path: Path) -> None:
    root = _project(tmp_path)
    task = 'run = "uv run --no-sync iglootools common check-pins"'
    (root / "mise.toml").write_text(f"[tasks.lint-common-pins]\n{task}\n")
    tools = FakeTools()
    found = adopt.plan(root, "1.33.1", SHA, run=tools)
    assert {
        path.name: rewritten.describe() for path, rewritten in found.files.items()
    } == {
        "mise.toml": "1 renamed command(s)",
        "renovate.json": "1 pin(s)",
    }
    assert "iglootools repo lint-common-pins" in found.files[root / "mise.toml"].text
    lines = adopt.preview(
        root,
        GitHub("t", transport=FakeGitHub()),
        REPO,
        found,
        merge_it=False,
        update_plugin=False,
        run=tools,
    )
    assert "Would change 1 renamed command(s) in mise.toml" in lines

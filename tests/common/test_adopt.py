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
from tests.conftest import UnexpectedCallError

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

    def __call__(
        self,
        command: Sequence[str],
        directory: Path,
    ) -> subprocess.CompletedProcess[str]:
        self.commands.append(list(command))
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


def _adopt(
    root: Path,
    github: FakeGitHub,
    tools: FakeTools,
    events: list[Event],
) -> adopt.Outcome:
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

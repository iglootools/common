import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

from iglootools.common import adopt
from iglootools.common.pins import Rewrite
from iglootools.github.client import GitHub, Repository

REPO = Repository("iglootools", "nbkp")


class FakeGitHub:
    def __init__(self) -> None:
        self.opened: dict[str, str] = {}

    def __call__(
        self, method: str, url: str, headers: Mapping[str, str], body: bytes | None
    ) -> tuple[int, bytes]:
        path = url.removeprefix("https://api.github.com")
        if (method, path) == ("GET", "/repos/iglootools/nbkp"):
            return 200, b'{"default_branch": "main"}'
        if (method, path) == ("POST", "/repos/iglootools/nbkp/pulls"):
            self.opened = json.loads(body or b"{}")
            return 201, b'{"number": 42}'
        raise AssertionError(f"unexpected {method} {path}")


class FakeTools:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(
        self, command: Sequence[str], directory: Path
    ) -> subprocess.CompletedProcess[str]:
        self.commands.append(list(command))
        return subprocess.CompletedProcess(command, 0, "", "")


def test_opens_a_pull_request_moving_the_pins_without_merging(tmp_path: Path) -> None:
    (tmp_path / "uv.lock").write_text("lock")
    renovate = tmp_path / "renovate.json"
    renovate.write_text("old")
    found = adopt.Plan("1.32.2", "b" * 40, {renovate: Rewrite("new", 2)})
    github, tools, reports = FakeGitHub(), FakeTools(), []
    outcome = adopt.adopt(
        tmp_path,
        GitHub("t", transport=github),
        REPO,
        found,
        merge_it=False,
        report=reports.append,
        sleep=lambda seconds: None,
        now=lambda: 0.0,
        run=tools,
    )
    assert outcome == adopt.Outcome(42, False, "opened, not merged (--no-merge)")
    assert renovate.read_text() == "new"
    assert tools.commands == [
        ["git", "status", "--porcelain", "--untracked-files=no"],
        ["git", "switch", "-q", "main"],
        ["git", "pull", "-q", "--ff-only"],
        ["git", "switch", "-q", "-c", "chore/iglootools-1.32.2"],
        ["mise", "exec", "--", "uv", "lock", "--upgrade-package", "iglootools"],
        ["git", "add", "--", "renovate.json", "uv.lock"],
        ["git", "commit", "-q", "-m", adopt.commit_message("1.32.2")],
        ["git", "push", "-q", "-u", "origin", "chore/iglootools-1.32.2"],
    ]
    assert (
        github.opened["head"] == "chore/iglootools-1.32.2"
        and github.opened["base"] == "main"
    )


def test_the_dry_run_lists_the_steps_after_the_pins(tmp_path: Path) -> None:
    found = adopt.Plan("1.32.2", "b" * 40, {})
    assert adopt.steps(tmp_path, found, merge_it=False) == [
        "Would create chore/iglootools-1.32.2 from the default branch, up to date.",
        "Would commit and push: chore: move to iglootools 1.32.2.",
        "Would open a pull request into the default branch.",
        "Would stop there (--no-merge).",
    ]

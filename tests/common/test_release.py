import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from iglootools.common import release
from iglootools.common.release import FULL, Plan
from iglootools.common.release import Stage as ReleaseStage
from iglootools.github.client import GitHub, Repository
from iglootools.github.events import Event, Stage
from iglootools.github.local import GitStepError


@pytest.mark.parametrize(
    ("current", "version", "plugin_tag", "plain_tag", "expected"),
    [
        (
            "1.32.2",
            "1.33.0",
            False,
            False,
            Plan(FULL, "releasing 1.33.0, after 1.32.2"),
        ),
        (
            "1.33.0",
            "1.33.0",
            False,
            False,
            Plan(
                (ReleaseStage.PLUGIN_TAG, ReleaseStage.PLAIN_TAG),
                "resuming: the bump has merged",
            ),
        ),
        (
            "1.33.0",
            "1.33.0",
            True,
            False,
            Plan((ReleaseStage.PLAIN_TAG,), "resuming: iglootools--v1.33.0 exists"),
        ),
        ("1.33.0", "1.33.0", True, True, Plan((), "1.33.0 is already released")),
        ("1.34.0", "1.33.0", True, True, Plan((), "1.33.0 is already released")),
        (
            "1.33.0",
            "1.33.0",
            False,
            True,
            Plan((), "", "v1.33.0 exists without iglootools--v1.33.0"),
        ),
        (
            "1.32.2",
            "1.33.0",
            True,
            False,
            Plan((), "", "a 1.33.0 tag exists, but plugin.json is still 1.32.2"),
        ),
        (
            "1.32.2",
            "1.31.9",
            False,
            False,
            Plan((), "", "1.31.9 is not newer than the current 1.32.2"),
        ),
        (
            "1.32.2",
            "v1.33.0",
            False,
            False,
            Plan((), "", "give the version as X.Y.Z, not 'v1.33.0'"),
        ),
    ],
)
def test_the_plan_follows_what_github_already_has(
    current: str, version: str, plugin_tag: bool, plain_tag: bool, expected: Plan
) -> None:
    assert (
        release.plan(current, version, plugin_tag=plugin_tag, plain_tag=plain_tag)
        == expected
    )


def test_the_bump_changes_only_the_version() -> None:
    text = (
        '{\n  "name": "iglootools",\n  "version": "1.32.2",\n  "description": "x"\n}\n'
    )
    assert release.bump(text, "1.33.0") == text.replace("1.32.2", "1.33.0")


def test_releases_are_cut_only_in_common(tmp_path: Path) -> None:
    with pytest.raises(GitStepError, match="releases are cut in iglootools/common"):
        release.release(
            tmp_path,
            GitHub("t"),
            Repository("iglootools", "nbkp"),
            "1.33.0",
            Plan(FULL, ""),
            report=print,
            sleep=lambda seconds: None,
            now=lambda: 0.0,
        )


def test_the_dry_run_of_a_resumed_release_lists_only_what_is_left() -> None:
    found = Plan((ReleaseStage.PLAIN_TAG,), "resuming: iglootools--v1.33.0 exists")
    assert release.steps(found, "1.33.0") == [
        "Resuming: iglootools--v1.33.0 exists.",
        "Would tag iglootools--v1.33.0's commit v1.33.0, push it, and check both tags name it.",
    ]


class FakeTagging:
    def __init__(self, plain_commit: str = "c1") -> None:
        self.plain_commit = plain_commit
        self.commands: list[list[str]] = []

    def __call__(
        self, command: Sequence[str], directory: Path
    ) -> subprocess.CompletedProcess[str]:
        self.commands.append(list(command))
        if list(command[:2]) == ["git", "rev-parse"]:
            commit = self.plain_commit if command[2].startswith("v") else "c1"
            return subprocess.CompletedProcess(command, 0, f"{commit}\n", "")
        return subprocess.CompletedProcess(command, 0, "", "")


def test_the_plugin_tag_is_made_by_claude(tmp_path: Path) -> None:
    tools = FakeTagging()
    release.plugin_tag(tmp_path, run=tools)
    assert tools.commands == [
        ["claude", "plugin", "validate", "."],
        ["claude", "plugin", "tag", "--push", "-m", "Release %s"],
    ]


def test_the_plain_tag_goes_on_the_plugin_tag_s_commit(tmp_path: Path) -> None:
    tools = FakeTagging()
    reports: list[Event] = []
    release.plain_tag(tmp_path, "1.33.0", report=reports.append, run=tools)
    assert tools.commands[:3] == [
        ["git", "fetch", "-q", "--tags"],
        [
            "git",
            "tag",
            "-a",
            "v1.33.0",
            "-m",
            "Release 1.33.0",
            "iglootools--v1.33.0^{}",
        ],
        ["git", "push", "-q", "origin", "v1.33.0"],
    ]
    assert reports == [Event(Stage.TAGGED, "Tagged iglootools--v1.33.0 and v1.33.0")]


def test_tags_naming_different_commits_are_an_error(tmp_path: Path) -> None:
    with pytest.raises(GitStepError, match="name different commits"):
        release.plain_tag(
            tmp_path, "1.33.0", report=print, run=FakeTagging(plain_commit="c2")
        )

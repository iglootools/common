import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from iglootools.common import release
from iglootools.common.release import FULL, Plan, Stage as ReleaseStage
from iglootools.github import worktree
from iglootools.github.client import GitHub, Repository
from iglootools.github.events import Event, Stage
from tests.conftest import git


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
    current: str,
    version: str,
    *,
    plugin_tag: bool,
    plain_tag: bool,
    expected: Plan,
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
    with pytest.raises(release.WrongRepositoryError) as raised:
        release.release(
            tmp_path,
            GitHub("t"),
            Repository("iglootools", "nbkp"),
            "1.33.0",
            Plan(FULL, ""),
            report=print,
            sleep=lambda _seconds: None,
            now=lambda: 0.0,
        )
    assert raised.value.repository == Repository("iglootools", "nbkp")


def test_the_dry_run_of_a_resumed_release_lists_only_what_is_left() -> None:
    found = Plan((ReleaseStage.PLAIN_TAG,), "resuming: iglootools--v1.33.0 exists")
    assert release.steps(found, "1.33.0") == [
        "Resuming: iglootools--v1.33.0 exists.",
        (
            "Would tag iglootools--v1.33.0's commit v1.33.0, push it, "
            "and check both tags name it."
        ),
        "Would fast-forward the checkout's default branch, where that is safe.",
    ]


class FakeTagging:
    def __init__(self, plain_commit: str = "c1") -> None:
        self.plain_commit = plain_commit
        self.commands: list[list[str]] = []
        self.directories: list[Path] = []

    def ran_in(self, directory: Path) -> list[list[str]]:
        """Return the commands run in *directory*."""
        return [
            command
            for command, where in zip(self.commands, self.directories, strict=True)
            if where == directory
        ]

    def __call__(
        self,
        command: Sequence[str],
        directory: Path,
    ) -> subprocess.CompletedProcess[str]:
        self.commands.append(list(command))
        self.directories.append(directory)
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
    with pytest.raises(release.TagMismatchError) as raised:
        release.plain_tag(
            tmp_path,
            "1.33.0",
            report=print,
            run=FakeTagging(plain_commit="c2"),
        )
    assert (raised.value.plain_tag, raised.value.plugin_tag) == (
        "v1.33.0",
        "iglootools--v1.33.0",
    )


def _dirs(tmp_path: Path) -> worktree.MakeDirFn:
    def make(prefix: str) -> Path:
        path = tmp_path / f"{prefix}x"
        path.mkdir()
        return path

    return make


def _plugin_json(version: str) -> str:
    return f'{{\n  "name": "iglootools",\n  "version": "{version}"\n}}\n'


class TestPushBump:
    def _with_plugin_json(self, clone: Path) -> None:
        # push_bump commits itself; the clone's own identity, which its worktrees
        # share, keeps it from depending on the developer's or the runner's.
        git(clone, "config", "user.name", "t")
        git(clone, "config", "user.email", "t@t")
        (clone / ".claude-plugin").mkdir()
        (clone / release.PLUGIN_JSON).write_text(_plugin_json("1.32.2"))
        git(clone, "add", str(release.PLUGIN_JSON))
        git(clone, "commit", "-qm", "v")
        git(clone, "push", "-q", "origin", "main")

    def test_the_bump_is_pushed_and_the_checkout_left_as_it_is(
        self,
        clone: Path,
        tmp_path: Path,
    ) -> None:
        self._with_plugin_json(clone)
        git(clone, "switch", "-q", "-c", "feat/elsewhere")
        (clone / "notes.txt").write_text("work in progress")
        branch = release.push_bump(
            clone,
            "main",
            "1.33.0",
            make_dir_fn=_dirs(tmp_path),
        )
        assert branch == "chore/release-1.33.0"
        pushed = git(clone, "show", f"origin/{branch}:{release.PLUGIN_JSON}")
        assert pushed == _plugin_json("1.33.0")
        assert git(clone, "branch", "--show-current").strip() == "feat/elsewhere"
        assert (clone / "notes.txt").read_text() == "work in progress"
        assert len(git(clone, "worktree", "list").splitlines()) == 1

    def test_it_runs_from_a_worktree_while_another_checkout_holds_main(
        self,
        clone: Path,
        tmp_path: Path,
    ) -> None:
        self._with_plugin_json(clone)
        linked = tmp_path / "linked"
        git(clone, "worktree", "add", "-q", "--detach", str(linked))
        branch = release.push_bump(
            linked,
            "main",
            "1.33.0",
            make_dir_fn=_dirs(tmp_path),
        )
        assert git(clone, "ls-remote", "--heads", "origin", branch) != ""
        assert git(clone, "branch", "--show-current").strip() == "main"


class TestTagRelease:
    def test_the_tags_are_made_in_a_worktree_at_the_default_branch(
        self,
        tmp_path: Path,
    ) -> None:
        tools = FakeTagging()
        root, work = tmp_path / "checkout", tmp_path / "iglootools-release-tags-x"
        root.mkdir()
        release.tag_release(
            root,
            "main",
            "1.33.0",
            (ReleaseStage.PLUGIN_TAG, ReleaseStage.PLAIN_TAG),
            report=lambda _event: None,
            run=tools,
            make_dir_fn=_dirs(tmp_path),
        )
        assert tools.ran_in(root) == [
            ["git", "fetch", "-q", "origin", "main"],
            ["git", "worktree", "add", "-q", "--detach", str(work), "origin/main"],
            ["git", "worktree", "remove", "--force", str(work)],
        ]
        assert ["claude", "plugin", "tag", "--push", "-m", "Release %s"] in (
            tools.ran_in(work)
        )
        assert ["git", "push", "-q", "origin", "v1.33.0"] in tools.ran_in(work)

    def test_a_release_with_no_tag_left_makes_no_worktree(self, tmp_path: Path) -> None:
        tools = FakeTagging()
        release.tag_release(
            tmp_path,
            "main",
            "1.33.0",
            (ReleaseStage.BUMP,),
            report=lambda _event: None,
            run=tools,
            make_dir_fn=_dirs(tmp_path),
        )
        assert tools.commands == []

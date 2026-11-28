from pathlib import Path

from iglootools.github import lint
from tests.conftest import track


def test_workflow_files_lists_only_tracked_top_level_workflows(git_repo: Path) -> None:
    track(git_repo, ".github/workflows/preflight.yml", "name: preflight\n")
    track(git_repo, ".github/workflows/release.yaml", "name: release\n")
    track(git_repo, ".github/workflows/README.md", "# Workflows\n")
    track(git_repo, ".github/workflows/scripts/helper.yml", "x: 1\n")
    track(git_repo, ".github/dependabot.yml", "version: 2\n")
    (git_repo / ".github/workflows/draft.yml").write_text("x: 1\n", encoding="utf-8")
    assert lint.workflow_files(git_repo) == [
        Path(".github/workflows/preflight.yml"),
        Path(".github/workflows/release.yaml"),
    ]


def test_workflow_files_is_empty_without_workflows(git_repo: Path) -> None:
    assert lint.workflow_files(git_repo) == []


def test_jactionlint_runs_the_given_shellcheck_and_no_pyflakes() -> None:
    assert lint.jactionlint_command(
        [Path(".github/workflows/preflight.yml")],
        "/bin/shellcheck",
    ) == [
        "jactionlint",
        "--shellcheck=/bin/shellcheck",
        "--pyflakes=",
        ".github/workflows/preflight.yml",
    ]

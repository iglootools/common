import os
import subprocess
import sys
from pathlib import Path

from tests.conftest import git

_PROJECT_ROOT = Path(__file__).parents[1]


def test_the_clone_fixture_works_in_its_own_repositories(clone: Path) -> None:
    assert git(clone, "rev-parse", "--show-toplevel").strip() == str(clone.resolve())
    assert git(clone, "log", "--format=%s", "origin/main") == "first\n"


def test_the_git_fixtures_leave_the_repository_in_git_dir_alone(
    tmp_path: Path,
) -> None:
    launcher = tmp_path / "launcher"
    git(tmp_path, "init", "-q", str(launcher))
    config_before = (launcher / ".git/config").read_text(encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            f"{__file__}::test_the_clone_fixture_works_in_its_own_repositories",
        ],
        cwd=_PROJECT_ROOT,
        env={**os.environ, "GIT_DIR": str(launcher / ".git")},
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (launcher / ".git/config").read_text(encoding="utf-8") == config_before
    assert git(launcher, "for-each-ref") == ""

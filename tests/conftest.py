import os
import subprocess
from pathlib import Path
from typing import NoReturn

import pytest


def pytest_configure() -> None:
    """
    Clear the variables that point git at a repository, before any test runs.

    `git rebase --exec` in a linked worktree, and git hooks, run their command with
    GIT_DIR set to the repository being worked on. Inherited, it overrides `git -C` and
    `cwd=`, so the fixtures below would init, commit and tag in that repository instead
    of under tmp_path: `git init --bare` once marked a real checkout bare. Not patching:
    the suite leaves the environment that launched it, as python-tooling.md › Run the
    tests apart from the repository that starts them describes.
    """
    names = subprocess.run(
        ["git", "rev-parse", "--local-env-vars"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    for name in names & os.environ.keys():
        del os.environ[name]


class UnexpectedCallError(AssertionError):
    """A fake was called in a way the test did not expect."""

    def __init__(self, call: object) -> None:
        super().__init__(f"unexpected {call!r}")
        self.call = call


@pytest.fixture
def monkeypatch() -> NoReturn:
    """Replace pytest's fixture for every test: tests do not patch."""
    pytest.fail(
        "The monkeypatch fixture is disabled: inject a fake through a parameter"
        " instead (guidelines/coding/general.md, Testability).",
        pytrace=False,
    )


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create an empty git repository, for commands that ask git what it tracks."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def track(repo: Path, name: str, content: str) -> Path:
    """Write *name* under *repo* and add it to git's index."""
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", name], check=True)
    return path


def git(directory: Path, *args: str) -> str:
    """Run git in *directory* and return its output; fail the test when git does."""
    return subprocess.run(
        ["git", "-C", str(directory), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def commit(directory: Path, name: str) -> None:
    """Commit a new file called *name* in *directory*."""
    (directory / name).write_text(name, encoding="utf-8")
    git(directory, "add", name)
    git(directory, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", name)


@pytest.fixture
def clone(tmp_path: Path) -> Path:
    """Clone a bare origin, and push one commit to its main."""
    origin, checkout = tmp_path / "origin.git", tmp_path / "checkout"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    git(tmp_path, "clone", "-q", str(origin), str(checkout))
    git(checkout, "switch", "-q", "-c", "main")
    commit(checkout, "first")
    git(checkout, "push", "-q", "-u", "origin", "main")
    return checkout


def advance_origin(clone: Path) -> str:
    """Push a commit to origin's main from a second clone; return its SHA."""
    other = clone.parent / "other"
    git(clone.parent, "clone", "-q", str(clone.parent / "origin.git"), str(other))
    commit(other, "second")
    git(other, "push", "-q", "origin", "main")
    return git(other, "rev-parse", "HEAD").strip()

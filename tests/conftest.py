import subprocess
from pathlib import Path
from typing import NoReturn

import pytest


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

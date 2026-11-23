import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from iglootools.python import devversion

NOW = datetime(2026, 11, 22, 9, 5, 7, tzinfo=UTC)


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("v1.4.0", "1.4.0.dev20261122090507"),
        (None, "0.0.0.dev20261122090507"),
        ("v1.4.0-rc1", "0.0.0.dev20261122090507"),
    ],
)
def test_the_dev_version_is_the_last_release_with_a_timestamp(
    tag: str | None,
    expected: str,
) -> None:
    assert devversion.compute_dev_version(tag, NOW) == expected


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.com",
            *args,
        ],
        check=True,
        capture_output=True,
    )


def test_the_latest_release_tag_is_the_nearest_reachable_one(git_repo: Path) -> None:
    _git(git_repo, "commit", "-q", "--allow-empty", "-m", "one")
    _git(git_repo, "tag", "v1.0.0")
    _git(git_repo, "commit", "-q", "--allow-empty", "-m", "two")
    _git(git_repo, "tag", "v1.1.0")
    _git(git_repo, "commit", "-q", "--allow-empty", "-m", "three")
    assert devversion.latest_release_tag(git_repo) == "v1.1.0"


def test_a_repository_without_tags_has_no_latest_release(git_repo: Path) -> None:
    _git(git_repo, "commit", "-q", "--allow-empty", "-m", "one")
    assert devversion.latest_release_tag(git_repo) is None

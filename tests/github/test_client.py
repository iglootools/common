import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from iglootools.github import client
from iglootools.github.client import GitHub, GitHubError, GitHubErrorKind, Repository


@pytest.mark.parametrize(
    "url",
    [
        "git@github.com:iglootools/common.git",
        "https://github.com/iglootools/common.git",
        "https://github.com/iglootools/common",
        "ssh://git@github.com/iglootools/common.git\n",
    ],
)
def test_remote_urls_name_the_repository(url: str) -> None:
    assert client.parse_remote(url) == Repository("iglootools", "common")


def test_a_non_github_remote_names_nothing() -> None:
    assert client.parse_remote("git@gitlab.com:someone/thing.git") is None


@pytest.mark.parametrize(
    ("slug", "expected"),
    [("a/b", Repository("a", "b")), ("a", None), ("a/b/c", None), ("/b", None)],
)
def test_slugs(slug: str, expected: Repository | None) -> None:
    assert client.parse_slug(slug) == expected


def _gh(stdout: str, returncode: int = 0) -> client.Run:
    def run(
        command: Sequence[str], directory: Path
    ) -> subprocess.CompletedProcess[str]:
        assert list(command) == ["gh", "auth", "token"]
        return subprocess.CompletedProcess(command, returncode, stdout, "")

    return run


def test_the_environment_token_wins_over_gh(tmp_path: Path) -> None:
    token = client.resolve_token(
        tmp_path, environ={"GITHUB_TOKEN": "env"}, run=_gh("gh")
    )
    assert token == "env"


def test_gh_supplies_the_token_otherwise(tmp_path: Path) -> None:
    assert client.resolve_token(tmp_path, environ={}, run=_gh("gho_abc\n")) == "gho_abc"


def test_no_token_anywhere_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(GitHubError) as raised:
        client.resolve_token(tmp_path, environ={}, run=_gh("", returncode=1))
    assert raised.value.kind == GitHubErrorKind.NO_TOKEN


def test_requests_carry_the_token_and_report_errors_with_their_status() -> None:
    seen: dict[str, Mapping[str, str]] = {}

    def transport(
        method: str, url: str, headers: Mapping[str, str], body: bytes | None
    ) -> tuple[int, bytes]:
        seen["headers"] = headers
        return 404, b'{"message": "Not Found"}'

    with pytest.raises(GitHubError) as raised:
        GitHub("secret", transport=transport).get("/repos/a/b")
    assert seen["headers"]["Authorization"] == "Bearer secret"
    assert raised.value.status == 404 and "Not Found" in raised.value.detail

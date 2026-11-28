import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from iglootools.github.client import GitHub, Repository
from iglootools.workspace import repositories
from iglootools.workspace.repositories import OrganizationRepository

NBKP = {
    "name": "nbkp",
    "archived": False,
    "default_branch": "trunk",
    "ssh_url": "git@github.com:iglootools/nbkp.git",
    "clone_url": "https://github.com/iglootools/nbkp.git",
}


def _github(path_and_reply: tuple[str, object]) -> GitHub:
    expected, reply = path_and_reply

    def transport(
        _method: str,
        url: str,
        _headers: Mapping[str, str],
        _body: bytes | None,
    ) -> tuple[int, bytes]:
        path = url.removeprefix("https://api.github.com")
        assert path.startswith(expected), path
        listed: object = [] if path.endswith("page=2") else reply
        return 200, json.dumps(listed).encode()

    return GitHub("t", transport=transport)


def test_one_repository_reads_as_the_listing_describes_it() -> None:
    github = _github(("/repos/iglootools/nbkp", NBKP))
    found = repositories.get_repository(github, Repository("iglootools", "nbkp"))
    assert found == OrganizationRepository(
        "nbkp",
        archived=False,
        default_branch="trunk",
        ssh_url="git@github.com:iglootools/nbkp.git",
        https_url="https://github.com/iglootools/nbkp.git",
    )


def test_the_listing_is_sorted_by_name() -> None:
    listed = [dict(NBKP, name="photree"), NBKP]
    github = _github(("/orgs/iglootools/repos?type=all", listed))
    assert [r.name for r in repositories.list_repositories(github)] == [
        "nbkp",
        "photree",
    ]


@pytest.mark.parametrize(
    ("text", "age"),
    [
        ("7d", timedelta(days=7)),
        ("12h", timedelta(hours=12)),
        ("30m", timedelta(minutes=30)),
        ("3", timedelta(days=3)),
        ("0", timedelta(0)),
    ],
)
def test_a_max_age_reads_days_hours_or_minutes(text: str, age: timedelta) -> None:
    assert repositories.parse_max_age(text) == age


@pytest.mark.parametrize("text", ["", "7 days", "1w", "-1d", "d"])
def test_anything_else_is_not_a_max_age(text: str) -> None:
    with pytest.raises(ValueError, match=f"^{re.escape(text)}$"):
        repositories.parse_max_age(text)


NOW = datetime(2026, 11, 28, 12, 0, tzinfo=UTC)


class CountingGitHub:
    """Answer the organization's listing, and count how often it was asked."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(
        self,
        _method: str,
        url: str,
        _headers: Mapping[str, str],
        _body: bytes | None,
    ) -> tuple[int, bytes]:
        self.calls += 1
        listed = [] if url.endswith("page=2") else [NBKP]
        return 200, json.dumps(listed).encode()


def _listing(
    fake: CountingGitHub,
    cache: Path,
    *,
    now: datetime = NOW,
    refresh: bool = False,
) -> repositories.Listing:
    return repositories.listing(
        GitHub("t", transport=fake),
        cache,
        max_age=timedelta(days=7),
        refresh=refresh,
        now=now,
    )


def test_a_fresh_listing_is_kept_and_reused_without_asking_github(
    tmp_path: Path,
) -> None:
    fake = CountingGitHub()
    first = _listing(fake, tmp_path / "cache")
    again = _listing(fake, tmp_path / "cache", now=NOW + timedelta(days=6))
    assert (first.cached, again.cached) == (False, True)
    assert again.repositories == first.repositories
    assert again.listed_at == NOW
    assert fake.calls == 1


def test_a_listing_older_than_allowed_is_asked_again(tmp_path: Path) -> None:
    fake = CountingGitHub()
    _listing(fake, tmp_path / "cache")
    again = _listing(fake, tmp_path / "cache", now=NOW + timedelta(days=8))
    assert not again.cached
    assert again.listed_at == NOW + timedelta(days=8)
    assert fake.calls == 2


def test_refresh_asks_again_whatever_the_listing_s_age(tmp_path: Path) -> None:
    fake = CountingGitHub()
    _listing(fake, tmp_path / "cache")
    assert not _listing(fake, tmp_path / "cache", refresh=True).cached
    assert fake.calls == 2


def test_the_cache_directory_is_created_under_the_marker(tmp_path: Path) -> None:
    _listing(CountingGitHub(), tmp_path / "cache")
    assert (tmp_path / "cache" / repositories.LISTING_FILE).is_file()


def test_without_the_marker_directory_nothing_is_kept(tmp_path: Path) -> None:
    fake = CountingGitHub()
    _listing(fake, tmp_path / "missing" / "cache")
    _listing(fake, tmp_path / "missing" / "cache")
    assert fake.calls == 2
    assert not (tmp_path / "missing").exists()


def test_a_cached_listing_that_cannot_be_read_is_an_error(tmp_path: Path) -> None:
    (tmp_path / repositories.LISTING_FILE).write_text("{not json", encoding="utf-8")
    with pytest.raises(repositories.ListingCacheError) as raised:
        _listing(CountingGitHub(), tmp_path)
    assert raised.value.path == tmp_path / repositories.LISTING_FILE

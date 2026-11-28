"""
The repositories of the iglootools organization, as GitHub lists them.

The listing rarely changes, so the workspace commands keep it in the workspace's cache
and reuse it until it is older than they allow: 7 days unless told otherwise.
"""

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from iglootools.github.client import GitHub, Repository

ORGANIZATION = "iglootools"
LISTING_FILE = "repositories.json"
DEFAULT_MAX_AGE = "7d"
_MAX_AGE = re.compile(r"(?P<amount>\d+)(?P<unit>[dhm]?)")
_UNITS = {"d": "days", "h": "hours", "m": "minutes", "": "days"}


@dataclass(frozen=True)
class OrganizationRepository:
    """A repository of the organization: its name, state and where to clone it from."""

    name: str
    archived: bool
    default_branch: str
    ssh_url: str
    https_url: str

    @property
    def repository(self) -> Repository:
        """Return it as the owner and name the GitHub client takes."""
        return Repository(ORGANIZATION, self.name)


def list_repositories(github: GitHub) -> list[OrganizationRepository]:
    """
    List every repository of the organization, archived ones included, by name.

    Raises GitHubError when GitHub cannot be asked.
    """
    return sorted(
        map(_parse, github.get_all(f"/orgs/{ORGANIZATION}/repos?type=all")),
        key=lambda found: found.name,
    )


def get_repository(github: GitHub, repository: Repository) -> OrganizationRepository:
    """
    Read one repository of the organization, as the listing describes it.

    Raises GitHubError when GitHub cannot be asked, or has no such repository.
    """
    return _parse(github.get(f"/repos/{repository.slug}"))


def _parse(item: dict[str, Any]) -> OrganizationRepository:
    return OrganizationRepository(
        name=item["name"],
        archived=bool(item.get("archived")),
        default_branch=item.get("default_branch") or "main",
        ssh_url=item.get("ssh_url", ""),
        https_url=item.get("clone_url", ""),
    )


def parse_max_age(text: str) -> timedelta:
    """
    Read how old a cached listing may be: `7d`, `12h`, `30m`; `0` never reuses it.

    A bare number counts days. Raises ValueError for anything else.
    """
    match = _MAX_AGE.fullmatch(text.strip())
    if match is None:
        raise ValueError(text)
    return timedelta(**{_UNITS[match["unit"]]: int(match["amount"])})


class ListingCacheError(Exception):
    """The cached listing at *path* exists but cannot be read."""

    def __init__(self, path: Path, detail: str) -> None:
        """Build the error from the file and what is wrong with it."""
        super().__init__(f"{path}: {detail}")
        self.path = path
        self.detail = detail


@dataclass(frozen=True)
class Listing:
    """The organization's repositories, when listed, and whether from the cache."""

    repositories: list[OrganizationRepository]
    listed_at: datetime
    cached: bool


def listing(
    github: GitHub,
    cache: Path,
    *,
    max_age: timedelta,
    refresh: bool,
    now: datetime,
) -> Listing:
    """
    Return the organization's repositories, from the cache in *cache* when fresh.

    The cached listing is reused while younger than *max_age*, unless *refresh*;
    otherwise GitHub is asked, and the answer kept in *cache*, created as needed, when
    the directory that holds it exists: the workspace's marker directory.
    Raises ListingCacheError when the cached listing exists but cannot be read, and
    GitHubError when GitHub cannot be asked.
    """
    path = cache / LISTING_FILE
    if not refresh and path.exists():
        cached = _read_listing(path)
        if now - cached.listed_at < max_age:
            return cached
    found = list_repositories(github)
    if cache.parent.is_dir():
        cache.mkdir(exist_ok=True)
        stored = {
            "listed_at": now.isoformat(),
            "repositories": [asdict(repository) for repository in found],
        }
        path.write_text(json.dumps(stored, indent=2) + "\n", encoding="utf-8")
    return Listing(found, now, cached=False)


def _read_listing(path: Path) -> Listing:
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
        return Listing(
            [OrganizationRepository(**item) for item in stored["repositories"]],
            datetime.fromisoformat(stored["listed_at"]),
            cached=True,
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ListingCacheError(path, str(error)) from error

"""
A small client for GitHub's REST API, over the standard library.

No HTTP library: the command is a dev dependency of every Python project, so whatever it
imports is resolved into each of their locks.

The token is the one `gh` already uses: GH_TOKEN or GITHUB_TOKEN when set, otherwise
what `gh auth token` prints. Reading it is the only time this module runs `gh`.
"""

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from http import HTTPStatus
from pathlib import Path
from typing import Any

API = "https://api.github.com"

type Json = Any
"""A decoded JSON value, as GitHub returns it."""

type Transport = Callable[
    [str, str, Mapping[str, str], bytes | None],
    tuple[int, bytes],
]
"""Sends (method, url, headers, body) and returns (status, body), for any status."""

type Run = Callable[[Sequence[str], Path], subprocess.CompletedProcess[str]]
"""Runs a command in a directory, capturing its output."""


class GitHubErrorKind(StrEnum):
    """Why a GitHub call could not be made or failed."""

    NO_TOKEN = "no-token"  # noqa: S105 - an error kind, not a secret
    NO_REPOSITORY = "no-repository"
    REQUEST_FAILED = "request-failed"


class GitHubError(RuntimeError):
    """A GitHub call that could not be made or failed: kind, detail and HTTP status."""

    def __init__(self, kind: GitHubErrorKind, detail: str, status: int = 0) -> None:
        """Build the error; *status* is the HTTP status, 0 when no request was made."""
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail
        self.status = status


@dataclass(frozen=True)
class Repository:
    """A GitHub repository, by owner and name."""

    owner: str
    name: str

    @property
    def slug(self) -> str:
        """Return `owner/name`, as GitHub's URLs and `gh` spell it."""
        return f"{self.owner}/{self.name}"


def urllib_transport(
    method: str,
    url: str,
    headers: Mapping[str, str],
    body: bytes | None,
) -> tuple[int, bytes]:
    """Send the request with urllib, with a 30-second timeout; return any status."""
    request = urllib.request.Request(  # noqa: S310 - GitHub.request sends only https://api.github.com URLs
        url,
        data=body,
        headers=dict(headers),
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - an https://api.github.com URL, as above
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


NONINTERACTIVE = {
    "GIT_TERMINAL_PROMPT": "0",
    "SSH_ASKPASS_REQUIRE": "never",
    "GCM_INTERACTIVE": "never",
}
"""Make git and ssh fail rather than prompt: several projects run at once, and a prompt
for one key's passphrase would wait on a terminal nobody is watching."""


def noninteractive(environ: Mapping[str, str]) -> dict[str, str]:
    """*environ* with git's and ssh's prompts turned into failures."""
    ssh = environ.get("GIT_SSH_COMMAND", "ssh")
    batch = ssh if "BatchMode" in ssh else f"{ssh} -o BatchMode=yes"
    return {**environ, **NONINTERACTIVE, "GIT_SSH_COMMAND": batch}


def capture(
    command: Sequence[str],
    directory: Path,
) -> subprocess.CompletedProcess[str]:
    """Run *command* in *directory*, capturing its text output, prompts turned off."""
    return subprocess.run(
        command,
        cwd=directory,
        capture_output=True,
        text=True,
        check=False,
        env=noninteractive(os.environ),
    )


@dataclass(frozen=True)
class GitHub:
    """Authenticated calls to the REST API. Any status of 400 or more is an error."""

    token: str
    transport: Transport = urllib_transport

    def request(self, method: str, path: str, body: Json = None) -> Json:
        """
        Send *body* as JSON to *path* under the API, and return the decoded reply.

        Raises GitHubError(REQUEST_FAILED), with the status, for any status from 400.
        """
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "iglootools",
        } | ({"Content-Type": "application/json"} if body is not None else {})
        data = json.dumps(body).encode() if body is not None else None
        status, raw = self.transport(method, f"{API}{path}", headers, data)
        if status >= HTTPStatus.BAD_REQUEST:
            raise GitHubError(
                GitHubErrorKind.REQUEST_FAILED,
                f"{method} {path}: {status} {_message(raw)}",
                status,
            )
        return json.loads(raw) if raw else None

    def get(self, path: str) -> Json:
        """Return the decoded reply to a GET of *path*; raises as request() does."""
        return self.request("GET", path)

    def get_all(self, path: str, *, per_page: int = 100) -> list[Json]:
        """Return every item of a paginated list, page by page until a short page."""
        separator = "&" if "?" in path else "?"
        items: list[Json] = []
        page = 1
        while True:
            batch = self.get(f"{path}{separator}per_page={per_page}&page={page}")
            items.extend(batch)
            if len(batch) < per_page:
                return items
            page += 1


def _message(raw: bytes) -> str:
    try:
        return str(json.loads(raw).get("message", ""))
    except ValueError, AttributeError:
        return raw.decode(errors="replace")[:200]


def resolve_token(root: Path, *, environ: Mapping[str, str], run: Run = capture) -> str:
    """Return the token `gh` would use: GH_TOKEN, GITHUB_TOKEN, then `gh auth token`."""
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        if environ.get(name):
            return environ[name]
    try:
        result = run(["gh", "auth", "token"], root)
    except FileNotFoundError:
        result = None
    if result is None or result.returncode != 0 or not result.stdout.strip():
        raise GitHubError(
            GitHubErrorKind.NO_TOKEN,
            "set GH_TOKEN, or log in with `gh auth login`",
        )
    return result.stdout.strip()


_REMOTE = re.compile(
    r"^(?:git@github\.com:|ssh://git@github\.com/|https://github\.com/)"
    r"(?P<owner>[^/]+)/(?P<name>[^/]+?)(?:\.git)?/?$",
)


def parse_remote(url: str) -> Repository | None:
    """Return the GitHub repository a remote URL names, in its SSH or HTTPS spelling."""
    match _REMOTE.match(url.strip()):
        case None:
            return None
        case found:
            return Repository(found["owner"], found["name"])


def origin_repository(root: Path, *, run: Run = capture) -> Repository:
    """
    Return the GitHub repository behind the `origin` remote of the checkout at *root*.

    Raises GitHubError(NO_REPOSITORY) when origin is not on GitHub.
    """
    result = run(["git", "remote", "get-url", "origin"], root)
    repository = parse_remote(result.stdout) if result.returncode == 0 else None
    if repository is None:
        raise GitHubError(
            GitHubErrorKind.NO_REPOSITORY,
            "origin is not a GitHub repository; pass --repo owner/name",
        )
    return repository


def parse_slug(slug: str) -> Repository | None:
    """`owner/name` as a repository, or None when it is not that shape."""
    owner, _, name = slug.partition("/")
    return Repository(owner, name) if owner and name and "/" not in name else None

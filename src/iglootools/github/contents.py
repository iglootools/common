"""Read a file from a repository on GitHub, without a checkout."""

import base64
from http import HTTPStatus
from urllib.parse import quote

from iglootools.github.client import GitHub, GitHubError, Repository


def read_text(
    github: GitHub,
    repository: Repository,
    path: str,
    *,
    ref: str | None = None,
) -> str | None:
    """
    Return *path* in *repository*, at *ref* or on its default branch, as UTF-8 text.

    None when there is no such file, which is also how GitHub answers for an empty
    repository, having no default branch yet. Raises GitHubError for anything else.
    """
    query = f"?ref={quote(ref, safe='')}" if ref else ""
    try:
        found = github.get(f"/repos/{repository.slug}/contents/{path}{query}")
    except GitHubError as error:
        if error.status == HTTPStatus.NOT_FOUND:
            return None
        raise
    return base64.b64decode(found["content"]).decode("utf-8")

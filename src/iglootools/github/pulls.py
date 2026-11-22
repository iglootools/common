"""Open pull requests."""

from iglootools.github.client import GitHub, Repository


def open_pull(
    github: GitHub,
    repository: Repository,
    *,
    head: str,
    base: str,
    title: str,
    body: str,
) -> int:
    """Open a pull request from *head* into *base*, and return its number."""
    created = github.request(
        "POST",
        f"/repos/{repository.slug}/pulls",
        {"head": head, "base": base, "title": title, "body": body},
    )
    return int(created["number"])


def default_branch(github: GitHub, repository: Repository) -> str:
    """Return the name of *repository*'s default branch on GitHub."""
    return str(github.get(f"/repos/{repository.slug}")["default_branch"])

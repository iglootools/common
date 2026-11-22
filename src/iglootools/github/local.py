"""Tidy the local checkout after a pull request merges."""

from dataclasses import dataclass
from pathlib import Path

from iglootools.github.client import Run, capture


@dataclass(frozen=True)
class LocalCleanup:
    switched_to_base: bool
    deleted: bool
    problem: str = ""


def update_commands(base: str) -> list[list[str]]:
    """Switch to *base* and fast-forward it to the remote, without `git pull`.

    `git pull` merges whatever .git/FETCH_HEAD lists, and that file has no lock: a fetch
    running at the same moment, such as an editor's background fetch, can leave it naming
    the branch twice, and the pull then refuses ("Cannot fast-forward to multiple
    branches"). Fetching the one branch and fast-forwarding from its remote-tracking ref,
    which git updates under a lock, does not depend on that file.
    """
    return [
        ["git", "switch", "-q", base],
        ["git", "fetch", "-q", "origin", base],
        ["git", "merge", "-q", "--ff-only", f"origin/{base}"],
    ]


def clean_local(
    root: Path, branch: str, base: str, *, run: Run = capture
) -> LocalCleanup:
    """Leave *branch* for an up-to-date *base*, then delete *branch* and stale remote refs.

    `git branch -d`, not `-D`: git refuses to delete a branch whose commits the updated base
    does not contain, which catches a local commit that never reached the pull request.
    """
    current = run(["git", "branch", "--show-current"], root).stdout.strip()
    switched = current == branch
    if switched:
        for command in update_commands(base):
            result = run(command, root)
            if result.returncode != 0:
                return LocalCleanup(False, False, result.stderr.strip())
    exists = run(["git", "show-ref", "-q", "--verify", f"refs/heads/{branch}"], root)
    deleted = False
    problem = ""
    if exists.returncode == 0:
        result = run(["git", "branch", "-q", "-d", branch], root)
        deleted = result.returncode == 0
        problem = "" if deleted else result.stderr.strip()
    run(["git", "fetch", "-q", "--prune"], root)
    return LocalCleanup(switched, deleted, problem)


def local_branches(root: Path, *, run: Run = capture) -> list[str]:
    """The branches in the checkout at *root*."""
    result = run(
        ["git", "for-each-ref", "--format=%(refname:short)", "refs/heads"], root
    )
    return [line for line in result.stdout.splitlines() if line]


class GitStepError(RuntimeError):
    """A git step failed; the message is git's own."""


def git(root: Path, *args: str, run: Run = capture) -> str:
    """Run `git <args>` in *root*, returning its output, or raise with git's message."""
    result = run(["git", *args], root)
    if result.returncode != 0:
        raise GitStepError(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout


def require_clean(root: Path, *, run: Run = capture) -> None:
    """Raise unless the checkout has no changes and no untracked files."""
    if git(root, "status", "--porcelain", run=run).strip():
        raise GitStepError(
            "the checkout has changes or untracked files; commit, stash or remove them"
        )


def start_branch(root: Path, base: str, branch: str, *, run: Run = capture) -> None:
    """Create *branch* from an up-to-date *base*, in a clean checkout."""
    require_clean(root, run=run)
    sync(root, base, run=run)
    git(root, "switch", "-q", "-c", branch, run=run)


def sync(root: Path, base: str, *, run: Run = capture) -> None:
    """Switch to *base* and bring it up to date with the remote, fast-forward only."""
    for command in update_commands(base):
        git(root, *command[1:], run=run)


def has_local_branch(root: Path, branch: str, *, run: Run = capture) -> bool:
    return (
        run(
            ["git", "show-ref", "-q", "--verify", f"refs/heads/{branch}"], root
        ).returncode
        == 0
    )


def has_remote_branch(root: Path, branch: str, *, run: Run = capture) -> bool:
    return bool(git(root, "ls-remote", "--heads", "origin", branch, run=run).strip())


def commit_and_push(
    root: Path,
    paths: list[str],
    message: str,
    branch: str,
    *,
    run: Run = capture,
) -> None:
    git(root, "add", "--", *paths, run=run)
    if run(["git", "diff", "--cached", "--quiet"], root).returncode != 0:
        git(root, "commit", "-q", "-m", message, run=run)
    git(root, "push", "-q", "-u", "origin", branch, run=run)

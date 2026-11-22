"""Tidy the local checkout after a pull request merges."""

from dataclasses import dataclass
from pathlib import Path

from iglootools.github.client import Run, capture


@dataclass(frozen=True)
class LocalCleanup:
    switched_to_base: bool
    deleted: bool
    problem: str = ""


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
        for command in (
            ["git", "switch", "-q", base],
            ["git", "pull", "-q", "--ff-only"],
        ):
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

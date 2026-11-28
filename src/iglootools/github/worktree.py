"""
Work on a branch in a temporary worktree, leaving the project's own checkout alone.

A worktree shares the repository's objects and refs but has its own files and HEAD, so a
command can branch, commit and push in it while an editor or another session goes on
working in the checkout, on whatever branch, with whatever changes it has.
"""

import shutil
import tempfile
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from iglootools.github import local
from iglootools.github.client import Run, capture

type MakeDirFn = Callable[[str], Path]
"""Creates a new, empty directory whose name starts with the given prefix."""


def make_temporary_dir(prefix: str) -> Path:
    """Create an empty directory under the system's temporary directory."""
    return Path(tempfile.mkdtemp(prefix=prefix))


@contextmanager
def temporary_worktree(
    root: Path,
    start: str,
    *,
    name: str,
    keep_on_failure: bool,
    run: Run = capture,
    make_dir_fn: MakeDirFn = make_temporary_dir,
) -> Generator[Path]:
    """
    Check *start* out, detached, in a new worktree of *root*, and remove it on exit.

    The directory is named iglootools-<name>-<random>. When the body raises and
    *keep_on_failure* is set, the worktree stays, and the error carries a note saying
    where. Raises GitStepError when git cannot add the worktree.
    """
    path = make_dir_fn(f"iglootools-{name}-")
    try:
        local.git(root, "worktree", "add", "-q", "--detach", str(path), start, run=run)
    except local.GitStepError:
        shutil.rmtree(path, ignore_errors=True)
        raise
    try:
        yield path
    except BaseException as error:
        if keep_on_failure:
            error.add_note(f"The worktree is kept at {path}.")
        else:
            remove(root, path, run=run)
        raise
    remove(root, path, run=run)


def remove(root: Path, path: Path, *, run: Run = capture) -> None:
    """
    Remove the worktree at *path*, uncommitted changes and all.

    When git cannot, deletes the directory and prunes git's record of it instead: the
    worktree only ever held what was already committed or can be regenerated.
    """
    if run(["git", "worktree", "remove", "--force", str(path)], root).returncode != 0:
        shutil.rmtree(path, ignore_errors=True)
        run(["git", "worktree", "prune"], root)


class FastForwardAction(StrEnum):
    """What fast-forwarding the default branch does, or why it leaves it alone."""

    UP_TO_DATE = "up-to-date"
    MOVE_REF = "move-ref"
    MERGE = "merge"
    DIVERGED = "diverged"
    HAS_CHANGES = "has-changes"


def plan_fast_forward(
    *,
    up_to_date: bool,
    behind_only: bool,
    checked_out: bool,
    clean: bool,
) -> FastForwardAction:
    """
    Decide how to bring the local default branch up to the remote's, if it is safe.

    Never when the branch has commits the remote lacks, nor when the checkout it is in
    has changes: that is someone's work in progress. A branch no checkout has is moved
    by its ref alone; one that is checked out is merged, fast-forward only, so its files
    follow.
    """
    if up_to_date:
        return FastForwardAction.UP_TO_DATE
    if not behind_only:
        return FastForwardAction.DIVERGED
    if not checked_out:
        return FastForwardAction.MOVE_REF
    return FastForwardAction.MERGE if clean else FastForwardAction.HAS_CHANGES


@dataclass(frozen=True)
class FastForward:
    """What fast-forwarding did, and the checkout *base* is in, if any."""

    action: FastForwardAction
    checkout: Path | None = None


def fast_forward(
    root: Path,
    base: str,
    *,
    dry_run: bool = False,
    run: Run = capture,
) -> FastForward:
    """
    Fast-forward the local *base* to origin's, wherever it is checked out, if safe.

    Fetches *base* first. Leaves it alone, saying why, as plan_fast_forward decides. A
    dry run neither fetches nor moves anything, and returns what it would do against
    the remote-tracking branch as it stands. Raises GitStepError when a git step fails.
    """
    if not dry_run:
        local.git(root, "fetch", "-q", "origin", base, run=run)
    ours = local.git(root, "rev-parse", f"refs/heads/{base}", run=run).strip()
    theirs = local.git(
        root,
        "rev-parse",
        f"refs/remotes/origin/{base}",
        run=run,
    ).strip()
    behind_only = (
        run(["git", "merge-base", "--is-ancestor", ours, theirs], root).returncode == 0
    )
    checkout = checkout_of(root, base, run=run)
    clean = checkout is not None and not local.git(
        checkout,
        "status",
        "--porcelain",
        run=run,
    )
    action = plan_fast_forward(
        up_to_date=ours == theirs,
        behind_only=behind_only,
        checked_out=checkout is not None,
        clean=clean,
    )
    match action:
        case _ if dry_run:
            pass  # only planning
        case FastForwardAction.MOVE_REF:
            local.git(root, "update-ref", f"refs/heads/{base}", theirs, ours, run=run)
        case FastForwardAction.MERGE if checkout is not None:
            local.git(checkout, "merge", "-q", "--ff-only", theirs, run=run)
        case _:
            pass  # up to date, or left alone for a reason the caller reports
    return FastForward(action, checkout)


def checkout_of(root: Path, branch: str, *, run: Run = capture) -> Path | None:
    """Return the worktree of *root*'s repository that has *branch* checked out."""
    entries = local.git(root, "worktree", "list", "--porcelain", run=run).split("\n\n")
    return next(
        (
            Path(lines[0].removeprefix("worktree "))
            for lines in map(str.splitlines, entries)
            if f"branch refs/heads/{branch}" in lines
        ),
        None,
    )

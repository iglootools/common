"""Tidy the local checkout after a pull request merges."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from iglootools.github.client import Run, capture


@dataclass(frozen=True)
class LocalCleanup:
    """What tidying the checkout did, and git's message for what it could not do."""

    switched_to_base: bool
    deleted: bool
    problem: str = ""


def update_commands(base: str) -> list[list[str]]:
    """
    Switch to *base* and fast-forward it to the remote, without `git pull`.

    `git pull` merges whatever .git/FETCH_HEAD lists, and that file has no lock: a fetch
    running at the same moment, such as an editor's background fetch, can leave it
    naming the branch twice, and the pull then refuses ("Cannot fast-forward to multiple
    branches"). Fetching the one branch and fast-forwarding from its remote-tracking
    ref, which git updates under a lock, does not depend on that file.
    """
    return [
        ["git", "switch", "-q", base],
        ["git", "fetch", "-q", "origin", base],
        ["git", "merge", "-q", "--ff-only", f"origin/{base}"],
    ]


def clean_local(
    root: Path,
    branch: str,
    base: str,
    *,
    run: Run = capture,
) -> LocalCleanup:
    """
    Leave *branch* for an up-to-date *base*, then delete *branch* and stale remote refs.

    `git branch -d`, not `-D`: git refuses to delete a branch whose commits the updated
    base does not contain, which catches a local commit that never reached the pull
    request.
    """
    current = run(["git", "branch", "--show-current"], root).stdout.strip()
    switched = current == branch
    if switched:
        for command in update_commands(base):
            result = run(command, root)
            if result.returncode != 0:
                return LocalCleanup(
                    switched_to_base=False,
                    deleted=False,
                    problem=result.stderr.strip(),
                )
    exists = run(["git", "show-ref", "-q", "--verify", f"refs/heads/{branch}"], root)
    deleted = False
    problem = ""
    if exists.returncode == 0:
        result = run(["git", "branch", "-q", "-d", branch], root)
        deleted = result.returncode == 0
        problem = "" if deleted else result.stderr.strip()
    run(["git", "fetch", "-q", "--prune"], root)
    return LocalCleanup(switched_to_base=switched, deleted=deleted, problem=problem)


def local_branches(root: Path, *, run: Run = capture) -> list[str]:
    """List the branches in the checkout at *root*."""
    result = run(
        ["git", "for-each-ref", "--format=%(refname:short)", "refs/heads"],
        root,
    )
    return [line for line in result.stdout.splitlines() if line]


class GitStepFailureKind(StrEnum):
    """
    How a git step failed.

    A command exited non-zero, the checkout was unclean, or something else switched
    the checkout to another branch while the step was working on its own.
    """

    COMMAND_FAILED = "command-failed"
    UNCLEAN_CHECKOUT = "unclean-checkout"
    SWITCHED_BRANCH = "switched-branch"


class GitStepError(RuntimeError):
    """
    A failed command with its own message as *output*, an unclean checkout, or a switch.

    For a switch, *branch* is the branch the step works on and *current* the one the
    checkout is on instead, empty for a detached HEAD.
    """

    def __init__(
        self,
        kind: GitStepFailureKind,
        command: Sequence[str] = (),
        output: str = "",
        *,
        branch: str = "",
        current: str = "",
    ) -> None:
        """Build the error from its kind and the fields that kind uses."""
        match kind:
            case GitStepFailureKind.COMMAND_FAILED:
                message = f"{' '.join(command)}: {output}"
            case GitStepFailureKind.UNCLEAN_CHECKOUT:
                message = (
                    "the checkout has changes or untracked files; "
                    "commit, stash or remove them"
                )
            case GitStepFailureKind.SWITCHED_BRANCH:
                message = (
                    f"the checkout left {branch} for {current or 'a detached HEAD'}"
                    " before the commit, so nothing was committed or pushed; the"
                    f" changes meant for {branch} are uncommitted there"
                )
        super().__init__(message)
        self.kind = kind
        self.command = tuple(command)
        self.output = output
        self.branch = branch
        self.current = current


def git(root: Path, *args: str, run: Run = capture) -> str:
    """Run `git <args>` in *root*, returning its output, or raise with git's message."""
    result = run(["git", *args], root)
    if result.returncode != 0:
        raise GitStepError(
            GitStepFailureKind.COMMAND_FAILED,
            ["git", *args],
            result.stderr.strip(),
        )
    return result.stdout


def require_clean(root: Path, *, run: Run = capture) -> None:
    """Raise unless the checkout has no changes and no untracked files."""
    if git(root, "status", "--porcelain", run=run).strip():
        raise GitStepError(GitStepFailureKind.UNCLEAN_CHECKOUT)


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
    """Tell whether the checkout at *root* has a local *branch*."""
    return (
        run(
            ["git", "show-ref", "-q", "--verify", f"refs/heads/{branch}"],
            root,
        ).returncode
        == 0
    )


def has_remote_branch(root: Path, branch: str, *, run: Run = capture) -> bool:
    """Tell whether origin has *branch*; raises GitStepError when it cannot be asked."""
    return bool(git(root, "ls-remote", "--heads", "origin", branch, run=run).strip())


def commit_and_push(
    root: Path,
    paths: list[str],
    message: str,
    branch: str,
    *,
    run: Run = capture,
) -> None:
    """
    Commit *paths* with *message* on *branch*, if they changed, and push it to origin.

    Refuses when the checkout is no longer on *branch*: another process sharing the
    checkout, such as an editor or an agent working there, can switch it while a long
    step runs, and the commit would then land on that other branch while *branch* is
    pushed without it. Raises GitStepError with git's message when a step fails.
    """
    current = git(root, "branch", "--show-current", run=run).strip()
    if current != branch:
        raise GitStepError(
            GitStepFailureKind.SWITCHED_BRANCH,
            branch=branch,
            current=current,
        )
    git(root, "add", "--", *paths, run=run)
    if run(["git", "diff", "--cached", "--quiet"], root).returncode != 0:
        git(root, "commit", "-q", "-m", message, run=run)
    git(root, "push", "-q", "-u", "origin", branch, run=run)

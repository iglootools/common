"""
Bring one checkout in line with GitHub: its default branch current, merged ones gone.

A checkout with uncommitted changes is never switched, one on a branch that has not
merged is switched only when forced, and a branch with commits its default branch lacks
is never deleted: each is someone's work, and is reported instead. Which branches go
follows prune-branches: those whose latest pull request merged, on GitHub and locally.
"""

from dataclasses import dataclass, field
from pathlib import Path

from iglootools.github import local, prune, worktree
from iglootools.github.client import GitHub, GitHubError, Run, capture
from iglootools.github.local import GitStepError
from iglootools.github.worktree import FastForwardAction
from iglootools.workspace.repositories import OrganizationRepository


@dataclass(frozen=True)
class KeptBranch:
    """A branch sync left in place, where it is, and why."""

    name: str
    where: str
    reason: str


@dataclass(frozen=True)
class SyncResult:
    """
    What sync did to one checkout.

    *done* says what changed (or would, in a dry run), *kept* the branches left in
    place, *worktrees* the checkout's other worktrees, *warnings* what was left alone on
    purpose, and *problems* what needs a person: each a sentence.
    """

    name: str
    done: list[str] = field(default_factory=list[str])
    kept: list[KeptBranch] = field(default_factory=list[KeptBranch])
    worktrees: list[str] = field(default_factory=list[str])
    warnings: list[str] = field(default_factory=list[str])
    problems: list[str] = field(default_factory=list[str])


def sync_one(
    path: Path,
    repository: OrganizationRepository,
    github: GitHub,
    *,
    force: bool,
    dry_run: bool,
    run: Run = capture,
) -> SyncResult:
    """
    Sync the checkout at *path* of *repository*, after clone has fetched it.

    Switches a clean checkout to the default branch when the branch it is on merged,
    or whatever it is on when *force*, and warns of one it leaves on unmerged work.
    Fast-forwards the default branch where safe and checks it matches origin's,
    deletes the branches whose pull request merged, and lists the branches kept and
    the other worktrees. A dry run changes nothing and says what it would do. Each
    failure is a problem of its result, never an exception.
    """
    base = repository.default_branch
    try:
        default_branch, branches = prune.gather(
            github,
            repository.repository,
            local.local_branches(path, run=run),
        )
        decisions = prune.plan(branches, default_branch)
        switched = _switch_to_base(
            path,
            base,
            decisions,
            force=force,
            dry_run=dry_run,
            run=run,
        )
        moved = _fast_forward(path, base, dry_run=dry_run, run=run)
        # In a dry run the switch has not happened, so delete from where it would
        # leave the checkout, not from where it still is.
        current = (
            base
            if switched.done
            else local.git(path, "branch", "--show-current", run=run).strip()
        )
        pruned = _prune(
            path,
            repository,
            github,
            decisions,
            current,
            dry_run=dry_run,
            run=run,
        )
        return SyncResult(
            repository.name,
            done=[*switched.done, *moved.done, *pruned.done],
            kept=pruned.kept,
            worktrees=other_worktrees(path, run=run),
            warnings=switched.warnings,
            problems=[*switched.problems, *moved.problems, *pruned.problems],
        )
    except (GitStepError, GitHubError) as error:
        return SyncResult(
            repository.name,
            problems=[str(getattr(error, "detail", error))],
        )


def _switch_to_base(
    path: Path,
    base: str,
    decisions: list[prune.Decision],
    *,
    force: bool,
    dry_run: bool,
    run: Run,
) -> SyncResult:
    current = local.git(path, "branch", "--show-current", run=run).strip()
    on = current or "a detached HEAD"
    if local.git(path, "status", "--porcelain", run=run).strip():
        return SyncResult(
            path.name,
            problems=[f"has uncommitted changes on {on}; left as it is"],
        )
    if current == base:
        return SyncResult(path.name)
    merged = {decision.branch.name for decision in decisions if decision.delete}
    if current not in merged and not force:
        why = next(
            (d.reason for d in decisions if d.branch.name == current),
            "no branch",
        )
        return SyncResult(
            path.name,
            warnings=[
                (
                    f"left on {on} ({why}), which has not merged; --force switches "
                    f"it to {base}"
                ),
            ],
        )
    if dry_run:
        return SyncResult(path.name, done=[f"would switch from {on} to {base}"])
    local.git(path, "switch", "-q", base, run=run)
    return SyncResult(path.name, done=[f"switched from {on} to {base}"])


def _fast_forward(path: Path, base: str, *, dry_run: bool, run: Run) -> SyncResult:
    result = worktree.fast_forward(path, base, dry_run=dry_run, run=run)
    would = "would fast-forward" if dry_run else "fast-forwarded"
    match result.action:
        case FastForwardAction.UP_TO_DATE:
            return SyncResult(path.name)
        case FastForwardAction.MOVE_REF | FastForwardAction.MERGE if dry_run:
            return SyncResult(path.name, done=[f"{would} {base}"])
        case FastForwardAction.MOVE_REF | FastForwardAction.MERGE:
            return _check_matches_origin(path, base, done=f"{would} {base}", run=run)
        case FastForwardAction.DIVERGED:
            return SyncResult(
                path.name,
                problems=[f"{base} has commits origin/{base} lacks; left as it is"],
            )
        case FastForwardAction.HAS_CHANGES:
            return SyncResult(
                path.name,
                problems=[
                    f"{base} not fast-forwarded: {result.checkout} has changes",
                ],
            )


def _check_matches_origin(path: Path, base: str, *, done: str, run: Run) -> SyncResult:
    ours = local.git(path, "rev-parse", f"refs/heads/{base}", run=run).strip()
    theirs = local.git(path, "rev-parse", f"refs/remotes/origin/{base}", run=run)
    if ours == theirs.strip():
        return SyncResult(path.name, done=[done])
    return SyncResult(
        path.name,
        done=[done],
        problems=[f"{base} still differs from origin/{base} after the fast-forward"],
    )


def _prune(
    path: Path,
    repository: OrganizationRepository,
    github: GitHub,
    decisions: list[prune.Decision],
    current: str,
    *,
    dry_run: bool,
    run: Run,
) -> SyncResult:
    pruned = [
        prune.delete_merged(
            github,
            repository.repository,
            decision,
            path,
            current=current,
            dry_run=dry_run,
            run=run,
        )
        for decision in decisions
        if decision.delete
    ]
    kept = [
        KeptBranch(decision.branch.name, decision.branch.where, decision.reason)
        for decision in decisions
        if not decision.delete
    ]
    if not dry_run and any(decision.delete for decision in decisions):
        local.git(path, "fetch", "-q", "--prune", "origin", run=run)
    return SyncResult(
        path.name,
        done=[line for result in pruned for line in result.done],
        kept=kept,
        problems=[line for result in pruned for line in result.problems],
    )


def other_worktrees(path: Path, *, run: Run = capture) -> list[str]:
    """
    Describe each worktree of *path*'s repository other than *path* itself.

    A worktree inside the checkout, as an agent's under `.claude/worktrees/` is, shows
    relative to it.
    """
    entries = local.git(path, "worktree", "list", "--porcelain", run=run).split("\n\n")
    here = path.resolve()
    return [
        _describe_worktree(lines, here)
        for lines in map(str.splitlines, entries)
        if lines and Path(lines[0].removeprefix("worktree ")).resolve() != here
    ]


def _describe_worktree(lines: list[str], here: Path) -> str:
    where = Path(lines[0].removeprefix("worktree ")).resolve()
    shown = where.relative_to(here) if where.is_relative_to(here) else where
    branch = next(
        (
            line.removeprefix("branch refs/heads/")
            for line in lines
            if line.startswith("branch ")
        ),
        "a detached HEAD",
    )
    locked = " (locked)" if any(line.startswith("locked") for line in lines) else ""
    return f"{shown} on {branch}{locked}"

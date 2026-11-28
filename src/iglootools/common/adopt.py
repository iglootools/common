"""Move a project to a release of iglootools/common, through a pull request."""

from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from iglootools.common import pins
from iglootools.github import local, merge, prune, pulls, worktree
from iglootools.github.client import GitHub, Repository, Run, capture
from iglootools.github.events import Event, Report, Stage


@dataclass(frozen=True)
class Plan:
    """The pin rewrites that would move a project to a release of common."""

    version: str
    sha: str
    files: dict[Path, pins.Rewrite]

    @property
    def changed(self) -> bool:
        """Tell whether any file's pins would move."""
        return bool(self.files)


def plan(root: Path, version: str, sha: str, *, run: Run = capture) -> Plan:
    """Plan the files under *root*, as they stand, whose pins move to *version*."""
    files = {
        path: rewritten
        for path in pins.candidate_files(root, run=run)
        for rewritten in [pins.rewrite(path.read_text(encoding="utf-8"), version, sha)]
        if rewritten.text != path.read_text(encoding="utf-8")
    }
    return Plan(version, sha, files)


def newer_pin(root: Path, version: str, *, run: Run = capture) -> str | None:
    """Return the newest release *root* already pins, when newer than *version*."""
    found, _ = pins.scan(root, run=run)
    pinned = [r.version for r in found if r.version]
    newest = max(pinned, key=_version_key, default=None)
    if newest is not None and _version_key(newest) > _version_key(version):
        return newest
    return None


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def branch_name(version: str) -> str:
    """Return the name of the branch that adopts *version*."""
    return f"chore/iglootools-{version}"


class Start(StrEnum):
    """Where an adopt with no pull request yet picks up."""

    NEW = "new"
    LOCAL = "local"
    REMOTE = "remote"


def where_to_start(*, local_branch: bool, remote_branch: bool) -> Start:
    """Continue from the branch an earlier run left, the remote copy first."""
    if remote_branch:
        return Start.REMOTE
    if local_branch:
        return Start.LOCAL
    return Start.NEW


def commit_message(version: str) -> str:
    """Return the message of the commit that moves the pins to *version*."""
    return (
        f"chore: move to iglootools {version}\n\n"
        "Every pin on iglootools/common moves to the release: the reusable workflows,\n"
        "the Renovate presets and the iglootools command."
    )


@dataclass(frozen=True)
class Workplace:
    """
    Where adopt does its work, and what it leaves the project's checkout on.

    By default it works in a temporary worktree, so the checkout is never switched and
    another session can go on working there, then fast-forwards the checkout's default
    branch once the pull request merges, where that is safe.
    *in_place* works in the checkout itself, for someone who means to finish the
    branch by hand. *keep_worktree* keeps the worktree when a step in it fails, to
    inspect; *skip_fast_forward* leaves the default branch where it is.
    """

    in_place: bool = False
    keep_worktree: bool = False
    skip_fast_forward: bool = False


IN_WORKTREE = Workplace()


class Result(StrEnum):
    """How an adopt ended."""

    MERGED = "merged"
    UP_TO_DATE = "up to date"
    OPENED = "opened"
    REFUSED = "refused"


@dataclass(frozen=True)
class Outcome:
    """How an adopt ended, why, and the pull request it worked on, if any."""

    result: Result
    reason: str
    pull_number: int | None = None

    @property
    def succeeded(self) -> bool:
        """Tell whether the adopt ended in anything but a refusal."""
        return self.result != Result.REFUSED

    @property
    def on_release(self) -> bool:
        """Tell whether the project's default branch now pins the release."""
        return self.result in (Result.MERGED, Result.UP_TO_DATE)


PLUGIN_STEP = "Would update the Claude Code plugin installed for the project."


def preview(
    root: Path,
    github: GitHub,
    repository: Repository,
    found: Plan,
    *,
    merge_it: bool,
    update_plugin: bool,
    workplace: Workplace = IN_WORKTREE,
    run: Run = capture,
) -> list[str]:
    """
    List what adopt would do, from the state a run starts from, one step per line.

    *update_plugin* adds the plugin update to every path that ends on the release.
    """
    branch = branch_name(found.version)
    state, number = prune.latest_pull(github, repository, branch)
    plugin = [PLUGIN_STEP] if update_plugin else []
    fast_forward = (
        []
        if workplace.in_place or workplace.skip_fast_forward
        else ["Would fast-forward the checkout's default branch, where that is safe."]
    )
    finish = (
        [
            "Would merge it once every check has passed, then delete the branch.",
            *fast_forward,
            *plugin,
        ]
        if merge_it
        else ["Would stop there (--no-merge)."]
    )
    match state:
        case prune.PullState.MERGED:
            return [f"Already merged in #{number}: nothing to do.", *plugin]
        case prune.PullState.CLOSED:
            return [f"Would refuse: #{number} was closed without merging."]
        case prune.PullState.OPEN:
            return [f"Would resume #{number}.", *finish]
        case prune.PullState.NONE:
            pass  # no pull request yet: plan one below
    newer = newer_pin(root, found.version, run=run)
    if newer:
        return [f"Would refuse: the project already pins the newer {newer}."]
    start = where_to_start(
        local_branch=local.has_local_branch(root, branch, run=run),
        remote_branch=local.has_remote_branch(root, branch, run=run),
    )
    if start == Start.NEW and not found.changed:
        return [f"Already on iglootools {found.version}: nothing to do.", *plugin]
    moves = [
        f"Would move {rewritten.changed} pin(s) in {path.relative_to(root)}"
        for path, rewritten in found.files.items()
    ]
    opening = {
        Start.NEW: f"Would create {branch} from the default branch, up to date",
        Start.LOCAL: f"Would continue on the local {branch} an earlier run left",
        Start.REMOTE: (
            f"Would continue from {branch} on GitHub, which an earlier run pushed"
        ),
    }[start]
    where = "." if workplace.in_place else ", in a temporary worktree."
    removal = (
        []
        if workplace.in_place
        else [
            "Would remove the worktree"
            + (", or keep it if a step fails." if workplace.keep_worktree else "."),
        ]
    )
    return [
        opening + where,
        *moves,
        *(["Would regenerate uv.lock."] if (root / "uv.lock").is_file() else []),
        (
            "Would commit what still differs, and push: "
            f"chore: move to iglootools {found.version}."
        ),
        *removal,
        "Would open a pull request into the default branch.",
        *finish,
    ]


def adopt(
    root: Path,
    github: GitHub,
    repository: Repository,
    version: str,
    sha: str,
    *,
    merge_it: bool,
    report: Report,
    sleep: Callable[[float], None],
    now: Callable[[], float],
    run: Run = capture,
    push_guard: AbstractContextManager[object] | None = None,
    workplace: Workplace = IN_WORKTREE,
    make_dir_fn: worktree.MakeDirFn = worktree.make_temporary_dir,
) -> Outcome:
    """
    Move *root* to *version* through a pull request, merged once green.

    Works where *workplace* says: by default in a temporary worktree made by
    *make_dir_fn*, leaving the checkout at *root* as it is. Safe to run again, after an
    interruption or alongside other projects: it picks up from the pull request or
    branch an earlier run left, commits only what still differs, and does nothing once
    the release is merged or already in place. A pull request for the release that was
    closed without merging is refused, since someone closed it on purpose. *push_guard*
    serialises pushes when several projects run at once. Raises GitStepError when a git
    or uv step fails, GitHubError when GitHub does; with *keep_worktree*, an error
    raised in the worktree carries a note saying where it was kept.
    """
    branch = branch_name(version)
    if workplace.in_place:
        local.require_clean(root, run=run)
    state, number = prune.latest_pull(github, repository, branch)
    base = pulls.default_branch(github, repository)
    match state:
        case prune.PullState.MERGED:
            return Outcome(Result.UP_TO_DATE, f"already merged in #{number}", number)
        case prune.PullState.CLOSED:
            return Outcome(
                Result.REFUSED,
                f"#{number} was closed without merging; reopen it or delete {branch}",
                number,
            )
        case prune.PullState.OPEN if number is not None:
            report(Event(Stage.OPENED, f"Resuming {repository.slug}#{number}", number))
            return _finish(
                root,
                github,
                repository,
                number,
                branch,
                base=base,
                merge_it=merge_it,
                workplace=workplace,
                report=report,
                sleep=sleep,
                now=now,
                run=run,
            )
        case prune.PullState.OPEN | prune.PullState.NONE:
            pass  # nothing to resume: open one below
    change = _Change(version, sha, branch, report, push_guard or nullcontext())
    if workplace.in_place:
        local.sync(root, base, run=run)
        stopped = _push_change(root, change, run=run)
    else:
        local.git(root, "fetch", "-q", "origin", base, run=run)
        with worktree.temporary_worktree(
            root,
            f"origin/{base}",
            name=f"adopt-{repository.name}",
            keep_on_failure=workplace.keep_worktree,
            run=run,
            make_dir_fn=make_dir_fn,
        ) as work:
            stopped = _push_change(work, change, run=run)
    if stopped is not None:
        return stopped
    number = pulls.open_pull(
        github,
        repository,
        head=branch,
        base=base,
        title=f"chore: move to iglootools {version}",
        body=f"Moves every pin on iglootools/common to {version}.",
    )
    report(Event(Stage.OPENED, f"Opened {repository.slug}#{number}", number))
    return _finish(
        root,
        github,
        repository,
        number,
        branch,
        base=base,
        merge_it=merge_it,
        workplace=workplace,
        report=report,
        sleep=sleep,
        now=now,
        run=run,
    )


@dataclass(frozen=True)
class _Change:
    """The release to move to, the branch that carries it, and how pushes take turns."""

    version: str
    sha: str
    branch: str
    report: Report
    push_guard: AbstractContextManager[object]


def _push_change(work: Path, change: _Change, *, run: Run) -> Outcome | None:
    """
    In the checkout or worktree at *work*, on its default branch, push the change.

    Return how the adopt ends when there is nothing to push, None once pushed.
    """
    newer = newer_pin(work, change.version, run=run)
    if newer:
        return Outcome(
            Result.REFUSED,
            f"the project already pins the newer {newer}; not moving back",
        )
    start = where_to_start(
        local_branch=local.has_local_branch(work, change.branch, run=run),
        remote_branch=local.has_remote_branch(work, change.branch, run=run),
    )
    if (
        start == Start.NEW
        and not plan(work, change.version, change.sha, run=run).changed
    ):
        return Outcome(Result.UP_TO_DATE, f"already on iglootools {change.version}")
    _switch(work, change.branch, start, run=run)
    change.report(Event(Stage.BRANCHED, f"On {change.branch}"))
    found = plan(work, change.version, change.sha, run=run)
    paths = _move_pins(work, found, change.report, run=run)
    with change.push_guard:
        local.commit_and_push(
            work,
            paths,
            commit_message(change.version),
            change.branch,
            run=run,
        )
    change.report(Event(Stage.PUSHED, f"Pushed {change.branch}"))
    return None


def _switch(root: Path, branch: str, start: Start, *, run: Run) -> None:
    match start:
        case Start.NEW:
            local.git(root, "switch", "-q", "-c", branch, run=run)
        case Start.LOCAL:
            local.git(root, "switch", "-q", branch, run=run)
        case Start.REMOTE:
            local.git(root, "fetch", "-q", "origin", branch, run=run)
            local.git(root, "switch", "-q", "-C", branch, f"origin/{branch}", run=run)


def _move_pins(root: Path, found: Plan, report: Report, *, run: Run) -> list[str]:
    """Write the moved pins, refresh uv.lock, and return the paths to commit."""
    for path, rewritten in found.files.items():
        path.write_text(rewritten.text, encoding="utf-8")
        report(
            Event(
                Stage.MOVING,
                f"Moved {rewritten.changed} pin(s) in {path.relative_to(root)}",
            ),
        )
    moved = [str(path.relative_to(root)) for path in found.files]
    if (root / "uv.lock").is_file():
        report(Event(Stage.LOCKING, "Updating uv.lock"))
        # A worktree sits in a temporary directory mise has never been told to trust,
        # and mise refuses an untrusted mise.toml; this trusts it for the one command.
        command = [
            "env",
            f"MISE_TRUSTED_CONFIG_PATHS={root}",
            "mise",
            "exec",
            "--",
            "uv",
            "lock",
            "--upgrade-package",
            "iglootools",
        ]
        result = run(command, root)
        if result.returncode != 0:
            raise local.GitStepError(
                local.GitStepFailureKind.COMMAND_FAILED,
                command,
                result.stderr.strip(),
            )
        return [*moved, "uv.lock"]
    else:
        return moved


def _finish(
    root: Path,
    github: GitHub,
    repository: Repository,
    number: int,
    branch: str,
    *,
    base: str,
    merge_it: bool,
    workplace: Workplace,
    report: Report,
    sleep: Callable[[float], None],
    now: Callable[[], float],
    run: Run,
) -> Outcome:
    if not merge_it:
        return Outcome(Result.OPENED, "opened, not merged (--no-merge)", number)
    outcome = merge.merge_when_green(
        github,
        repository,
        number,
        sleep=sleep,
        now=now,
        report=report,
    )
    if not outcome.merged:
        return Outcome(Result.REFUSED, outcome.reason, number)
    tidied = tidy_after_merge(
        root,
        branch,
        base,
        workplace,
        branch_deleted=outcome.branch_deleted,
        run=run,
    )
    if not tidied:
        return Outcome(Result.MERGED, outcome.reason, number)
    report(Event(Stage.FAST_FORWARD, tidied[0].upper() + tidied[1:]))
    return Outcome(Result.MERGED, f"{outcome.reason}; {tidied}", number)


def tidy_after_merge(
    root: Path,
    branch: str,
    base: str,
    workplace: Workplace,
    *,
    branch_deleted: bool,
    run: Run = capture,
) -> str:
    """
    Tidy the checkout at *root* once the pull request merged; say what became of *base*.

    Deletes the local *branch* when GitHub's copy was deleted. In place, that returns
    the checkout to an up-to-date *base*, and nothing more is said. Out of place, a
    checkout someone switched to *branch* keeps it, since cleaning up would switch
    that checkout, and *base* is fast-forwarded where safe unless
    *skip_fast_forward*. Returns the sentence saying what happened to *base*, or ""
    when nothing was tried.
    """
    kept_by = (
        None if workplace.in_place else worktree.checkout_of(root, branch, run=run)
    )
    if branch_deleted and kept_by is None:
        local.clean_local(root, branch, base, run=run)
    if workplace.in_place or workplace.skip_fast_forward:
        return ""
    return _fast_forward(root, base, run=run)


def _fast_forward(root: Path, base: str, *, run: Run) -> str:
    """Fast-forward *base* in the checkout where safe, and say what happened."""
    try:
        done = worktree.fast_forward(root, base, run=run)
    except local.GitStepError as error:
        return f"{base} not fast-forwarded: {error}"
    match done.action:
        case worktree.FastForwardAction.UP_TO_DATE:
            return f"{base} already up to date"
        case worktree.FastForwardAction.MOVE_REF | worktree.FastForwardAction.MERGE:
            return f"fast-forwarded {base}"
        case worktree.FastForwardAction.DIVERGED:
            return f"{base} left alone: it has commits GitHub lacks"
        case worktree.FastForwardAction.HAS_CHANGES:
            return f"{base} left alone: {done.checkout} has changes"

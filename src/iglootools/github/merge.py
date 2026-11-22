"""Merge a pull request once every check has passed, then delete its branch.

The decision is a pure function of what GitHub reports (`assess`); the loop around it
(`merge_when_green`) fetches, sleeps and acts. Each guard was earned:

- "No checks reported" means "not yet", never "nothing failed". GitHub registers check
  runs a few seconds after a push, so a loop that trusts an empty list merges too early.
  The checks a ruleset requires are waited for by name; in a repository that requires
  none, the first check is waited for during a settling period.
- Every check run on the head commit counts, not only the latest per name. Reopening a
  pull request starts a second run of the same workflow, and the ruleset waits for it.
- "Blocked" with every check green is waited on for a grace period before it counts. GitHub
  recomputes the merge state a few seconds after the last required check passes, so a
  poll in between still reads the block the missing check caused. Only a block that
  outlasts the grace, such as a required review, is refused. The grace starts once every
  check is green, so a long run of checks does not use it up.
- The merge names the head commit it assessed, so a push that lands in between is refused
  by GitHub rather than merged unchecked.
- The branch is deleted only after GitHub reports the pull request merged, and only when
  it belongs to the same repository. Deleting it earlier closes the pull request.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from iglootools.github.client import GitHub, GitHubError, Json, Repository
from iglootools.github.events import Event, Report, Stage

FAILED_CONCLUSIONS = frozenset(
    {"failure", "cancelled", "timed_out", "action_required", "stale", "startup_failure"}
)
FAILED_STATES = frozenset({"failure", "error"})
MERGEABLE_STATES = frozenset({"clean", "unstable", "has_hooks"})
CLEARING_BLOCK = "waiting for GitHub to clear the merge block"


@dataclass(frozen=True)
class Check:
    """A check run, or a commit status, on the pull request's head commit."""

    name: str
    done: bool
    failed: bool


@dataclass(frozen=True)
class PullRequest:
    number: int
    state: str
    merged: bool
    draft: bool
    mergeable_state: str
    head_sha: str
    head_ref: str
    head_repository: str
    base_ref: str
    base_repository: str

    @property
    def from_same_repository(self) -> bool:
        return self.head_repository == self.base_repository


class Action(StrEnum):
    WAIT = "wait"
    MERGE = "merge"
    DONE = "done"
    REFUSE = "refuse"


@dataclass(frozen=True)
class Verdict:
    action: Action
    reason: str


def assess(
    pull: PullRequest,
    checks: Sequence[Check],
    required: frozenset[str],
    *,
    settled: bool,
    block_settled: bool = True,
) -> Verdict:
    """What to do next, given the pull request and the checks on its head commit.

    *required* names the checks a ruleset requires. *settled* says whether the settling
    period has passed, after which a repository that requires no checks and reports none is
    taken to have none. *block_settled* says whether a block that remains with every check
    green has outlasted its grace period; until then it is waited on.
    """
    names = {check.name for check in checks}
    failed = sorted({check.name for check in checks if check.failed})
    pending = sorted({check.name for check in checks if not check.done})
    missing = sorted(required - names)
    match pull:
        case PullRequest(merged=True):
            return Verdict(Action.DONE, "already merged")
        case PullRequest(state="closed"):
            return Verdict(Action.REFUSE, "closed without being merged")
        case PullRequest(draft=True):
            return Verdict(Action.REFUSE, "still a draft")
        case _:
            pass  # open and ready for review: the checks decide
    if failed:
        return Verdict(Action.REFUSE, f"failed: {', '.join(failed)}")
    if missing:
        return Verdict(Action.WAIT, f"waiting for {', '.join(missing)} to start")
    if pending:
        return Verdict(Action.WAIT, f"waiting for {', '.join(pending)}")
    if not checks and not settled:
        return Verdict(Action.WAIT, "waiting for checks to start")
    match pull.mergeable_state:
        case state if state in MERGEABLE_STATES:
            return Verdict(Action.MERGE, "every check passed")
        case "unknown" | "":
            return Verdict(Action.WAIT, "waiting for GitHub to compute mergeability")
        case "blocked" if not block_settled:
            return Verdict(Action.WAIT, CLEARING_BLOCK)
        case "blocked":
            # Still blocked after the grace: a review or another rule GitHub will not lift
            # on its own.
            return Verdict(Action.REFUSE, "blocked by a rule other than the checks")
        case "behind":
            return Verdict(Action.REFUSE, f"behind {pull.base_ref}: update the branch")
        case "dirty":
            return Verdict(Action.REFUSE, f"conflicts with {pull.base_ref}")
        case other:
            return Verdict(Action.REFUSE, f"not mergeable ({other})")


def _full_name(repo: Json) -> str:
    """The `owner/name` of a pull request's head repository; empty once it is deleted."""
    return repo["full_name"] if repo else ""


def parse_pull(data: Json) -> PullRequest:
    head, base = data["head"], data["base"]
    return PullRequest(
        number=data["number"],
        state=data["state"],
        merged=bool(data.get("merged")),
        draft=bool(data.get("draft")),
        mergeable_state=data.get("mergeable_state") or "",
        head_sha=head["sha"],
        head_ref=head["ref"],
        head_repository=_full_name(head.get("repo")),
        base_ref=base["ref"],
        base_repository=base["repo"]["full_name"],
    )


def parse_checks(check_runs: Json, combined_status: Json) -> list[Check]:
    runs = [
        Check(
            name=run["name"],
            done=run["status"] == "completed",
            failed=run.get("conclusion") in FAILED_CONCLUSIONS,
        )
        for run in check_runs.get("check_runs", [])
    ]
    statuses = [
        Check(
            name=status["context"],
            done=status["state"] != "pending",
            failed=status["state"] in FAILED_STATES,
        )
        for status in combined_status.get("statuses", [])
    ]
    return runs + statuses


def parse_required(rules: Json) -> frozenset[str]:
    return frozenset(
        check["context"]
        for rule in rules
        if rule.get("type") == "required_status_checks"
        for check in rule.get("parameters", {}).get("required_status_checks", [])
    )


def fetch_pull(github: GitHub, repository: Repository, number: int) -> PullRequest:
    return parse_pull(github.get(f"/repos/{repository.slug}/pulls/{number}"))


def fetch_checks(github: GitHub, repository: Repository, sha: str) -> list[Check]:
    base = f"/repos/{repository.slug}/commits/{sha}"
    return parse_checks(
        github.get(f"{base}/check-runs?per_page=100"), github.get(f"{base}/status")
    )


def fetch_required(
    github: GitHub, repository: Repository, branch: str
) -> frozenset[str]:
    """The checks the rulesets on *branch* require; none where rulesets are unavailable.

    A private repository on a free plan answers 403 or 404: it has no rulesets to read.
    """
    try:
        return parse_required(
            github.get(f"/repos/{repository.slug}/rules/branches/{branch}")
        )
    except GitHubError as error:
        if error.status in (403, 404):
            return frozenset()
        raise


@dataclass(frozen=True)
class Outcome:
    merged: bool
    reason: str
    pull: PullRequest
    branch_deleted: bool = False


@dataclass(frozen=True)
class Preview:
    pull: PullRequest
    verdict: Verdict


def preview(github: GitHub, repository: Repository, number: int) -> Preview:
    """One assessment of *number*, without waiting or acting: what a run would do first.

    Checks that have not started count as not started, so a pull request whose checks
    GitHub has not registered yet reads as "would wait", never as "would merge".
    """
    pull = fetch_pull(github, repository, number)
    required = fetch_required(github, repository, pull.base_ref)
    checks = fetch_checks(github, repository, pull.head_sha)
    return Preview(
        pull, assess(pull, checks, required, settled=False, block_settled=False)
    )


def describe(found: Preview, *, delete_branch: bool) -> list[str]:
    """What merge_when_green would do, from *found*, one action per line."""
    pull, verdict = found.pull, found.verdict
    cleanup = (
        [f"Would delete {pull.head_ref} on GitHub, and locally if checked out."]
        if delete_branch and pull.from_same_repository
        else []
    )
    merge_line = (
        f"Would merge #{pull.number} (head {pull.head_sha[:7]}) into {pull.base_ref} "
        "with a merge commit."
    )
    match verdict.action:
        case Action.DONE:
            return ["Already merged.", *cleanup]
        case Action.REFUSE:
            return [f"Would not merge: {verdict.reason}."]
        case Action.WAIT:
            return [
                f"Would wait: {verdict.reason}.",
                f"Then, if every check passes: {merge_line[0].lower()}{merge_line[1:]}",
                *cleanup,
            ]
        case Action.MERGE:
            return [merge_line, *cleanup]


def merge_when_green(
    github: GitHub,
    repository: Repository,
    number: int,
    *,
    sleep: Callable[[float], None],
    now: Callable[[], float],
    report: Report,
    timeout: float = 1800,
    first_interval: float = 30,
    interval: float = 60,
    settle: float = 60,
    block_grace: float = 60,
    delete_branch: bool = True,
) -> Outcome:
    """Wait for *number*'s checks, merge it with a merge commit, and delete its branch.

    Returns without merging when a check fails, GitHub refuses, or *timeout* passes.
    Polls *first_interval* after the first look, then every *interval*: most checks take
    a minute or more, so polling faster only spends API requests, which several runs in
    parallel share under one rate limit.
    """
    start = now()
    pull = fetch_pull(github, repository, number)
    required = fetch_required(github, repository, pull.base_ref)
    last_reason = ""
    green_but_blocked_since: float | None = None
    waited = False
    while True:
        checks = fetch_checks(github, repository, pull.head_sha)
        block_settled = (
            green_but_blocked_since is not None
            and now() - green_but_blocked_since >= block_grace
        )
        verdict = assess(
            pull,
            checks,
            required,
            settled=now() - start >= settle,
            block_settled=block_settled,
        )
        if verdict.reason != CLEARING_BLOCK:
            green_but_blocked_since = None
        elif green_but_blocked_since is None:
            green_but_blocked_since = now()
        match verdict.action:
            case Action.DONE:
                return _cleaned(github, repository, pull, verdict.reason, delete_branch)
            case Action.REFUSE:
                return Outcome(False, verdict.reason, pull)
            case Action.MERGE:
                _merge(github, repository, pull)
                merged = fetch_pull(github, repository, number)
                if not merged.merged:
                    return Outcome(False, "GitHub did not report it merged", merged)
                return _cleaned(github, repository, merged, "merged", delete_branch)
            case Action.WAIT:
                if now() - start >= timeout:
                    return Outcome(False, f"timed out, {verdict.reason}", pull)
                if verdict.reason != last_reason:
                    report(Event(Stage.WAITING, verdict.reason, number))
                    last_reason = verdict.reason
                sleep(interval if waited else first_interval)
                waited = True
                pull = fetch_pull(github, repository, number)


def _merge(github: GitHub, repository: Repository, pull: PullRequest) -> None:
    github.request(
        "PUT",
        f"/repos/{repository.slug}/pulls/{pull.number}/merge",
        {"merge_method": "merge", "sha": pull.head_sha},
    )


def _cleaned(
    github: GitHub,
    repository: Repository,
    pull: PullRequest,
    reason: str,
    delete_branch: bool,
) -> Outcome:
    if not (delete_branch and pull.from_same_repository):
        return Outcome(True, reason, pull)
    try:
        github.request(
            "DELETE", f"/repos/{repository.slug}/git/refs/heads/{pull.head_ref}"
        )
    except GitHubError as error:
        # 422 or 404: already gone, for instance deleted by the repository's own setting.
        if error.status not in (404, 422):
            raise
    return Outcome(True, reason, pull, branch_deleted=True)

import json
from collections.abc import Mapping
from dataclasses import replace

import pytest

from iglootools.github import merge
from iglootools.github.client import GitHub, Repository
from iglootools.github.merge import Action, Check, PullRequest

REPO = Repository("iglootools", "common")
OPEN = PullRequest(
    number=7,
    state="open",
    merged=False,
    draft=False,
    mergeable_state="clean",
    head_sha="abc123",
    head_ref="docs/x",
    head_repository="iglootools/common",
    base_ref="main",
    base_repository="iglootools/common",
)
GREEN = Check("preflight", done=True, failed=False)
RUNNING = Check("preflight", done=False, failed=False)
RED = Check("preflight", done=True, failed=True)


def _assess(
    pull: PullRequest = OPEN,
    checks: tuple[Check, ...] = (GREEN,),
    required: frozenset[str] = frozenset({"preflight"}),
    settled: bool = False,
    block_settled: bool = True,
) -> merge.Verdict:
    return merge.assess(
        pull, checks, required, settled=settled, block_settled=block_settled
    )


def test_green_checks_on_a_clean_pull_request_merge() -> None:
    assert _assess().action == Action.MERGE


def test_no_checks_reported_yet_means_wait_not_merge() -> None:
    # The bug this guards against: an empty list read as "nothing failed".
    verdict = _assess(checks=(), required=frozenset())
    assert verdict.action == Action.WAIT


def test_a_required_check_that_has_not_started_is_waited_for() -> None:
    verdict = _assess(checks=(), settled=True)
    assert verdict == merge.Verdict(Action.WAIT, "waiting for preflight to start")


def test_a_repository_without_checks_merges_once_settled() -> None:
    assert _assess(checks=(), required=frozenset(), settled=True).action == Action.MERGE


def test_a_second_run_of_a_passed_check_is_still_waited_for() -> None:
    # Reopening a pull request starts another run of the same workflow.
    assert _assess(checks=(GREEN, RUNNING)).action == Action.WAIT


@pytest.mark.parametrize(
    ("pull", "checks", "reason"),
    [
        (OPEN, (RED,), "failed: preflight"),
        (replace(OPEN, state="closed"), (GREEN,), "closed without being merged"),
        (replace(OPEN, draft=True), (GREEN,), "still a draft"),
        (replace(OPEN, mergeable_state="dirty"), (GREEN,), "conflicts with main"),
        (
            replace(OPEN, mergeable_state="behind"),
            (GREEN,),
            "behind main: update the branch",
        ),
    ],
)
def test_refusals_say_why(
    pull: PullRequest, checks: tuple[Check, ...], reason: str
) -> None:
    assert _assess(pull, checks) == merge.Verdict(Action.REFUSE, reason)


def test_a_failure_is_reported_even_while_other_checks_run() -> None:
    other = Check("lint", done=False, failed=False)
    assert _assess(checks=(RED, other)).action == Action.REFUSE


def test_an_already_merged_pull_request_is_done() -> None:
    assert _assess(replace(OPEN, merged=True, state="closed")).action == Action.DONE


def test_unknown_mergeability_is_waited_for() -> None:
    assert _assess(replace(OPEN, mergeable_state="unknown")).action == Action.WAIT


def test_check_runs_and_commit_statuses_both_count() -> None:
    checks = merge.parse_checks(
        {
            "check_runs": [
                {"name": "preflight", "status": "completed", "conclusion": "success"}
            ]
        },
        {"statuses": [{"context": "ci/legacy", "state": "pending"}]},
    )
    assert checks == [
        Check("preflight", done=True, failed=False),
        Check("ci/legacy", done=False, failed=False),
    ]


def test_required_checks_come_from_the_rulesets() -> None:
    rules = [
        {"type": "deletion"},
        {
            "type": "required_status_checks",
            "parameters": {"required_status_checks": [{"context": "preflight"}]},
        },
    ]
    assert merge.parse_required(rules) == frozenset({"preflight"})


def _pull_json(pull: PullRequest) -> dict[str, object]:
    return {
        "number": pull.number,
        "state": pull.state,
        "merged": pull.merged,
        "draft": pull.draft,
        "mergeable_state": pull.mergeable_state,
        "head": {
            "sha": pull.head_sha,
            "ref": pull.head_ref,
            "repo": {"full_name": pull.head_repository},
        },
        "base": {"ref": pull.base_ref, "repo": {"full_name": pull.base_repository}},
    }


class FakeGitHub:
    """Answers the endpoints merge_when_green calls, from a script of check states."""

    def __init__(
        self,
        check_states: list[list[dict[str, str]]],
        rules_status: int = 200,
        merge_states: list[str] | None = None,
    ) -> None:
        self.check_states = check_states
        self.rules_status = rules_status
        self.merge_states = merge_states or ["clean"]
        self.merged = False
        self.calls: list[tuple[str, str, object]] = []

    def __call__(
        self, method: str, url: str, headers: Mapping[str, str], body: bytes | None
    ) -> tuple[int, bytes]:
        path = url.removeprefix("https://api.github.com")
        self.calls.append((method, path, json.loads(body) if body else None))
        match method, path:
            case "GET", "/repos/iglootools/common/pulls/7":
                state = (
                    self.merge_states.pop(0)
                    if len(self.merge_states) > 1
                    else self.merge_states[0]
                )
                pull = replace(
                    OPEN,
                    merged=self.merged,
                    state="closed" if self.merged else "open",
                    mergeable_state=state,
                )
                return 200, json.dumps(_pull_json(pull)).encode()
            case "GET", "/repos/iglootools/common/rules/branches/main":
                rules = [
                    {
                        "type": "required_status_checks",
                        "parameters": {
                            "required_status_checks": [{"context": "preflight"}]
                        },
                    }
                ]
                return self.rules_status, json.dumps(
                    rules if self.rules_status == 200 else {"message": "Upgrade"}
                ).encode()
            case (
                "GET",
                "/repos/iglootools/common/commits/abc123/check-runs?per_page=100",
            ):
                state = (
                    self.check_states.pop(0)
                    if len(self.check_states) > 1
                    else self.check_states[0]
                )
                return 200, json.dumps({"check_runs": state}).encode()
            case "GET", "/repos/iglootools/common/commits/abc123/status":
                return 200, json.dumps({"statuses": []}).encode()
            case "PUT", "/repos/iglootools/common/pulls/7/merge":
                self.merged = True
                return 200, b'{"merged": true}'
            case "DELETE", "/repos/iglootools/common/git/refs/heads/docs/x":
                return 204, b""
            case _:
                raise AssertionError(f"unexpected {method} {path}")


class Clock:
    def __init__(self) -> None:
        self.time = 0.0
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.time

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.time += seconds


RUN_PENDING = {"name": "preflight", "status": "in_progress"}
RUN_PASSED = {"name": "preflight", "status": "completed", "conclusion": "success"}
RUN_FAILED = {"name": "preflight", "status": "completed", "conclusion": "failure"}


def _run(fake: FakeGitHub, clock: Clock, **kwargs: object) -> merge.Outcome:
    reports: list[str] = []
    outcome = merge.merge_when_green(
        GitHub("token", transport=fake),
        REPO,
        7,
        sleep=clock.sleep,
        now=clock.now,
        report=reports.append,
        **kwargs,  # type: ignore[arg-type]
    )
    return outcome


def test_waits_for_checks_then_merges_with_a_merge_commit_and_deletes_the_branch() -> (
    None
):
    fake, clock = FakeGitHub([[], [RUN_PENDING], [RUN_PASSED]]), Clock()
    outcome = _run(fake, clock)
    assert outcome.merged and outcome.branch_deleted
    assert (
        "PUT",
        "/repos/iglootools/common/pulls/7/merge",
        {"merge_method": "merge", "sha": "abc123"},
    ) in fake.calls
    assert clock.sleeps == [30, 60]


def test_a_failed_check_is_never_merged() -> None:
    fake = FakeGitHub([[RUN_FAILED]])
    outcome = _run(fake, Clock())
    assert not outcome.merged and outcome.reason == "failed: preflight"
    assert not [call for call in fake.calls if call[0] in ("PUT", "DELETE")]


def test_gives_up_after_the_timeout_without_merging() -> None:
    fake = FakeGitHub([[RUN_PENDING]])
    outcome = _run(fake, Clock(), timeout=30)
    assert not outcome.merged and outcome.reason.startswith("timed out")


def test_a_repository_without_rulesets_waits_out_the_settling_period() -> None:
    fake, clock = FakeGitHub([[]], rules_status=403), Clock()
    outcome = _run(fake, clock, settle=30)
    assert outcome.merged
    assert clock.time >= 30


def test_keep_branch_leaves_the_branch_alone() -> None:
    fake = FakeGitHub([[RUN_PASSED]])
    outcome = _run(fake, Clock(), delete_branch=False)
    assert outcome.merged and not outcome.branch_deleted
    assert not [call for call in fake.calls if call[0] == "DELETE"]


@pytest.mark.parametrize(
    ("verdict", "lines"),
    [
        (
            merge.Verdict(Action.MERGE, "every check passed"),
            [
                "Would merge #7 (head abc123) into main with a merge commit.",
                "Would delete docs/x on GitHub, and locally if checked out.",
            ],
        ),
        (
            merge.Verdict(Action.WAIT, "waiting for preflight"),
            [
                "Would wait: waiting for preflight.",
                "Then, if every check passes: would merge #7 (head abc123) into main with a merge commit.",
                "Would delete docs/x on GitHub, and locally if checked out.",
            ],
        ),
        (
            merge.Verdict(Action.REFUSE, "failed: preflight"),
            ["Would not merge: failed: preflight."],
        ),
        (
            merge.Verdict(Action.DONE, "already merged"),
            [
                "Already merged.",
                "Would delete docs/x on GitHub, and locally if checked out.",
            ],
        ),
    ],
)
def test_the_dry_run_says_each_action_it_would_take(
    verdict: merge.Verdict, lines: list[str]
) -> None:
    assert merge.describe(merge.Preview(OPEN, verdict), delete_branch=True) == lines


def test_the_dry_run_of_a_fork_or_keep_branch_deletes_nothing() -> None:
    found = merge.Preview(
        replace(OPEN, head_repository="someone/fork"), merge.Verdict(Action.MERGE, "ok")
    )
    assert merge.describe(found, delete_branch=True) == [
        "Would merge #7 (head abc123) into main with a merge commit."
    ]


def test_a_block_with_every_check_green_is_waited_on_before_it_counts() -> None:
    assert _assess(
        replace(OPEN, mergeable_state="blocked"), block_settled=False
    ) == merge.Verdict(Action.WAIT, merge.CLEARING_BLOCK)
    assert _assess(
        replace(OPEN, mergeable_state="blocked"), block_settled=True
    ) == merge.Verdict(Action.REFUSE, "blocked by a rule other than the checks")


def test_a_merge_state_that_lags_the_last_check_still_merges() -> None:
    # The race nbkp#317 hit: the required check passed, GitHub still said "blocked".
    fake = FakeGitHub([[RUN_PASSED]], merge_states=["blocked", "clean"])
    outcome = _run(fake, Clock())
    assert outcome.merged


def test_a_block_that_outlasts_the_grace_is_refused() -> None:
    fake, clock = FakeGitHub([[RUN_PASSED]], merge_states=["blocked"]), Clock()
    outcome = _run(fake, clock, block_grace=30)
    assert not outcome.merged
    assert outcome.reason == "blocked by a rule other than the checks"
    assert clock.time >= 30


def test_time_spent_waiting_for_checks_does_not_use_up_the_grace() -> None:
    fake = FakeGitHub(
        [[RUN_PENDING]] * 10 + [[RUN_PASSED]],
        merge_states=["blocked"] * 11 + ["clean"],
    )
    outcome = _run(fake, Clock(), block_grace=30)
    assert outcome.merged

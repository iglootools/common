import json
from collections.abc import Mapping

import pytest

from iglootools.github import linkreport
from iglootools.github.client import GitHub, Repository
from iglootools.github.linkreport import LinkCheckOutcome, ReportAction, ReportIssue

CLEAN = "# Summary\n\n| Status | Count |\n|---|---|\n| ✅ Successful | 12 |\n"
BROKEN = CLEAN + "\n## Errors per input\n\n### docs/a.md\n\n* [404] https://x.test/\n"
TIMEOUTS = CLEAN + "\n## Timeouts per input\n\n### docs/a.md\n\n* https://slow.test/\n"


@pytest.mark.parametrize(
    ("report", "expected"),
    [
        (BROKEN, LinkCheckOutcome.BROKEN),
        (CLEAN, LinkCheckOutcome.CLEAN),
        (TIMEOUTS, LinkCheckOutcome.CLEAN),
        ("", LinkCheckOutcome.NOT_RAN),
        ("error: invalid value '2xx' for '--accept'\n", LinkCheckOutcome.NOT_RAN),
        (None, LinkCheckOutcome.NOT_RAN),
    ],
)
def test_the_report_says_whether_lychee_ran_and_found_broken_links(
    report: str | None,
    expected: LinkCheckOutcome,
) -> None:
    assert linkreport.classify_report(report) == expected


@pytest.mark.parametrize(
    ("broken", "open_report", "expected"),
    [
        (True, None, ReportAction.CREATE),
        (True, 3, ReportAction.UPDATE),
        (False, 3, ReportAction.CLOSE),
        (False, None, ReportAction.NOTHING),
    ],
)
def test_one_report_stays_open_while_links_are_broken(
    broken: bool,  # noqa: FBT001 - a parametrized value
    open_report: int | None,
    expected: ReportAction,
) -> None:
    assert linkreport.plan_report(broken=broken, open_report=open_report) == expected


def test_a_report_that_fits_is_the_body_as_it_is() -> None:
    assert linkreport.fit_body(BROKEN, "https://run") == BROKEN


def test_a_report_too_long_is_cut_and_points_at_the_run() -> None:
    body = linkreport.fit_body("x" * 500, "https://run", limit=200)
    assert len(body) == 200
    assert body.endswith("https://run\n")


class FakeIssues:
    """Answers the issue endpoints, recording every call."""

    def __init__(self, issues: list[dict[str, object]]) -> None:
        self.issues = issues
        self.calls: list[tuple[str, str, object]] = []

    def __call__(
        self,
        method: str,
        url: str,
        _headers: Mapping[str, str],
        body: bytes | None,
    ) -> tuple[int, bytes]:
        path = url.removeprefix("https://api.github.com")
        self.calls.append((method, path, json.loads(body) if body else None))
        match method:
            case "GET":
                return 200, json.dumps(self.issues).encode()
            case "POST" if path.endswith("/issues"):
                return 201, json.dumps({"number": 9}).encode()
            case _:
                return 200, b"{}"


ISSUE = ReportIssue(Repository("o", "r"), "Link Checker Report", ["report"])


def test_the_newest_open_issue_with_the_exact_title_is_the_report() -> None:
    fake = FakeIssues(
        [
            {"number": 2, "title": "Link Checker Report"},
            {"number": 5, "title": "Link Checker Report"},
            {"number": 7, "title": "Link Checker Report (old)"},
            {"number": 8, "title": "Link Checker Report", "pull_request": {}},
        ],
    )
    assert linkreport.find_open_report(GitHub("t", fake), ISSUE) == 5


def test_no_open_issue_with_the_title_means_no_report() -> None:
    fake = FakeIssues([{"number": 2, "title": "Something else"}])
    assert linkreport.find_open_report(GitHub("t", fake), ISSUE) is None


def test_filing_a_report_sends_its_title_body_and_labels() -> None:
    fake = FakeIssues([])
    assert linkreport.file_report(GitHub("t", fake), ISSUE, "body") == 9
    assert fake.calls == [
        (
            "POST",
            "/repos/o/r/issues",
            {"title": "Link Checker Report", "body": "body", "labels": ["report"]},
        ),
    ]


def test_updating_a_report_replaces_its_body_and_adds_the_labels() -> None:
    fake = FakeIssues([])
    linkreport.update_report(GitHub("t", fake), ISSUE, 5, "new")
    assert fake.calls == [
        ("PATCH", "/repos/o/r/issues/5", {"body": "new"}),
        ("POST", "/repos/o/r/issues/5/labels", {"labels": ["report"]}),
    ]


def test_closing_a_report_says_which_run_found_no_broken_link() -> None:
    fake = FakeIssues([])
    linkreport.close_report(GitHub("t", fake), ISSUE, 5, "https://run")
    assert fake.calls == [
        (
            "POST",
            "/repos/o/r/issues/5/comments",
            {"body": "No broken links in the latest check (https://run)."},
        ),
        (
            "PATCH",
            "/repos/o/r/issues/5",
            {"state": "closed", "state_reason": "completed"},
        ),
    ]

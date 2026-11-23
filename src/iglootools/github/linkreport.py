"""
Keep one issue reporting a project's broken links: file it, update it, close it.

lychee writes a Markdown report, and the shared link checker (reusable-check-links.yml)
hands it here. One report is open at a time: a run that finds broken links updates the
open one or files it, and a run that finds none closes it. Filing a new issue every week
left a stack of identical reports, of which only the newest was current.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from iglootools.github.client import GitHub, Repository

BODY_LIMIT = 65536
"""The most characters GitHub accepts in an issue body."""


class LinkCheckOutcome(StrEnum):
    """What a lychee report says about the run that wrote it."""

    BROKEN = "broken"
    CLEAN = "clean"
    NOT_RAN = "not-ran"


def classify_report(report: str | None) -> LinkCheckOutcome:
    """
    Read what a lychee run found from its Markdown report, None when there is none.

    The report, not lychee's exit code: lychee exits 2 both for broken links and for a
    usage error, so the code alone cannot tell "links are broken" from "lychee never
    ran", which is how an argument error was once filed as an empty issue every week.
    lychee writes `# Summary` whenever it completes, and `## Errors per input` only when
    a link failed. Timeouts have a section of their own and raise no issue: they are
    usually transient.
    """
    lines = report.splitlines() if report is not None else []
    match ("# Summary" in lines, "## Errors per input" in lines):
        case (False, _):
            return LinkCheckOutcome.NOT_RAN
        case (True, True):
            return LinkCheckOutcome.BROKEN
        case (True, False):
            return LinkCheckOutcome.CLEAN


class ReportAction(StrEnum):
    """What to do about the issue, once lychee has run."""

    CREATE = "create"
    UPDATE = "update"
    CLOSE = "close"
    NOTHING = "nothing"


def plan_report(*, broken: bool, open_report: int | None) -> ReportAction:
    """Decide what to do from whether links are broken and the open report's number."""
    match (broken, open_report):
        case (True, None):
            return ReportAction.CREATE
        case (True, int()):
            return ReportAction.UPDATE
        case (False, int()):
            return ReportAction.CLOSE
        case (False, None):
            return ReportAction.NOTHING


def fit_body(report: str, run_url: str, *, limit: int = BODY_LIMIT) -> str:
    """
    Return *report* as an issue body GitHub accepts, cut short when it is too long.

    A cut report ends by pointing at the run, whose log has the whole of it.
    """
    if len(report) <= limit:
        return report
    note = f"\n\n…cut short: the whole report is in the run's log, {run_url}\n"
    return report[: limit - len(note)] + note


@dataclass(frozen=True)
class ReportIssue:
    """Where the report is filed: the repository, and the issue's title and labels."""

    repository: Repository
    title: str
    labels: Sequence[str]


def find_open_report(github: GitHub, issue: ReportIssue) -> int | None:
    """
    Return the number of the newest open issue titled exactly as the report, or None.

    Lists the open issues rather than searching: the search index lags, and a report
    filed a minute ago would be missed.
    """
    numbers = [
        int(item["number"])
        for item in github.get_all(f"/repos/{issue.repository.slug}/issues?state=open")
        if item["title"] == issue.title and "pull_request" not in item
    ]
    return max(numbers, default=None)


def file_report(github: GitHub, issue: ReportIssue, body: str) -> int:
    """File a new report with *body*, and return its number."""
    created = github.request(
        "POST",
        f"/repos/{issue.repository.slug}/issues",
        {"title": issue.title, "body": body, "labels": list(issue.labels)},
    )
    return int(created["number"])


def update_report(github: GitHub, issue: ReportIssue, number: int, body: str) -> None:
    """Replace the body of report *number* with *body*, and add the labels."""
    path = f"/repos/{issue.repository.slug}/issues/{number}"
    github.request("PATCH", path, {"body": body})
    if issue.labels:
        github.request("POST", f"{path}/labels", {"labels": list(issue.labels)})


def close_report(github: GitHub, issue: ReportIssue, number: int, run_url: str) -> None:
    """Close report *number*, commenting with the run that found no broken link."""
    path = f"/repos/{issue.repository.slug}/issues/{number}"
    github.request(
        "POST",
        f"{path}/comments",
        {"body": f"No broken links in the latest check ({run_url})."},
    )
    github.request("PATCH", path, {"state": "closed", "state_reason": "completed"})

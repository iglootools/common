"""
Resolve the release a workflow run builds, and check out its tag.

A job that a release starts (publish, demo, a site deploy) builds the release's `v*`
tag, never whatever the branch head has become: the tag a dispatch names, otherwise the
`v*` tag on the commit the run started on. guidelines/project-setup/workflows.md, "Build
what a release triggers from its tag", gives the reasons.
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from iglootools.github.client import Run, capture

WORKFLOW_RUN = "workflow_run"
"""The event a job started by the release run's completion sees."""

_RELEASE_TAG = re.compile(r"^v\d")


class CheckoutAction(StrEnum):
    """What a run does about the release it was started for."""

    CHECKOUT = "checkout"
    SKIP = "skip"
    USE_HEAD = "use-head"
    REFUSE = "refuse"


@dataclass(frozen=True)
class CheckoutPlan:
    """The decision, and the tag to check out when the action is CHECKOUT."""

    action: CheckoutAction
    tag: str = ""


def plan_checkout(
    *,
    requested: str,
    head_tag: str | None,
    event: str,
    allow_untagged: bool,
) -> CheckoutPlan:
    """
    Decide which release a run builds, from the tag asked for and the one on HEAD.

    A tag asked for wins; otherwise the `v*` tag on HEAD. With neither, a `workflow_run`
    skips, since the release run released nothing (a dry run, a run on another branch).
    Any other run builds HEAD when *allow_untagged*, which is how a demo change is tried
    out, and is refused otherwise.
    """
    match (requested, head_tag):
        case ("", None) if event == WORKFLOW_RUN:
            return CheckoutPlan(CheckoutAction.SKIP)
        case ("", None) if allow_untagged:
            return CheckoutPlan(CheckoutAction.USE_HEAD)
        case ("", None):
            return CheckoutPlan(CheckoutAction.REFUSE)
        case ("", str() as tag):
            return CheckoutPlan(CheckoutAction.CHECKOUT, tag)
        case (tag, _):
            return CheckoutPlan(CheckoutAction.CHECKOUT, tag)


def head_release_tag(root: Path, *, run: Run = capture) -> str | None:
    """Return the `v*` tag on HEAD of the checkout at *root*, or None without one."""
    result = run(
        ["git", "describe", "--exact-match", "--tags", "--match", "v*", "HEAD"],
        root,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def is_release_tag(root: Path, tag: str, *, run: Run = capture) -> bool:
    """Whether *tag* is shaped `v<digit>…` and names a commit at *root*."""
    return bool(_RELEASE_TAG.match(tag)) and (
        run(
            ["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}^{{commit}}"],
            root,
        ).returncode
        == 0
    )


def short_head(root: Path, *, run: Run = capture) -> str:
    """Return the abbreviated commit HEAD names in the checkout at *root*."""
    return run(["git", "rev-parse", "--short", "HEAD"], root).stdout.strip()


class CheckoutError(OSError):
    """git could not check out the release tag; carries the tag and git's message."""

    def __init__(self, tag: str, detail: str) -> None:
        """Build the error from the tag and what git printed."""
        super().__init__(f"could not check out {tag}: {detail}")
        self.tag = tag
        self.detail = detail


def checkout_tag(root: Path, tag: str, *, run: Run = capture) -> None:
    """
    Check out *tag* in the checkout at *root*, on a detached HEAD.

    Raises CheckoutError with git's message when git refuses.
    """
    result = run(["git", "checkout", "-q", "--detach", f"refs/tags/{tag}"], root)
    if result.returncode != 0:
        raise CheckoutError(tag, result.stderr.strip())

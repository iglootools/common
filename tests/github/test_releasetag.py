import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from iglootools.cli import app
from iglootools.github import releasetag
from iglootools.github.releasetag import CheckoutAction, CheckoutPlan


@pytest.mark.parametrize(
    ("requested", "head_tag", "event", "allow_untagged", "expected"),
    [
        (
            "v1.2.0",
            None,
            "workflow_dispatch",
            False,
            CheckoutPlan(CheckoutAction.CHECKOUT, "v1.2.0"),
        ),
        (
            "v1.2.0",
            "v1.3.0",
            "workflow_run",
            False,
            CheckoutPlan(CheckoutAction.CHECKOUT, "v1.2.0"),
        ),
        (
            "",
            "v1.3.0",
            "workflow_run",
            False,
            CheckoutPlan(CheckoutAction.CHECKOUT, "v1.3.0"),
        ),
        ("", None, "workflow_run", True, CheckoutPlan(CheckoutAction.SKIP)),
        ("", None, "workflow_dispatch", True, CheckoutPlan(CheckoutAction.USE_HEAD)),
        ("", None, "workflow_dispatch", False, CheckoutPlan(CheckoutAction.REFUSE)),
    ],
)
def test_the_plan_follows_the_tag_asked_for_then_the_one_on_head(
    requested: str,
    head_tag: str | None,
    event: str,
    allow_untagged: bool,  # noqa: FBT001 - a parametrized value
    expected: CheckoutPlan,
) -> None:
    plan = releasetag.plan_checkout(
        requested=requested,
        head_tag=head_tag,
        event=event,
        allow_untagged=allow_untagged,
    )
    assert plan == expected


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit(repo: Path, message: str) -> str:
    _git(
        repo,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.com",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        message,
    )
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def released(git_repo: Path) -> Path:
    """Return a repository tagged v1.0.0, with an untagged commit on top."""
    _commit(git_repo, "release")
    _git(git_repo, "tag", "v1.0.0")
    _commit(git_repo, "after the release")
    return git_repo


def test_head_without_a_tag_has_no_release_tag(released: Path) -> None:
    assert releasetag.head_release_tag(released) is None


def test_a_tagged_head_names_its_release_tag(released: Path) -> None:
    _git(released, "checkout", "-q", "v1.0.0")
    assert releasetag.head_release_tag(released) == "v1.0.0"


@pytest.mark.parametrize(
    ("tag", "expected"),
    [("v1.0.0", True), ("v9.9.9", False), ("main", False), ("vX", False)],
)
def test_only_an_existing_v_digit_tag_is_a_release_tag(
    released: Path,
    tag: str,
    expected: bool,  # noqa: FBT001 - a parametrized value
) -> None:
    assert releasetag.is_release_tag(released, tag) is expected


def test_checking_out_a_tag_detaches_head_at_its_commit(released: Path) -> None:
    releasetag.checkout_tag(released, "v1.0.0")
    assert _git(released, "rev-parse", "HEAD") == _git(released, "rev-parse", "v1.0.0")


def _invoke(root: Path, output: Path, *args: str) -> tuple[int, str, str]:
    result = CliRunner().invoke(
        app,
        [
            "--root",
            str(root),
            "github",
            "checkout-release",
            "--github-output",
            str(output),
            *args,
        ],
    )
    written = output.read_text(encoding="utf-8") if output.exists() else ""
    return result.exit_code, result.output, written


def test_a_requested_tag_is_checked_out_and_named_in_the_outputs(
    released: Path,
    tmp_path: Path,
) -> None:
    code, _, written = _invoke(
        released,
        tmp_path / "out",
        "--tag",
        "v1.0.0",
        "--event",
        "workflow_dispatch",
    )
    assert (code, written) == (0, "skip=false\ntag=v1.0.0\n")
    assert releasetag.head_release_tag(released) == "v1.0.0"


def test_a_workflow_run_on_an_untagged_commit_skips(
    released: Path,
    tmp_path: Path,
) -> None:
    code, output, written = _invoke(
        released,
        tmp_path / "out",
        "--event",
        "workflow_run",
    )
    assert (code, written) == (0, "skip=true\ntag=\n")
    assert output.startswith("::notice::")


def test_a_dispatch_on_an_untagged_commit_fails_saying_how_to_pass_the_tag(
    released: Path,
    tmp_path: Path,
) -> None:
    code, output, written = _invoke(
        released,
        tmp_path / "out",
        "--event",
        "workflow_dispatch",
    )
    assert (code, written) == (1, "")
    assert "-f tag=vX.Y.Z" in output


def test_a_tag_the_repository_lacks_is_refused(released: Path, tmp_path: Path) -> None:
    code, output, written = _invoke(
        released,
        tmp_path / "out",
        "--tag",
        "v9.9.9",
        "--event",
        "workflow_dispatch",
    )
    assert (code, written) == (1, "")
    assert output.startswith("::error::v9.9.9 is not a release tag")

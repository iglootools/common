import json
from collections.abc import Mapping
from pathlib import Path

from iglootools.github.client import GitHub
from iglootools.workspace import status
from iglootools.workspace.repositories import OrganizationRepository
from iglootools.workspace.status import RepositoryStatus
from tests.conftest import advance_origin, commit, git

CHECKOUT = OrganizationRepository(
    "checkout",
    archived=False,
    default_branch="main",
    ssh_url="",
    https_url="",
)


def _github(authors: list[str], *, status_code: int = 200) -> GitHub:
    def transport(
        _method: str,
        url: str,
        _headers: Mapping[str, str],
        _body: bytes | None,
    ) -> tuple[int, bytes]:
        assert "/repos/iglootools/checkout/pulls?state=open" in url
        if status_code != 200:
            return status_code, b'{"message": "Server Error"}'
        pulls = [{"user": {"login": author}} for author in authors]
        return 200, json.dumps(pulls if url.endswith("page=1") else []).encode()

    return GitHub("t", transport=transport)


def test_a_checkout_s_branch_changes_and_standing_are_read(clone: Path) -> None:
    advance_origin(clone)
    commit(clone, "local")
    git(clone, "branch", "feat/x")
    (clone / "notes.txt").write_text("wip", encoding="utf-8")
    found = status.read_status(
        clone,
        CHECKOUT,
        _github(["renovate[bot]", "someone"]),
        fetch=True,
    )
    assert found == RepositoryStatus(
        "checkout",
        cloned=True,
        branch="main",
        changes=1,
        ahead=1,
        behind=1,
        branches=["feat/x"],
        worktrees=0,
        open_pulls=2,
        renovate_pulls=1,
    )


def test_without_fetch_origin_is_compared_as_last_fetched(clone: Path) -> None:
    advance_origin(clone)
    found = status.read_status(clone, CHECKOUT, _github([]), fetch=False)
    assert (found.ahead, found.behind) == (0, 0)


def test_a_repository_not_cloned_still_counts_its_pull_requests(tmp_path: Path) -> None:
    found = status.read_status(
        tmp_path / "checkout",
        CHECKOUT,
        _github(["someone"]),
        fetch=True,
    )
    assert found == RepositoryStatus("checkout", cloned=False, open_pulls=1)


def test_github_refusing_is_the_status_s_problem(clone: Path) -> None:
    found = status.read_status(
        clone,
        CHECKOUT,
        _github([], status_code=500),
        fetch=True,
    )
    assert found.cloned
    assert found.problem.endswith("500 Server Error")

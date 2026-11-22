import json
from collections.abc import Mapping

import pytest

from iglootools.github import prune
from iglootools.github.client import GitHub, Repository
from iglootools.github.prune import Branch, PullState

REPO = Repository("iglootools", "nbkp")


def _branch(
    name: str, pull: PullState = PullState.NONE, protected: bool = False
) -> Branch:
    return Branch(
        name, on_remote=True, local=False, protected=protected, pull=pull, pull_number=3
    )


@pytest.mark.parametrize(
    ("branch", "delete", "reason"),
    [
        (_branch("feat/x", PullState.MERGED), True, "#3 merged"),
        (_branch("renovate/all", PullState.OPEN), False, "#3 open"),
        (_branch("fix/y", PullState.CLOSED), False, "#3 closed without merging"),
        (_branch("gh-pages"), False, "no pull request"),
        (_branch("release", PullState.MERGED, protected=True), False, "protected"),
        (_branch("main", PullState.MERGED), False, "default branch"),
    ],
)
def test_only_a_branch_whose_latest_pull_request_merged_is_deleted(
    branch: Branch, delete: bool, reason: str
) -> None:
    assert prune.decide(branch, "main") == prune.Decision(branch, delete, reason)


class FakeGitHub:
    def __init__(
        self,
        branch_pages: list[list[dict[str, object]]],
        pulls: Mapping[str, list[dict[str, object]]],
    ) -> None:
        self.branch_pages = branch_pages
        self.pulls = pulls

    def __call__(
        self, method: str, url: str, headers: Mapping[str, str], body: bytes | None
    ) -> tuple[int, bytes]:
        path = url.removeprefix("https://api.github.com")
        if path == "/repos/iglootools/nbkp":
            return 200, json.dumps({"default_branch": "main"}).encode()
        if path.startswith("/repos/iglootools/nbkp/branches?"):
            page = int(path.rsplit("page=", 1)[1])
            return 200, json.dumps(self.branch_pages[page - 1]).encode()
        if path.startswith("/repos/iglootools/nbkp/pulls?"):
            head = path.split("head=iglootools:", 1)[1].split("&", 1)[0]
            return 200, json.dumps(self.pulls.get(head, [])).encode()
        raise AssertionError(f"unexpected {method} {path}")


def test_gather_reads_every_page_and_each_branch_s_latest_pull_request() -> None:
    full_page: list[dict[str, object]] = [
        {"name": f"b{i}", "protected": False} for i in range(100)
    ]
    fake = FakeGitHub(
        [full_page, [{"name": "main", "protected": True}, {"name": "gh-pages"}]],
        {
            "b0": [
                {"number": 9, "state": "closed", "merged_at": "2026-11-21T00:00:00Z"}
            ],
            "b1": [{"number": 8, "state": "open", "merged_at": None}],
            "b2": [{"number": 7, "state": "closed", "merged_at": None}],
        },
    )
    default, branches = prune.gather(GitHub("t", transport=fake), REPO, ["local-only"])
    by_name = {branch.name: branch for branch in branches}
    assert default == "main" and "main" not in by_name
    assert len(branches) == 102  # 100 + gh-pages + local-only
    assert (by_name["b0"].pull, by_name["b0"].pull_number) == (PullState.MERGED, 9)
    assert by_name["b1"].pull == PullState.OPEN
    assert by_name["b2"].pull == PullState.CLOSED
    assert by_name["gh-pages"].pull == PullState.NONE
    assert by_name["local-only"].local and not by_name["local-only"].on_remote

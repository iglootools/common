import json
from collections.abc import Mapping

from iglootools.github import merge
from iglootools.github.client import GitHub
from iglootools.workspace import renovate
from iglootools.workspace.renovate import RenovatePull
from iglootools.workspace.repositories import OrganizationRepository
from tests.conftest import UnexpectedCallError

NBKP = OrganizationRepository(
    "nbkp",
    archived=False,
    default_branch="main",
    ssh_url="",
    https_url="",
)


def _pull(number: int, *, mergeable_state: str = "clean") -> dict[str, object]:
    return {
        "number": number,
        "state": "open",
        "merged": False,
        "draft": False,
        "mergeable_state": mergeable_state,
        "head": {
            "sha": f"sha{number}",
            "ref": f"renovate/{number}",
            "repo": {"full_name": "iglootools/nbkp"},
        },
        "base": {"ref": "main", "repo": {"full_name": "iglootools/nbkp"}},
    }


class FakeGitHub:
    """Answers the listing and what merge.preview reads, with green checks."""

    def __init__(self, failing: frozenset[int] = frozenset()) -> None:
        self.failing = failing

    def __call__(
        self,
        method: str,
        url: str,
        _headers: Mapping[str, str],
        _body: bytes | None,
    ) -> tuple[int, bytes]:
        path = url.removeprefix("https://api.github.com/repos/iglootools/nbkp")
        if path.startswith("/pulls?state=open"):
            listed = [
                {"number": 1, "title": "update uv", "user": {"login": "renovate[bot]"}},
                {"number": 2, "title": "a feature", "user": {"login": "someone"}},
                {"number": 3, "title": "conflicts", "user": {"login": "renovate[bot]"}},
            ]
            return 200, json.dumps(listed if path.endswith("page=1") else []).encode()
        match path:
            case "/pulls/1":
                return 200, json.dumps(_pull(1)).encode()
            case "/pulls/3" if 3 in self.failing:
                return 502, b'{"message": "Bad Gateway"}'
            case "/pulls/3":
                return 200, json.dumps(_pull(3, mergeable_state="dirty")).encode()
            case "/rules/branches/main":
                return 200, b"[]"
            case _ if path.endswith("/check-runs?per_page=100"):
                runs = [
                    {
                        "name": "preflight",
                        "status": "completed",
                        "conclusion": "success",
                    },
                ]
                return 200, json.dumps({"check_runs": runs}).encode()
            case _ if path.endswith("/status"):
                return 200, b'{"statuses": []}'
            case _:
                raise UnexpectedCallError((method, path))


def test_only_renovate_s_pull_requests_are_listed_with_their_verdict() -> None:
    found = renovate.find_pulls(GitHub("t", transport=FakeGitHub()), NBKP)
    assert [(pull.number, pull.verdict) for pull in found] == [
        (1, merge.Verdict(merge.Action.MERGE, "every check passed")),
        (3, merge.Verdict(merge.Action.REFUSE, "conflicts with main")),
    ]
    assert [pull.mergeable for pull in found] == [True, False]


def test_a_pull_request_that_cannot_be_assessed_carries_its_problem() -> None:
    github = GitHub("t", transport=FakeGitHub(failing=frozenset({3})))
    found = renovate.find_pulls(github, NBKP)
    assert found[1] == RenovatePull(
        NBKP,
        3,
        "conflicts",
        problem="GET /repos/iglootools/nbkp/pulls/3: 502 Bad Gateway",
    )
    assert not found[1].mergeable

import base64
import json
import subprocess
import threading
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager
from pathlib import Path

import pytest

from iglootools.common import adopt, adopt_all
from iglootools.common.adopt_all import Project, Skipped
from iglootools.github.client import GitHub, GitHubError, GitHubErrorKind, Repository
from iglootools.github.events import Event, Report, Stage
from iglootools.workspace.repositories import OrganizationRepository
from tests.conftest import UnexpectedCallError

ORIGINS = {
    "common": "git@github.com:iglootools/common.git",
    "nbkp": "git@github.com:iglootools/nbkp.git",
    ".github": "git@github.com:iglootools/.github.git",
    "photree": "git@github.com:someone/photree.git",
    "old": "git@github.com:iglootools/old.git",
}
PINS = {
    "nbkp": "uses: iglootools/common/.github/workflows/r.yml@"
    + "a" * 40
    + " # v1.33.1\n",
}


def _repository(name: str, *, archived: bool = False) -> OrganizationRepository:
    return OrganizationRepository(
        name,
        archived=archived,
        default_branch="main",
        ssh_url="",
        https_url="",
    )


def _workspace(tmp_path: Path) -> Path:
    for name in ORIGINS:
        (tmp_path / name / ".git").mkdir(parents=True)
        if name in PINS:
            (tmp_path / name / "release.yml").write_text(PINS[name])
    (tmp_path / "unrelated").mkdir()
    return tmp_path


def _git(command: Sequence[str], directory: Path) -> subprocess.CompletedProcess[str]:
    match list(command):
        case ["git", "remote", "get-url", "origin"]:
            return subprocess.CompletedProcess(
                command,
                0,
                ORIGINS[directory.name] + "\n",
                "",
            )
        case ["git", "ls-files", "-z"]:
            names = [p.name for p in directory.iterdir() if p.is_file()]
            return subprocess.CompletedProcess(command, 0, "\0".join(names), "")
        case _:
            raise UnexpectedCallError(command)


def test_discovery_sorts_the_organization_by_what_the_workspace_holds(
    tmp_path: Path,
) -> None:
    repositories = [
        _repository(".github"),
        _repository("common"),
        _repository("nbkp"),
        _repository("newproject"),
        _repository("old", archived=True),
        _repository("photree"),
    ]
    found = adopt_all.discover(_workspace(tmp_path), repositories, run=_git)
    assert found.projects == [
        Project("nbkp", tmp_path / "nbkp", Repository("iglootools", "nbkp")),
    ]
    assert found.skipped == [
        Skipped(".github", "pins nothing on common"),
        Skipped("old", "archived"),
        Skipped("photree", "its origin is someone/photree, not iglootools/photree"),
    ]
    assert found.not_checked_out == [_repository("newproject")]


PROJECTS = [
    Project(name, Path(name), Repository("iglootools", name))
    for name in ("alberta-hiking-resources", "nbkp", "photree")
]


def test_only_and_exclude_narrow_the_selection() -> None:
    selected, left_out = adopt_all.select(
        PROJECTS,
        only=["nbkp", "photree"],
        exclude=["photree"],
    )
    assert [p.name for p in selected] == ["nbkp"]
    assert left_out == [
        Skipped("alberta-hiking-resources", "not in --only"),
        Skipped("photree", "excluded"),
    ]


def test_naming_a_project_the_workspace_lacks_is_an_error() -> None:
    with pytest.raises(adopt_all.SelectionError) as raised:
        adopt_all.select(PROJECTS, only=["nbpk"], exclude=[])
    assert raised.value.unknown == ("nbpk",)


def _config(text: str) -> bytes:
    content = base64.b64encode(text.encode()).decode()
    return json.dumps({"content": content, "encoding": "base64"}).encode()


RENOVATE_CONFIGS = {
    "newproject": _config('{"extends": ["github>iglootools/common//renovate/base"]}'),
    "docs-site": _config('{"extends": ["config:recommended"]}'),
}


def _organization(
    contents_status: int = 404,
) -> Callable[[str, str, Mapping[str, str], bytes | None], tuple[int, bytes]]:
    def transport(
        _method: str,
        url: str,
        _headers: Mapping[str, str],
        _body: bytes | None,
    ) -> tuple[int, bytes]:
        path = url.removeprefix("https://api.github.com")
        name = path.removeprefix("/repos/iglootools/").removesuffix(
            "/contents/renovate.json",
        )
        if name in RENOVATE_CONFIGS:
            return 200, RENOVATE_CONFIGS[name]
        return contents_status, b'{"message": "Not Found"}'

    return transport


def test_every_repository_without_a_checkout_is_sorted_by_whether_it_pins_common() -> (
    None
):
    unchecked = adopt_all.find_unchecked(
        GitHub("t", transport=_organization()),
        [_repository("docs-site"), _repository("empty"), _repository("newproject")],
    )
    assert unchecked.missing == ["newproject"]
    assert unchecked.passed_over == [
        Skipped(
            "docs-site",
            "not checked out, and its renovate.json does not extend iglootools/common",
        ),
        Skipped(
            "empty",
            "not checked out, and its renovate.json does not extend iglootools/common",
        ),
    ]


def test_a_renovate_config_github_will_not_serve_stops_the_run() -> None:
    with pytest.raises(GitHubError) as raised:
        adopt_all.find_unchecked(
            GitHub("t", transport=_organization(contents_status=500)),
            [_repository("newproject"), _repository("empty")],
        )
    assert raised.value.status == 500


@pytest.mark.parametrize(
    ("config", "extends"),
    [
        ('{"extends": ["github>iglootools/common//renovate/base#v2.5.0"]}', True),
        ('{"extends": ["config:recommended"]}', False),
        (None, False),
    ],
)
def test_extends_common_reads_the_renovate_config(
    config: str | None,
    *,
    extends: bool,
) -> None:
    assert adopt_all.extends_common(config) is extends


def _reach(status: int) -> Callable[..., subprocess.CompletedProcess[str]]:
    def run(
        command: Sequence[str],
        _directory: Path,
    ) -> subprocess.CompletedProcess[str]:
        assert list(command[:2]) == ["git", "ls-remote"], command
        return subprocess.CompletedProcess(
            command,
            status,
            "",
            "Permission denied (publickey).\n",
        )

    return run


def test_an_unreachable_origin_is_found_before_anything_changes() -> None:
    assert adopt_all.problems(PROJECTS[1], run=_reach(128)) == [
        (
            "cannot reach origin without a prompt (Permission denied (publickey).); "
            "load your key with `ssh-add`, or log in to git over HTTPS"
        ),
    ]


def test_a_reachable_project_is_ready_whatever_its_checkout_holds() -> None:
    # Only ls-remote runs: the checkout's branch and changes are never looked at,
    # since adopt works in a worktree started from GitHub's default branch.
    assert adopt_all.problems(PROJECTS[1], run=_reach(0)) == []


def test_describe_appends_the_notes_an_error_carries() -> None:
    error = RuntimeError("boom")
    error.add_note("The worktree is kept at /tmp/w.")
    assert adopt_all.describe(error, "push failed") == (
        "push failed The worktree is kept at /tmp/w."
    )


def test_every_project_runs_and_one_failure_does_not_stop_the_others() -> None:
    guards: list[AbstractContextManager[object]] = []
    events: list[tuple[str, Event]] = []

    def adopt_one(
        project: Project,
        report: Report,
        _sleep: Callable[[float], None],
        push_guard: AbstractContextManager[object],
    ) -> adopt.Outcome:
        guards.append(push_guard)
        report(Event(Stage.OPENED, f"Opened {project.name}", 1))
        if project.name == "nbkp":
            raise GitHubError(GitHubErrorKind.REQUEST_FAILED, "POST pulls: 422 exists")
        return adopt.Outcome(adopt.Result.MERGED, "merged", 1)

    outcomes = adopt_all.run_all(
        PROJECTS,
        adopt_one,
        report=lambda n, e: events.append((n, e)),
        stop=threading.Event(),
    )
    assert outcomes["alberta-hiking-resources"].result == adopt.Result.MERGED
    assert outcomes["photree"].result == adopt.Result.MERGED
    assert outcomes["nbkp"] == adopt.Outcome(
        adopt.Result.REFUSED,
        "POST pulls: 422 exists",
    )
    assert len({id(guard) for guard in guards}) == 1  # one guard: pushes take turns
    assert sorted(name for name, _ in events) == sorted(p.name for p in PROJECTS)


def test_an_interrupted_run_stops_each_project_at_its_next_sleep() -> None:
    stop = threading.Event()
    stop.set()

    def adopt_one(
        _project: Project,
        _report: Report,
        sleep: Callable[[float], None],
        _push_guard: AbstractContextManager[object],
    ) -> adopt.Outcome:
        sleep(60)
        return adopt.Outcome(adopt.Result.MERGED, "merged")

    outcomes = adopt_all.run_all(
        PROJECTS,
        adopt_one,
        report=lambda _n, _e: None,
        stop=stop,
    )
    assert {o.reason for o in outcomes.values()} == {"interrupted; run again to resume"}

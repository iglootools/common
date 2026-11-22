import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from iglootools.common import pins
from iglootools.github.client import GitHub, GitHubError
from tests.conftest import track

OLD = "a" * 40
NEW = "b" * 40


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (
            f"    uses: iglootools/common/.github/workflows/reusable-release.yml@{OLD} # v1.31.0\n",
            f"    uses: iglootools/common/.github/workflows/reusable-release.yml@{NEW} # v1.32.2\n",
        ),
        (
            '  "iglootools @ git+https://github.com/iglootools/common@v1.31.0",\n',
            '  "iglootools @ git+https://github.com/iglootools/common@v1.32.2",\n',
        ),
        (
            '    "github>iglootools/common//renovate/python#v1.31.0"\n',
            '    "github>iglootools/common//renovate/python#v1.32.2"\n',
        ),
        ('IGLOOTOOLS_VERSION = "v1.31.0"\n', 'IGLOOTOOLS_VERSION = "v1.32.2"\n'),
    ],
)
def test_each_kind_of_pin_moves(before: str, after: str) -> None:
    assert pins.rewrite(before, "1.32.2", NEW) == pins.Rewrite(after, 1)


def test_text_that_pins_nothing_on_common_is_left_alone() -> None:
    text = (
        "    uses: actions/checkout@" + OLD + " # v5\n"
        '  "other @ git+https://github.com/someone/else@v1.0.0",\n'
        "# see iglootools/common v1.31.0 for why\n"
    )
    assert pins.rewrite(text, "1.32.2", NEW) == pins.Rewrite(text, 0)


def test_candidate_files_are_every_tracked_file_that_mentions_common(
    git_repo: Path,
) -> None:
    track(git_repo, ".github/workflows/release.yml", "uses: iglootools/common/x")
    track(
        git_repo,
        "Dockerfile",
        "RUN uvx --from git+https://github.com/iglootools/common@v1.0.0 x",
    )
    track(git_repo, "uv.lock", "iglootools/common?rev=v1.0.0#" + "a" * 40)
    track(git_repo, "README.md", "nothing here")
    (git_repo / "untracked.toml").write_text("iglootools/common@v1.0.0")
    names = sorted(
        path.relative_to(git_repo).as_posix() for path in pins.candidate_files(git_repo)
    )
    assert names == [".github/workflows/release.yml", "Dockerfile"]


def _transport(responses: Mapping[str, tuple[int, object]]):
    def transport(
        method: str, url: str, headers: Mapping[str, str], body: bytes | None
    ) -> tuple[int, bytes]:
        status, payload = responses[url.removeprefix("https://api.github.com")]
        return status, json.dumps(payload).encode()

    return transport


def test_an_annotated_tag_resolves_to_its_commit() -> None:
    github = GitHub(
        "t",
        transport=_transport(
            {
                "/repos/iglootools/common/git/ref/tags/v1.32.2": (
                    200,
                    {"object": {"type": "tag", "sha": "tagobj"}},
                ),
                "/repos/iglootools/common/git/tags/tagobj": (
                    200,
                    {"object": {"type": "commit", "sha": NEW}},
                ),
            }
        ),
    )
    assert pins.tag_commit(github, "1.32.2") == NEW


def test_a_missing_release_says_so() -> None:
    github = GitHub(
        "t",
        transport=_transport(
            {
                "/repos/iglootools/common/git/ref/tags/v9.9.9": (
                    404,
                    {"message": "Not Found"},
                ),
            }
        ),
    )
    with pytest.raises(GitHubError, match="has no release v9.9.9"):
        pins.tag_commit(github, "9.9.9")


ROOT = Path("/project")


def _refs(text: str) -> list[pins.Reference]:
    return pins.references(ROOT / "x.yml", text)


def test_each_pin_is_found_with_its_release_and_commit() -> None:
    found = _refs(
        f"    uses: iglootools/common/.github/workflows/r.yml@{OLD} # v1.33.0\n"
        'IGLOOTOOLS_VERSION = "v1.33.0"\n'
        "see iglootools/common for why, and blob/main/x.md#anchor\n"
    )
    assert [(r.line, r.version, r.sha, r.movable) for r in found] == [
        (1, "1.33.0", OLD, True),
        (2, "1.33.0", None, True),
    ]


def test_a_spelling_adopt_would_not_move_is_flagged() -> None:
    # A pin the broad pattern sees but the rewrite does not, such as a raw SHA URL.
    found = _refs(f"curl https://raw.githubusercontent.com/iglootools/common@{OLD}/x\n")
    assert found and not found[0].movable
    assert "adopt would not move this pin" in pins.problems(found, None, ROOT)[0]


def test_pins_on_different_releases_disagree() -> None:
    found = _refs(
        'IGLOOTOOLS_VERSION = "v1.32.2"\n'
        '"github>iglootools/common//renovate/base#v1.33.0"\n'
    )
    assert (
        pins.problems(found, None, ROOT)[0]
        == "the pins name different releases: 1.32.2, 1.33.0"
    )


def test_a_sha_pin_without_its_tag_comment_is_flagged() -> None:
    found = _refs(f"uses: iglootools/common/.github/workflows/r.yml@{OLD}\n")
    issues = pins.problems(found, None, ROOT)
    assert any("no `# vX.Y.Z` comment" in issue for issue in issues)
    assert any("adopt would not move this pin" in issue for issue in issues)


def test_workflow_shas_must_be_the_commit_uv_lock_resolved() -> None:
    found = _refs(f"uses: iglootools/common/.github/workflows/r.yml@{OLD} # v1.33.0\n")
    lock = pins.locked(
        f'source = {{ git = "https://github.com/iglootools/common?rev=v1.33.0#{NEW}" }}'
    )
    assert lock == pins.Locked("1.33.0", NEW)
    assert "is not v1.33.0's commit" in pins.problems(found, lock, ROOT)[0]


def test_consistent_pins_have_no_problems() -> None:
    found = _refs(
        f"uses: iglootools/common/.github/workflows/r.yml@{NEW} # v1.33.0\n"
        '"iglootools @ git+https://github.com/iglootools/common@v1.33.0",\n'
    )
    assert pins.problems(found, pins.Locked("1.33.0", NEW), ROOT) == []

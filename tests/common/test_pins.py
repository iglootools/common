import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from iglootools.common import pins
from iglootools.github.client import GitHub, GitHubError

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


def test_candidate_files_are_the_workflows_and_the_files_that_pin(
    tmp_path: Path,
) -> None:
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    for name in (
        ".github/workflows/release.yml",
        "mise.toml",
        "renovate.json",
        "README.md",
    ):
        (tmp_path / name).write_text("x")
    names = [
        path.relative_to(tmp_path).as_posix() for path in pins.candidate_files(tmp_path)
    ]
    assert names == [".github/workflows/release.yml", "mise.toml", "renovate.json"]


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

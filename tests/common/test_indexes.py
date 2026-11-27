from pathlib import Path, PurePosixPath

from iglootools.common import indexes
from iglootools.common.indexes import Unlisted
from tests.conftest import track


def _complete(repo: Path) -> None:
    track(
        repo,
        "guidelines/README.md",
        "[philosophy.md](philosophy.md) [coding/](coding/README.md)\n",
    )
    track(repo, "guidelines/philosophy.md", "# Philosophy\n")
    track(
        repo,
        "guidelines/coding/README.md",
        "[general.md](general.md) [t](templates/x.md.template)\n",
    )
    track(repo, "guidelines/coding/general.md", "# General\n")
    track(repo, "guidelines/coding/templates/x.md.template", "x\n")


def test_find_unlisted_is_empty_when_every_file_is_listed(git_repo: Path) -> None:
    _complete(git_repo)
    assert indexes.find_unlisted(git_repo) == []


def test_find_unlisted_reports_a_file_missing_from_its_directory_index(
    git_repo: Path,
) -> None:
    _complete(git_repo)
    track(git_repo, "guidelines/coding/python.md", "# Python\n")
    track(git_repo, "guidelines/coding/templates/y.md.template", "y\n")
    assert indexes.find_unlisted(git_repo) == [
        Unlisted(PurePosixPath("guidelines/coding/README.md"), "python.md"),
        Unlisted(
            PurePosixPath("guidelines/coding/README.md"),
            "templates/y.md.template",
        ),
    ]


def test_find_unlisted_reports_a_directory_or_guideline_missing_from_the_map(
    git_repo: Path,
) -> None:
    _complete(git_repo)
    track(git_repo, "guidelines/review/README.md", "")
    track(git_repo, "guidelines/cross-cutting-concerns.md", "# Concerns\n")
    assert indexes.find_unlisted(git_repo) == [
        Unlisted(PurePosixPath("guidelines/README.md"), "review/README.md"),
        Unlisted(PurePosixPath("guidelines/README.md"), "cross-cutting-concerns.md"),
    ]


def test_find_unlisted_reports_every_file_of_a_directory_without_an_index(
    git_repo: Path,
) -> None:
    _complete(git_repo)
    track(git_repo, "guidelines/review/audit.md", "# Audit\n")
    assert indexes.find_unlisted(git_repo) == [
        Unlisted(PurePosixPath("guidelines/README.md"), "review/README.md"),
        Unlisted(PurePosixPath("guidelines/review/README.md"), "audit.md"),
    ]


def test_find_unlisted_ignores_untracked_files(git_repo: Path) -> None:
    _complete(git_repo)
    (git_repo / "guidelines/coding/.DS_Store").write_bytes(b"\0")
    assert indexes.find_unlisted(git_repo) == []

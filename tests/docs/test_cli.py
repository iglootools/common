from pathlib import Path

from typer.testing import CliRunner

from iglootools.cli import app
from tests.conftest import track

runner = CliRunner()

GUIDE = "# Guide\n\nIntro.\n\n## First\n\n## Second\n"


def iglootools(repo: Path, *args: str) -> tuple[int, str]:
    result = runner.invoke(app, ["--root", str(repo), *args])
    return result.exit_code, result.output


def test_add_then_regenerate_fills_the_block(git_repo: Path) -> None:
    guide = track(git_repo, "docs/guide.md", GUIDE)
    code, output = iglootools(git_repo, "docs", "toc", "--add", str(guide))
    assert (code, output) == (0, "Updated docs/guide.md\n")
    assert "- [First](#first)\n- [Second](#second)\n" in guide.read_text()


def test_check_lists_a_stale_file_and_fails(git_repo: Path) -> None:
    track(
        git_repo, "guide.md", GUIDE.replace("Intro.", "<!-- toc -->\n<!-- tocstop -->")
    )
    code, output = iglootools(git_repo, "docs", "toc", "--check")
    assert code == 1
    assert "Out of date: guide.md" in output
    assert "iglootools docs toc" in output


def test_check_passes_once_regenerated(git_repo: Path) -> None:
    track(
        git_repo, "guide.md", GUIDE.replace("Intro.", "<!-- toc -->\n<!-- tocstop -->")
    )
    iglootools(git_repo, "docs", "toc")
    assert iglootools(git_repo, "docs", "toc", "--check") == (
        0,
        "1 table(s) of contents up to date.\n",
    )


def test_untracked_files_are_left_alone(git_repo: Path) -> None:
    untracked = git_repo / "notes.md"
    untracked.write_text("<!-- toc -->\n<!-- tocstop -->\n## A\n", encoding="utf-8")
    assert iglootools(git_repo, "docs", "toc")[0] == 0
    assert untracked.read_text() == "<!-- toc -->\n<!-- tocstop -->\n## A\n"


def test_add_reports_a_file_without_sections(git_repo: Path) -> None:
    title_only = track(git_repo, "title.md", "# Title only\n")
    code, output = iglootools(git_repo, "docs", "toc", "--add", str(title_only))
    assert code == 1
    assert output.startswith("title.md: no ## or ### heading")


def test_add_cannot_be_combined_with_check(git_repo: Path) -> None:
    guide = track(git_repo, "guide.md", GUIDE)
    code, _ = iglootools(git_repo, "docs", "toc", "--check", "--add", str(guide))
    assert code == 2
    assert "<!-- toc -->" not in guide.read_text()


def test_version_names_the_package() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.startswith("iglootools ")

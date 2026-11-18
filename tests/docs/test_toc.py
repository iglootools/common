from pathlib import Path
from textwrap import dedent

import pytest

from iglootools.docs import toc as markdown_toc

# Expected anchors come from github-slugger 2.0.0, given each heading's text as GitHub
# renders it (code spans, links and emphasis reduced to their text). They are the
# reference: rerun that comparison before changing slug() rather than updating them.
GITHUB_ANCHORS = [
    (
        "Fold rework into the commit it corrects",
        "fold-rework-into-the-commit-it-corrects",
    ),
    (
        "Invoke tools through `uv run --no-sync <tool>` in mise tasks, not bare",
        "invoke-tools-through-uv-run---no-sync-tool-in-mise-tasks-not-bare",
    ),
    ("One `ci-*` task per workflow job", "one-ci--task-per-workflow-job"),
    (
        "Let `hverlin.mise-vscode` write the other tools' paths",
        "let-hverlinmise-vscode-write-the-other-tools-paths",
    ),
    (
        "High cohesion, low coupling — at every boundary",
        "high-cohesion-low-coupling--at-every-boundary",
    ),
    (
        "Chain publish to release with `workflow_run`",
        "chain-publish-to-release-with-workflow_run",
    ),
    ("Use [links](https://example.com) in headings", "use-links-in-headings"),
    ("**Bold** and _emphasis_", "bold-and-emphasis"),
    ("*Star* emphasis", "star-emphasis"),
    ("C++ & Rust: 100% safe?", "c--rust-100-safe"),
    ("Café déjà vu", "café-déjà-vu"),
    ("Emoji 🚀 launch", "emoji--launch"),
    ("Don’t “smart” quote", "dont-smart-quote"),
    ("snake_case_name", "snake_case_name"),
    ("日本語の見出し", "日本語の見出し"),
    ("a/b\\c|d", "abcd"),
    ("version 1.2.3", "version-123"),
    ("x = y + z", "x--y--z"),
]


@pytest.mark.parametrize(("heading", "anchor"), GITHUB_ANCHORS)
def test_slug_matches_github(heading: str, anchor: str) -> None:
    assert markdown_toc.slug(heading) == anchor


def test_heading_trailing_spaces_and_closing_hashes_are_not_part_of_it() -> None:
    [heading] = markdown_toc.headings("## Trailing spaces ##   \n")
    assert (heading.text, heading.anchor) == ("Trailing spaces", "trailing-spaces")


def test_repeated_anchors_skip_suffixes_already_taken() -> None:
    markdown = "## Repeated\n## Repeated\n## Repeated-1\n## Repeated\n"
    assert [h.anchor for h in markdown_toc.headings(markdown)] == [
        "repeated",
        "repeated-1",
        "repeated-1-1",
        "repeated-2",
    ]


def test_a_suffix_skips_an_anchor_a_heading_took_literally() -> None:
    markdown = "## Repeated-1\n## Repeated\n## Repeated\n"
    assert [h.anchor for h in markdown_toc.headings(markdown)] == [
        "repeated-1",
        "repeated",
        "repeated-2",
    ]


def test_headings_inside_code_fences_are_ignored() -> None:
    markdown = dedent("""\
        ## Before

        ````markdown
        ## Inside four backticks
        ```
        ## Still inside: a shorter fence does not close it
        ````

        ~~~
        ## Inside tildes
        ~~~

        ## After
        """)
    assert [h.text for h in markdown_toc.headings(markdown)] == ["Before", "After"]


def test_toc_lists_levels_two_and_three_nested() -> None:
    markdown = dedent("""\
        # Title

        <!-- toc -->
        <!-- tocstop -->

        ## Section [with a link](https://example.com)
        ### Sub `code`
        #### Too deep to list
        ## Next
        """)
    assert markdown_toc.with_toc(markdown) == dedent("""\
        # Title

        <!-- toc -->
        **On this page**

        - [Section with a link](#section-with-a-link)
          - [Sub `code`](#sub-code)
        - [Next](#next)
        <!-- tocstop -->

        ## Section [with a link](https://example.com)
        ### Sub `code`
        #### Too deep to list
        ## Next
        """)


def test_sections_starting_at_level_three_are_listed_flush_left() -> None:
    markdown = "<!-- toc -->\n<!-- tocstop -->\n\n### One\n### Two\n"
    toc = markdown_toc.with_toc(markdown)
    assert "\n- [One](#one)\n- [Two](#two)\n" in toc


def test_regenerating_an_up_to_date_toc_changes_nothing() -> None:
    once = markdown_toc.with_toc("<!-- toc -->\n<!-- tocstop -->\n\n## A\n## B\n")
    assert markdown_toc.with_toc(once) == once


def test_add_puts_the_block_before_the_first_listed_heading() -> None:
    markdown = "# Title\n\nIntro.\n\n## First\n"
    assert markdown_toc.with_empty_block(markdown) == (
        "# Title\n\nIntro.\n\n<!-- toc -->\n<!-- tocstop -->\n\n## First\n"
    )


def test_add_puts_the_block_above_a_generated_sections_marker() -> None:
    markdown = (
        "# Architecture\n\nIntro.\n\n"
        "<!-- BEGIN MODULE OVERVIEW (auto-generated) -->\n"
        "## Module Overview\n\ngraph\n<!-- END MODULE OVERVIEW -->\n\n## Layering\n"
    )
    assert markdown_toc.with_empty_block(markdown).startswith(
        "# Architecture\n\nIntro.\n\n<!-- toc -->\n<!-- tocstop -->\n\n"
        "<!-- BEGIN MODULE OVERVIEW (auto-generated) -->\n## Module Overview\n"
    )


def test_add_refuses_a_file_without_sections() -> None:
    with pytest.raises(markdown_toc.TocError) as raised:
        markdown_toc.with_empty_block("# Title only\n\n```\n## In code\n```\n")
    assert raised.value.kind == markdown_toc.TocErrorKind.NO_SECTIONS


def test_stale_reports_only_files_whose_toc_is_out_of_date(tmp_path: Path) -> None:
    current = tmp_path / "current.md"
    current.write_text(markdown_toc.with_toc("<!-- toc -->\n<!-- tocstop -->\n## A\n"))
    renamed = tmp_path / "renamed.md"
    renamed.write_text(current.read_text().replace("## A", "## B"))
    assert markdown_toc.stale([current, renamed]) == [renamed]

"""Keep the tables of contents in this repository's Markdown files up to date.

A file opts in with a `<!-- toc -->` ... `<!-- tocstop -->` block; everything between
the markers is regenerated from the file's `##` and `###` headings. `--add` puts an
empty block before the first of those headings in a file that has none.

    mise run toc                     # rewrite every block that is out of date
    mise run toc-check               # list stale files and exit 1; changes nothing
    mise exec -- uv run --no-sync python -m iglootools.docs.toc --add <file>...
"""

import argparse
import re
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import accumulate, count, islice
from pathlib import Path

TOC_START = "<!-- toc -->"
TOC_END = "<!-- tocstop -->"
TOC_LEVELS = (2, 3)

HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t#]*$")
FENCE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})")
LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
# An underscore that opens or closes emphasis; inside a word (snake_case) it is text.
EMPHASIS_UNDERSCORE = re.compile(r"(?<!\w)_+|_+(?!\w)")
TOC_BLOCK = re.compile(
    rf"{re.escape(TOC_START)}\n.*?{re.escape(TOC_END)}", flags=re.DOTALL
)


@dataclass(frozen=True)
class Heading:
    level: int
    text: str
    anchor: str


def outside_fences(lines: Sequence[str]) -> list[str]:
    """The lines that are not inside a fenced code block, with fenced ones blanked."""

    def step(fence: str | None, line: str) -> tuple[str | None, str]:
        opening = FENCE.match(line)
        match fence, opening:
            case None, None:
                return None, line
            case None, _:
                return opening.group(1), ""
            case _, _ if opening and opening.group(1).startswith(fence):
                return None, ""
            case _:
                return fence, ""

    states = accumulate(
        lines, lambda state, line: step(state[0], line), initial=(None, "")
    )
    return [visible for _, visible in islice(states, 1, None)]


def plain_text(markdown: str) -> str:
    return LINK.sub(r"\1", markdown)


def slug(text: str) -> str:
    """GitHub's heading anchor: lower case, punctuation dropped, spaces to hyphens."""
    rendered = EMPHASIS_UNDERSCORE.sub("", plain_text(text))
    return re.sub(r"[^\w\- ]", "", rendered.lower()).replace(" ", "-")


def unique_anchors(slugs: Iterable[str]) -> list[str]:
    """Suffix repeats with -1, -2, skipping any suffixed form a heading already took.

    `Repeated`, `Repeated`, `Repeated-1` become `repeated`, `repeated-1` and
    `repeated-1-1`, as github-slugger does.
    """

    def assign(taken: dict[str, int], base: str) -> tuple[dict[str, int], str]:
        if base not in taken:
            return {**taken, base: 0}, base
        else:
            n = next(i for i in count(taken[base] + 1) if f"{base}-{i}" not in taken)
            return {**taken, base: n, f"{base}-{n}": 0}, f"{base}-{n}"

    states = accumulate(
        slugs, lambda state, base: assign(state[0], base), initial=({}, "")
    )
    return [anchor for _, anchor in islice(states, 1, None)]


def headings(markdown: str) -> list[Heading]:
    """Every heading outside code blocks, with GitHub's -1, -2 on repeated anchors."""
    found = [
        (len(m.group(1)), m.group(2))
        for line in outside_fences(markdown.splitlines())
        if (m := HEADING.match(line))
    ]
    anchors = unique_anchors(slug(text) for _, text in found)
    return [
        Heading(level, text, anchor)
        for (level, text), anchor in zip(found, anchors, strict=True)
    ]


def render_toc(entries: Iterable[Heading]) -> str:
    listed = [h for h in entries if h.level in TOC_LEVELS]
    # Sections that start at ### are listed flush left, not as an orphan sublist.
    top = min((h.level for h in listed), default=min(TOC_LEVELS))
    lines = [
        f"{'  ' * (h.level - top)}- [{plain_text(h.text)}](#{h.anchor})" for h in listed
    ]
    return "\n".join([TOC_START, "**On this page**", "", *lines, TOC_END])


def with_toc(markdown: str) -> str:
    return TOC_BLOCK.sub(lambda _: render_toc(headings(markdown)), markdown, count=1)


def with_empty_block(markdown: str) -> str:
    lines = markdown.splitlines(keepends=True)
    visible = outside_fences([line.rstrip("\n") for line in lines])
    first = next(
        (
            i
            for i, line in enumerate(visible)
            if (m := HEADING.match(line)) and len(m.group(1)) in TOC_LEVELS
        ),
        None,
    )
    if first is None:
        raise ValueError("no ## or ### heading to put a table of contents before")
    block = f"{TOC_START}\n{TOC_END}\n\n"
    return "".join([*lines[:first], block, *lines[first:]])


def files_with_toc(root: Path) -> list[Path]:
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.md"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split("\0")
    return [
        root / name
        for name in tracked
        if name and TOC_START in (root / name).read_text()
    ]


def stale(paths: Iterable[Path]) -> list[Path]:
    return [p for p in paths if with_toc(p.read_text()) != p.read_text()]


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check", action="store_true", help="report stale files, change nothing"
    )
    mode.add_argument(
        "--add", nargs="+", type=Path, metavar="FILE", help="add a block to FILE"
    )
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[3]

    for path in args.add or []:
        path.write_text(with_empty_block(path.read_text()))
    out_of_date = stale(files_with_toc(root))

    if args.check:
        for path in out_of_date:
            print(f"stale table of contents: {path.relative_to(root)}")
        if out_of_date:
            print("Run `mise run toc` to regenerate.")
        return 1 if out_of_date else 0
    for path in out_of_date:
        path.write_text(with_toc(path.read_text()))
        print(f"updated {path.relative_to(root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

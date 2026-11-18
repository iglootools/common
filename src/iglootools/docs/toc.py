"""Tables of contents in Markdown files, generated from their headings.

A file opts in with a `<!-- toc -->` ... `<!-- tocstop -->` block; everything between the
markers is regenerated from the file's `##` and `###` headings, with anchors that follow
GitHub's rules.
"""

import re
import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
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


class TocErrorKind(StrEnum):
    NO_SECTIONS = "no-sections"


class TocError(ValueError):
    """A file the table of contents cannot be generated for."""

    def __init__(self, kind: TocErrorKind, path: Path | None = None) -> None:
        super().__init__(f"{kind}: {path}")
        self.kind = kind
        self.path = path


def with_empty_block(markdown: str) -> str:
    """Insert an empty block before the first `##` or `###` heading.

    Raises TocError(NO_SECTIONS) when there is no such heading outside code blocks.
    """
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
        raise TocError(TocErrorKind.NO_SECTIONS)
    block = f"{TOC_START}\n{TOC_END}\n\n"
    return "".join([*lines[:first], block, *lines[first:]])


def add_block(path: Path) -> None:
    """Give *path* an empty block; regenerate() fills it in."""
    try:
        path.write_text(with_empty_block(_read(path)), encoding="utf-8")
    except TocError as error:
        raise TocError(error.kind, path) from None


def files_with_toc(root: Path) -> list[Path]:
    """The Markdown files git tracks under *root* that carry a block."""
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.md"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split("\0")
    return [root / name for name in tracked if name and TOC_START in _read(root / name)]


def stale(paths: Iterable[Path]) -> list[Path]:
    return [p for p in paths if with_toc(_read(p)) != _read(p)]


def regenerate(paths: Iterable[Path]) -> list[Path]:
    """Rewrite the out-of-date blocks among *paths*; returns the files it changed."""
    changed = stale(paths)
    for path in changed:
        path.write_text(with_toc(_read(path)), encoding="utf-8")
    return changed


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")

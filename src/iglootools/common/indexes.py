"""
Every shared guideline is registered in the indexes readers are routed through.

guidelines/documentation/writing-guidelines.md › Register a new or renamed guideline in
its directory's index. The plugin's SessionStart hook puts the indexes, not the
guidelines, in every session, so a guideline missing from them is a file nobody reads.

An index lists a file when it links to it by its path relative to the index, as
`](name)`. Only tracked files count: an editor's scratch file is not a guideline.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

GUIDELINES_DIR = PurePosixPath("guidelines")
INDEX = "README.md"
_HERE = PurePosixPath()


@dataclass(frozen=True)
class Unlisted:
    """A guideline file, or directory index, that *index* does not link to."""

    index: PurePosixPath
    entry: str


def find_unlisted(root: Path) -> list[Unlisted]:
    """
    Find what the indexes under *root*'s guidelines/ do not list.

    Each directory's README.md lists every file under it; guidelines/README.md lists
    every directory's README.md and every top-level guideline. An index that does not
    exist lists nothing. Paths are relative to *root*.
    """
    files = _tracked(root)
    relative = [path.relative_to(GUIDELINES_DIR) for path in files]
    directories = sorted({path.parts[0] for path in relative if path.parent != _HERE})
    top_level = sorted(
        path.name for path in relative if path.parent == _HERE and path.name != INDEX
    )
    return [
        *_missing(
            root,
            GUIDELINES_DIR / INDEX,
            [f"{name}/{INDEX}" for name in directories] + top_level,
        ),
        *(
            unlisted
            for name in directories
            for unlisted in _missing(
                root,
                GUIDELINES_DIR / name / INDEX,
                _entries_under(files, GUIDELINES_DIR / name),
            )
        ),
    ]


def _entries_under(files: list[PurePosixPath], directory: PurePosixPath) -> list[str]:
    return sorted(
        path.relative_to(directory).as_posix()
        for path in files
        if path.is_relative_to(directory) and path != directory / INDEX
    )


def _missing(root: Path, index: PurePosixPath, entries: list[str]) -> list[Unlisted]:
    path = root / index
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    return [Unlisted(index, entry) for entry in entries if f"]({entry})" not in text]


def _tracked(root: Path) -> list[PurePosixPath]:
    names = subprocess.run(
        ["git", "ls-files", "-z", "--", str(GUIDELINES_DIR)],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split("\0")
    return [PurePosixPath(name) for name in names if name]

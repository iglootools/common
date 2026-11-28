"""
The iglootools commands a release renamed, and rewriting their old names in a project.

A project calls iglootools commands by name, in its mise tasks above all, and runs the
release it pins, so once it adopts a release that renamed one, the old name fails its
own checks. Adopting therefore rewrites each old name to the new in the project's
tracked files, in the commit that moves the pins, and the pull request passes and
merges.

A rename stays listed while a project may still pin a release from before it.
"""

import re
from pathlib import Path

from iglootools.common.pins import SKIPPED, Run, capture

# Whole names only: `common adopt` must not match inside `common adopt-all`, nor
# `build` inside `python build`.
RENAMED: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\biglootools common adopt-all(?![\w-])"),
        "iglootools workspace adopt-common",
    ),
    (re.compile(r"\biglootools common adopt(?![\w-])"), "iglootools repo adopt-common"),
    (
        re.compile(r"\biglootools common check-pins(?![\w-])"),
        "iglootools repo lint-common-pins",
    ),
    (re.compile(r"\biglootools build(?![\w-])"), "iglootools repo run"),
)


def rename(text: str) -> tuple[str, int]:
    """Return *text* with every renamed command's old name replaced, and how many."""
    count = 0
    for pattern, new in RENAMED:
        text, found = pattern.subn(new, text)
        count += found
    return text, count


def candidate_files(root: Path, *, run: Run = capture) -> list[Path]:
    """List the tracked files under *root* naming an iglootools command, locks aside."""
    names = run(["git", "ls-files", "-z"], root).stdout.split("\0")
    return [
        root / name
        for name in names
        if name and not name.startswith(SKIPPED) and _names_a_command(root / name)
    ]


def _names_a_command(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError, OSError:
        return False
    return "iglootools " in text

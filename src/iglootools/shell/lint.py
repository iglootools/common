"""Linting the shell scripts git tracks with shellcheck.

A shell script is a .sh or .bash file, or a file whose shebang runs sh or bash, which is
how mise file tasks under mise-tasks/, having no extension, are found. Files marked
linguist-vendored or linguist-generated in .gitattributes are skipped: vendored code is not
the project's to restyle, and generated code is fixed in its generator. GitHub reads the
same attributes to leave such files out of diffs and language statistics.
"""

import re
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

type Run = Callable[[Sequence[str], Path], int]
"""Runs a command in a directory with its output going to the terminal."""

_SHEBANG = re.compile(rb"^#!(/usr/bin/env[ \t]+|/bin/|/usr/bin/)(ba)?sh([ \t]|$)")
_SHELL_SUFFIXES = (".sh", ".bash")


def is_shell_script(path: Path) -> bool:
    if path.suffix in _SHELL_SUFFIXES:
        return True
    if not path.is_file():
        return False
    with path.open("rb") as handle:
        return bool(_SHEBANG.match(handle.readline().rstrip(b"\r\n")))


def shell_scripts(root: Path) -> list[Path]:
    """The tracked shell scripts under *root* that are not vendored or generated, as
    paths relative to it."""
    tracked = _git(root, "ls-files", "-z").split("\0")
    candidates = [
        Path(name) for name in tracked if name and is_shell_script(root / name)
    ]
    excluded = _vendored_or_generated(root, candidates)
    return [path for path in candidates if path not in excluded]


def _vendored_or_generated(root: Path, paths: Sequence[Path]) -> set[Path]:
    """check-attr -z prints path NUL attribute NUL value NUL; an attribute that is on
    reads "set", or "true" when written as linguist-vendored=true."""
    if not paths:
        return set()
    fields = _git(
        root,
        "check-attr",
        "-z",
        "linguist-vendored",
        "linguist-generated",
        "--",
        *map(str, paths),
    ).split("\0")
    return {
        Path(path)
        for path, _, value in zip(
            fields[0::3], fields[1::3], fields[2::3], strict=False
        )
        if value in {"set", "true"}
    }


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout


def shellcheck_command(scripts: Sequence[Path]) -> list[str]:
    """--external-sources follows `source` into the sourced file, so a variable set in a
    script and read in what it sources is not reported as unused. Findings inside the
    sourced file are not reported here: it is linted on its own, or skipped as vendored."""
    return ["shellcheck", "--external-sources", *map(str, scripts)]


def run_in(command: Sequence[str], directory: Path) -> int:
    return subprocess.run(command, cwd=directory, check=False).returncode

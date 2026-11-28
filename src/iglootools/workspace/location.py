"""
Find the iglootools workspace: the directory every project is checked out in.

The IGLOOTOOLS_WORKSPACE environment variable names it, or a .iglootools-workspace
directory marks it, found in the directory a command starts from or any directory above
it. The variable wins, so one shell can point elsewhere without moving the directory.
Nothing is guessed: where the projects live is the developer's choice, stated once.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

ENVIRONMENT_VARIABLE = "IGLOOTOOLS_WORKSPACE"
SENTINEL = ".iglootools-workspace"


class WorkspaceSource(StrEnum):
    """What named the workspace."""

    ENVIRONMENT = "environment"
    SENTINEL = "sentinel"


@dataclass(frozen=True)
class Workspace:
    """The workspace directory, and what named it."""

    path: Path
    source: WorkspaceSource


class WorkspaceErrorKind(StrEnum):
    """Why no workspace could be found."""

    NOT_FOUND = "not-found"
    RELATIVE = "relative"
    NOT_A_DIRECTORY = "not-a-directory"


class WorkspaceError(Exception):
    """
    No workspace: none is configured, or IGLOOTOOLS_WORKSPACE names no directory.

    *start* is where the search for the sentinel began, *configured* the variable's
    value, empty when it is not set.
    """

    def __init__(self, kind: WorkspaceErrorKind, start: Path, configured: str) -> None:
        """Build the error from its kind, where the search began and the variable."""
        super().__init__(f"{kind}: {configured or start}")
        self.kind = kind
        self.start = start
        self.configured = configured


def resolve_workspace(start: Path, *, environ: Mapping[str, str]) -> Workspace:
    """
    Return the workspace IGLOOTOOLS_WORKSPACE names, or the nearest sentinel marks.

    The variable, once `~` is expanded, must be an absolute path to a directory: a set
    variable that is unusable raises rather than falling back to the sentinel, which
    would hide the mistake. Otherwise *start* and each directory above it are searched
    for a .iglootools-workspace directory. Raises WorkspaceError when neither gives one.
    """
    configured = environ.get(ENVIRONMENT_VARIABLE, "").strip()
    if configured:
        path = _expand_home(configured, environ)
        if not path.is_absolute():
            raise WorkspaceError(WorkspaceErrorKind.RELATIVE, start, configured)
        if not path.is_dir():
            raise WorkspaceError(WorkspaceErrorKind.NOT_A_DIRECTORY, start, configured)
        return Workspace(path, WorkspaceSource.ENVIRONMENT)
    marked = next(
        (directory for directory in [start, *start.parents] if _is_marked(directory)),
        None,
    )
    if marked is None:
        raise WorkspaceError(WorkspaceErrorKind.NOT_FOUND, start, configured)
    return Workspace(marked, WorkspaceSource.SENTINEL)


def _is_marked(directory: Path) -> bool:
    return (directory / SENTINEL).is_dir()


def _expand_home(value: str, environ: Mapping[str, str]) -> Path:
    """Expand a leading `~` from *environ*'s HOME, as the shell would."""
    home = environ.get("HOME", "")
    if home and (value == "~" or value.startswith("~/")):
        return Path(home) / value.removeprefix("~").removeprefix("/")
    return Path(value)

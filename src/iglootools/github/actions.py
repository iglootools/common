"""
Hand values to the next steps of a GitHub Actions job, through its output file.

A step's outputs are `name=value` lines appended to the file $GITHUB_OUTPUT names; later
steps read them as `steps.<id>.outputs.<name>`.
"""

from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path


class MultilineOutputError(ValueError):
    """An output value spans lines, which the `name=value` form cannot carry."""

    def __init__(self, name: str) -> None:
        """Build the error for the output called *name*."""
        super().__init__(f"output {name} spans several lines")
        self.name = name


def format_outputs(values: Mapping[str, str]) -> str:
    """
    Return *values* as `name=value` lines, in the order given.

    Raises MultilineOutputError for a value with a newline, which would end the line
    early and let the rest of the value set an output of its own.
    """
    for name, value in values.items():
        if "\n" in value or "\r" in value:
            raise MultilineOutputError(name)
    return "".join(f"{name}={value}\n" for name, value in values.items())


def append_outputs(path: Path, values: Mapping[str, str]) -> None:
    """Append *values* to the step output file at *path*, one `name=value` per line."""
    with path.open("a", encoding="utf-8") as output:
        output.write(format_outputs(values))


class AnnotationLevel(StrEnum):
    """How prominently the run's page shows an annotation."""

    NOTICE = "notice"
    ERROR = "error"


def format_annotation(level: AnnotationLevel, message: str) -> str:
    """
    Return a workflow command that shows *message* as a *level* annotation on the run.

    The message is escaped as the runner expects, so a value interpolated into it, such
    as a tag from a dispatch input, cannot end the command and start another.
    """
    escaped = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    return f"::{level}::{escaped}"

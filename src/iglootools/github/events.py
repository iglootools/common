"""What a long-running command is doing, reported as it happens.

Commands report events rather than lines of text, so the same progress can be printed as
lines by a single command and drawn as a live table when several run in parallel.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum


class Stage(StrEnum):
    BRANCHED = "branched"
    MOVING = "moving"
    LOCKING = "locking"
    PUSHED = "pushed"
    OPENED = "opened"
    WAITING = "waiting"
    TAGGED = "tagged"


@dataclass(frozen=True)
class Event:
    stage: Stage
    detail: str
    pull: int | None = None


type Report = Callable[[Event], None]
"""Receives each event as it happens."""

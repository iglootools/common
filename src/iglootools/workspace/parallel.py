"""Do the same thing to every repository of the workspace at once."""

import threading
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor


def each[T, R](
    items: Sequence[T],
    work: Callable[[T], R],
    *,
    jobs: int | None = None,
) -> list[R]:
    """
    Return *work* applied to each of *items*, in their order, running *jobs* at once.

    All of them by default: the work is almost all waiting on git, GitHub or a
    subprocess, so threads cost nothing. *work* reports its own failures in what it
    returns; an exception it raises propagates once every item has finished.
    """
    with ThreadPoolExecutor(max_workers=jobs or max(len(items), 1)) as pool:
        return list(pool.map(work, items))


type Sleep = Callable[[float], None]
"""Waits the given seconds, unless the run is interrupted first."""


class CancelledError(Exception):
    """The run was interrupted; raised from a sleep, so the item stops there."""


def each_interruptible[T, R](
    items: Sequence[T],
    work: Callable[[T, Sleep], R],
    *,
    stop: threading.Event,
) -> list[R]:
    """
    Return *work* applied to each of *items* at once, in their order, until stopped.

    *work* waits only through the sleep it is given. Setting *stop*, which Ctrl-C does,
    makes each item's next sleep raise CancelledError, which *work* turns into its
    result; the call returns once every item has.
    """

    def sleep(seconds: float) -> None:
        if stop.wait(seconds):
            raise CancelledError

    with ThreadPoolExecutor(max_workers=max(len(items), 1)) as pool:
        futures = [pool.submit(work, item, sleep) for item in items]
        try:
            return [future.result() for future in futures]
        except KeyboardInterrupt:
            stop.set()
            return [future.result() for future in futures]

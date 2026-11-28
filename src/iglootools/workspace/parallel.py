"""Do the same thing to every repository of the workspace at once."""

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

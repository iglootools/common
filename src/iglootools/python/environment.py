"""Building, cleaning and reinstalling a uv project."""

import shutil
import subprocess
from collections.abc import Callable, Iterator, Sequence
from enum import StrEnum
from pathlib import Path

type Run = Callable[[Sequence[str], Path], int]
"""Runs a command in a directory, output going to the terminal; returns its status."""

# Directories that belong to the environment or to git, never to the build.
_SKIPPED = frozenset({".venv", ".git"})


class EnvironmentErrorKind(StrEnum):
    """How an environment command failed."""

    COMMAND_FAILED = "command-failed"


class EnvironmentCommandError(RuntimeError):
    """A build or environment command exited non-zero: the command and its status."""

    def __init__(self, command: Sequence[str], status: int) -> None:
        """Build the error from the command and its exit status."""
        super().__init__(f"{' '.join(command)} exited with {status}")
        self.kind = EnvironmentErrorKind.COMMAND_FAILED
        self.command = tuple(command)
        self.status = status


def run_in(command: Sequence[str], directory: Path) -> int:
    """Run *command* in *directory*, output to the terminal; return its exit status."""
    return subprocess.run(command, cwd=directory, check=False).returncode


def build(root: Path, run: Run = run_in) -> list[Path]:
    """
    Build the sdist and wheel into an emptied dist/; returns what was built.

    dist/ is emptied first: `uv build` does not clear it, and the PyPI publish action
    uploads everything it finds there, so a leftover artifact would be published with
    the current one. --sdist --wheel builds both from source; plain `uv build` would
    build the wheel from the sdist, which is also correct, since hatchling writes the
    resolved version into the sdist's PKG-INFO, but is one round-trip through generated
    metadata more.
    """
    dist = root / "dist"
    shutil.rmtree(dist, ignore_errors=True)
    _check(["uv", "build", "--sdist", "--wheel"], root, run)
    return sorted(dist.iterdir()) if dist.exists() else []


def build_artifacts(root: Path) -> list[Path]:
    """
    List what `clean` deletes: build/, dist/, *.egg-info, and bytecode outside .venv.

    The bytecode inside .venv belongs to the environment.
    """
    return [
        *(p for p in (root / "build", root / "dist") if p.exists()),
        *sorted(root.glob("*.egg-info")),
        *_bytecode(root),
    ]


def _bytecode(root: Path) -> Iterator[Path]:
    for directory, subdirectories, files in root.walk():
        caches = [d for d in subdirectories if d == "__pycache__"]
        # Pruned in place: Path.walk does not descend into what is removed here.
        subdirectories[:] = [
            d for d in subdirectories if d not in _SKIPPED and d != "__pycache__"
        ]
        yield from (directory / c for c in caches)
        yield from (directory / f for f in files if f.endswith(".pyc"))


def remove(paths: Sequence[Path]) -> None:
    """Delete each of *paths*, a directory with its contents; a missing file is fine."""
    for path in paths:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)


def reinstall(root: Path, run: Run = run_in) -> None:
    """
    Delete .venv and recreate it from the lock.

    `uv sync` is exact and UV_PYTHON pins the interpreter, so a stale environment fixes
    itself. What [deps.uv] cannot see is a dirty one: its freshness check hashes uv.lock
    and pyproject.toml, so a venv someone ran `uv pip install` into still reads as
    fresh.
    """
    shutil.rmtree(root / ".venv", ignore_errors=True)
    _check(["mise", "deps", "install", "uv", "--force"], root, run)


def _check(command: Sequence[str], root: Path, run: Run) -> None:
    status = run(command, root)
    if status != 0:
        raise EnvironmentCommandError(command, status)

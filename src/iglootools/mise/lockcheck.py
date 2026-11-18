"""Whether the staged mise.lock is what `mise lock` produces from the staged mise.toml.

mise has no read-only freshness check, unlike `uv lock --check`, so this regenerates the
lockfile and compares. Each guard below was earned by hitting the failure it prevents:

- It regenerates in a scratch directory, never in place. `mise lock` always writes, and
  undoing that with `git checkout mise.lock` would discard the regenerated lockfile the
  error message asks you to commit.
- It reads both files from the git index, not the working tree. With [settings]
  lockfile = true, any tool-resolving mise command rewrites mise.lock on its own, updating
  the version stanza and dropping the per-platform checksums it can no longer vouch for,
  which is exactly what makes `mise install --locked` fail on a fresh runner. So "up to date"
  can only mean "matches what is staged". The index also ignores a `mise use` in CI or a
  local experiment in the working copy of mise.toml.
- It removes MISE_PYTHON_VERSION, which `mise lock` honours, so an interpreter chosen
  through the environment is not locked in place of the committed pin.
- A failing `mise lock` is an error. Treating its exit status as "no difference" would let
  the check pass in the very situation it exists to catch.
"""

import difflib
import os
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

type Run = Callable[
    [Sequence[str], Path, Mapping[str, str]], subprocess.CompletedProcess[str]
]
"""Runs a command in a directory with an environment, capturing its output."""


class LockCheckErrorKind(StrEnum):
    NOT_STAGED = "not-staged"
    MISE_LOCK_FAILED = "mise-lock-failed"


class LockCheckError(RuntimeError):
    def __init__(self, kind: LockCheckErrorKind, detail: str) -> None:
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail


@dataclass(frozen=True)
class LockComparison:
    staged: str
    regenerated: str

    @property
    def up_to_date(self) -> bool:
        return self.staged == self.regenerated

    def diff(self) -> list[str]:
        return list(
            difflib.unified_diff(
                self.staged.splitlines(keepends=True),
                self.regenerated.splitlines(keepends=True),
                "mise.lock (staged)",
                "mise.lock (regenerated)",
            )
        )


def capture(
    command: Sequence[str], directory: Path, env: Mapping[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, cwd=directory, env=env, capture_output=True, text=True, check=False
    )


def compare(
    root: Path,
    run: Run = capture,
    environ: Mapping[str, str] = os.environ,
) -> LockComparison:
    config = _staged(root, "mise.toml", run, environ)
    staged = _staged(root, "mise.lock", run, environ)
    with tempfile.TemporaryDirectory() as scratch:
        directory = Path(scratch)
        (directory / "mise.toml").write_text(config, encoding="utf-8")
        (directory / "mise.lock").write_text(staged, encoding="utf-8")
        result = run(["mise", "lock"], directory, _lock_environment(environ, directory))
        if result.returncode != 0:
            raise LockCheckError(LockCheckErrorKind.MISE_LOCK_FAILED, result.stderr)
        regenerated = (directory / "mise.lock").read_text(encoding="utf-8")
    return LockComparison(staged=staged, regenerated=regenerated)


def _lock_environment(environ: Mapping[str, str], scratch: Path) -> dict[str, str]:
    """Trusted through MISE_TRUSTED_CONFIG_PATHS rather than `mise trust`, so the scratch
    config is not added to the user's persistent trust store on every run."""
    return {
        **{k: v for k, v in environ.items() if k != "MISE_PYTHON_VERSION"},
        "MISE_TRUSTED_CONFIG_PATHS": str(scratch),
    }


def _staged(root: Path, name: str, run: Run, environ: Mapping[str, str]) -> str:
    result = run(["git", "show", f":{name}"], root, environ)
    if result.returncode != 0:
        raise LockCheckError(LockCheckErrorKind.NOT_STAGED, name)
    return result.stdout

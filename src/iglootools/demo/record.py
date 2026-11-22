"""Recording the project's scripted demo as an asciinema cast."""

import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from iglootools.project import DemoSettings


def title(name: str, installed_version: str | None) -> str:
    """Return the cast's title: the project's name, with its version when known."""
    return f"{name} v{installed_version} demo" if installed_version else f"{name} demo"


def installed_version(distribution: str) -> str | None:
    """Return the version in the environment's .dist-info, or None if not installed."""
    # A VCS-derived version is only in the installed metadata, not in the source tree.
    try:
        return version(distribution)
    except PackageNotFoundError:
        return None


def recording_command(settings: DemoSettings, cast_title: str) -> list[str]:
    """Return the asciinema command that records the demo script under *cast_title*."""
    # --return because asciinema exits 0 by default whatever the recorded command does,
    # which let a demo that died on its first command record and "succeed" on CI.
    return [
        "asciinema", "rec", "--return", "--overwrite",
        "--title", cast_title,
        "--window-size", settings.window_size,
        "--command", str(settings.script),
        str(settings.recording),
    ]  # fmt: skip


def recording_environment(
    environ: Mapping[str, str],
    python: str = sys.executable,
) -> dict[str, str]:
    """Return *environ* with *python*'s bin/ first on PATH, so the demo runs ours."""
    # mise adds .venv/bin when it resolves the environment, which on a fresh clone (CI)
    # happens before [deps.uv] has created .venv.
    path = environ.get("PATH", "")
    return {**environ, "PATH": os.pathsep.join([str(Path(python).parent), path])}


def record(command: Sequence[str], env: Mapping[str, str], root: Path) -> int:
    """Run the recording *command* in *root* with *env*, and return its exit status."""
    return subprocess.run(command, cwd=root, env=env, check=False).returncode

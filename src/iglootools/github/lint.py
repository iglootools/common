"""
Linting the GitHub Actions workflows git tracks with actionlint.

actionlint checks a workflow's syntax, expressions, action inputs and job graph, and
runs shellcheck on each `run:` script. It skips shellcheck silently, exiting 0, when it
cannot find it, so the caller resolves shellcheck first and passes its path, failing
when it is missing rather than linting half of each workflow.
"""

import subprocess
from collections.abc import Sequence
from pathlib import Path

WORKFLOWS_DIR = Path(".github/workflows")
_WORKFLOW_SUFFIXES = (".yml", ".yaml")


def workflow_files(root: Path) -> list[Path]:
    """
    Find the tracked workflow files under *root*'s .github/workflows/.

    Only the directory's own files: GitHub runs no workflow from a subdirectory. The
    paths are relative to *root*.
    """
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--", str(WORKFLOWS_DIR)],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split("\0")
    return [
        path
        for path in map(Path, filter(None, tracked))
        if path.parent == WORKFLOWS_DIR and path.suffix in _WORKFLOW_SUFFIXES
    ]


def actionlint_command(workflows: Sequence[Path], shellcheck: str) -> list[str]:
    """Return the actionlint command that lints *workflows*, `run:` scripts included."""
    # -pyflakes= turns the Python check off rather than leaving it to whether pyflakes
    # happens to be on PATH, so a workflow passes or fails the same on every machine.
    # Workflows run tasks, not inline Python (workflows.md › Keep workflows thin).
    return [
        "actionlint",
        f"-shellcheck={shellcheck}",
        "-pyflakes=",
        *map(str, workflows),
    ]


def run_in(command: Sequence[str], directory: Path) -> int:
    """Run *command* in *directory*, output to the terminal; return its exit status."""
    return subprocess.run(command, cwd=directory, check=False).returncode

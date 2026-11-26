"""
Every guideline is registered in the indexes agents are routed through.

guidelines/documentation/writing-guidelines.md › Register a new or renamed guideline
in its directory's index. The plugin's SessionStart hook puts the indexes, not the
guidelines, in every session, so a guideline missing from them is a file nobody reads.
"""

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUIDELINES = ROOT / "guidelines"
HOOK = ROOT / "hooks" / "load-guideline-indexes.sh"
DIRECTORIES = sorted(path.name for path in GUIDELINES.iterdir() if path.is_dir())


def _files(directory: str) -> list[str]:
    """Every file under the directory, as a path relative to it, except its index."""
    base = GUIDELINES / directory
    return sorted(
        path.relative_to(base).as_posix()
        for path in base.rglob("*")
        if path.is_file() and path.relative_to(base).as_posix() != "README.md"
    )


@pytest.mark.parametrize("directory", DIRECTORIES)
def test_every_file_is_listed_in_its_directory_index(directory: str) -> None:
    index = (GUIDELINES / directory / "README.md").read_text(encoding="utf-8")
    missing = [name for name in _files(directory) if f"]({name})" not in index]
    assert not missing, f"guidelines/{directory}/README.md does not list {missing}"


def test_every_directory_and_top_level_guideline_is_in_the_map() -> None:
    index = (GUIDELINES / "README.md").read_text(encoding="utf-8")
    entries = [f"{name}/README.md" for name in DIRECTORIES] + sorted(
        path.name for path in GUIDELINES.glob("*.md") if path.name != "README.md"
    )
    missing = [entry for entry in entries if f"]({entry})" not in index]
    assert not missing, f"guidelines/README.md does not list {missing}"


def test_the_hook_emits_every_index(tmp_path: Path) -> None:
    result = subprocess.run(
        ["bash", str(HOOK)],
        env={
            **os.environ,
            "CLAUDE_PLUGIN_ROOT": str(ROOT),
            "CLAUDE_PROJECT_DIR": str(tmp_path),
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    indexes = [GUIDELINES / "README.md"] + [
        GUIDELINES / name / "README.md" for name in DIRECTORIES
    ]
    missing = [
        index.relative_to(ROOT).as_posix()
        for index in indexes
        if index.read_text(encoding="utf-8") not in result.stdout
    ]
    assert not missing, f"the hook does not emit {missing}"
    assert "ERROR:" not in result.stdout

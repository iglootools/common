"""
Every guideline is registered where readers and agents are routed to it.

guidelines/documentation/writing-guidelines.md › Register a new or renamed guideline in
every index that routes to it. A guideline missing from these is a file nobody reads.
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUIDELINES = ROOT / "guidelines"
SKILL = ROOT / "skills" / "guidelines" / "SKILL.md"
HOOK = ROOT / "hooks" / "load-guideline-indexes.sh"
AUDITOR = ROOT / "agents" / "auditor.md"

ROUTED_BY = {
    "project-setup": SKILL,
    "documentation": SKILL,
    "coding": HOOK,
    "review": AUDITOR,
}
"""Which file routes agents to the guidelines of each directory."""


def _guidelines(directory: str) -> list[str]:
    return sorted(
        path.name
        for path in (GUIDELINES / directory).glob("*.md")
        if path.name != "README.md"
    )


def test_every_guideline_directory_is_known() -> None:
    directories = sorted(path.name for path in GUIDELINES.iterdir() if path.is_dir())
    assert directories == sorted(ROUTED_BY), (
        "a new directory under guidelines/: say which file routes agents to it in "
        "ROUTED_BY, and give it a line in guidelines/README.md"
    )


@pytest.mark.parametrize("directory", sorted(ROUTED_BY))
def test_every_guideline_is_listed_in_its_directory_index(directory: str) -> None:
    index = (GUIDELINES / directory / "README.md").read_text(encoding="utf-8")
    missing = [name for name in _guidelines(directory) if f"]({name})" not in index]
    assert not missing, f"guidelines/{directory}/README.md does not list {missing}"


@pytest.mark.parametrize("directory", sorted(ROUTED_BY))
def test_every_guideline_is_routed_to_agents(directory: str) -> None:
    router = ROUTED_BY[directory]
    text = router.read_text(encoding="utf-8")
    missing = [
        name
        for name in _guidelines(directory)
        if f"guidelines/{directory}/{name}" not in text
    ]
    assert not missing, f"{router.relative_to(ROOT)} does not route to {missing}"


def test_every_directory_and_top_level_guideline_is_in_the_map() -> None:
    index = (GUIDELINES / "README.md").read_text(encoding="utf-8")
    entries = [f"{name}/" for name in sorted(ROUTED_BY)] + sorted(
        path.name for path in GUIDELINES.glob("*.md") if path.name != "README.md"
    )
    missing = [entry for entry in entries if f"]({entry})" not in index]
    assert not missing, f"guidelines/README.md does not list {missing}"

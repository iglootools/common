"""
The plugin's SessionStart hook puts every guideline index in the session.

That every guideline is listed in an index is checked by the lint-guideline-indexes
task, `iglootools common check-indexes`.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUIDELINES = ROOT / "guidelines"
HOOK = ROOT / "hooks" / "load-guideline-indexes.sh"
DIRECTORIES = sorted(path.name for path in GUIDELINES.iterdir() if path.is_dir())


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


CLEAN_BRANCH = ROOT / "hooks" / "remind-clean-branch.sh"


def _reminder(repo: Path, command: str) -> str:
    event = json.dumps({"tool_input": {"command": command}})
    return subprocess.run(
        ["bash", str(CLEAN_BRANCH)],
        input=event,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(repo), "CLAUDE_PLUGIN_ROOT": "/p"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout


@pytest.mark.parametrize(
    "command",
    ["git push", "git push -u origin feat/x", "cd x && git push --force-with-lease"],
)
def test_pushing_a_branch_asks_for_the_reviewer_s_read_first(
    git_repo: Path,
    command: str,
) -> None:
    subprocess.run(
        ["git", "-C", str(git_repo), "switch", "-q", "-c", "feat/x"],
        check=True,
    )
    context = json.loads(_reminder(git_repo, command))["hookSpecificOutput"]
    assert context["hookEventName"] == "PreToolUse"
    assert "Before pushing feat/x" in context["additionalContext"]
    assert "/p/guidelines/coding/git.md" in context["additionalContext"]


@pytest.mark.parametrize("command", ["git status", "git pushd", "gh pr view"])
def test_other_commands_get_no_reminder(git_repo: Path, command: str) -> None:
    subprocess.run(
        ["git", "-C", str(git_repo), "switch", "-q", "-c", "feat/x"],
        check=True,
    )
    assert _reminder(git_repo, command) == ""


def test_pushing_the_default_branch_gets_no_reminder(git_repo: Path) -> None:
    subprocess.run(
        ["git", "-C", str(git_repo), "switch", "-q", "-c", "main"],
        check=True,
    )
    assert _reminder(git_repo, "git push") == ""

"""
The plugin's SessionStart hook puts every guideline index in the session.

That every guideline is listed in an index is checked by the lint-guideline-indexes
task, `iglootools common check-indexes`.
"""

import os
import subprocess
from pathlib import Path

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

from pathlib import Path

import pytest

from iglootools.shell import lint
from tests.conftest import track


@pytest.mark.parametrize(
    ("name", "first_line", "expected"),
    [
        ("deploy.sh", "", True),
        ("mise-tasks/build", "#!/usr/bin/env bash", True),
        ("mise-tasks/build", "#!/bin/sh", True),
        ("mise-tasks/build", "#!/usr/bin/bash -e", True),
        ("tool", "#!/usr/bin/env python3", False),
        ("tool", "#!/usr/bin/env bashful", False),
        ("README", "", False),
    ],
)
def test_is_shell_script(
    tmp_path: Path,
    name: str,
    first_line: str,
    *,
    expected: bool,
) -> None:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{first_line}\necho hi\n", encoding="utf-8")
    assert lint.is_shell_script(path) is expected


def test_binary_files_are_not_scripts(tmp_path: Path) -> None:
    path = tmp_path / "logo.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe")
    assert lint.is_shell_script(path) is False


def test_shell_scripts_skips_vendored_generated_and_untracked(git_repo: Path) -> None:
    track(git_repo, "mise-tasks/build", "#!/usr/bin/env bash\n")
    track(git_repo, "scripts/setup.sh", "echo\n")
    track(git_repo, "demo/demo-magic.sh", "echo\n")
    track(git_repo, "gen/out.sh", "echo\n")
    track(git_repo, "app.py", "#!/usr/bin/env python3\n")
    track(
        git_repo,
        ".gitattributes",
        "demo/demo-magic.sh linguist-vendored\ngen/out.sh linguist-generated=true\n",
    )
    (git_repo / "untracked.sh").write_text("echo\n", encoding="utf-8")
    assert lint.shell_scripts(git_repo) == [
        Path("mise-tasks/build"),
        Path("scripts/setup.sh"),
    ]


def test_shellcheck_follows_sources() -> None:
    assert lint.shellcheck_command([Path("a.sh")]) == [
        "shellcheck",
        "--external-sources",
        "a.sh",
    ]

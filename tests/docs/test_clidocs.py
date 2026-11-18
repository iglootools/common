import subprocess
from collections.abc import Sequence

import pytest

from iglootools.docs import clidocs


def completed(code: int, stdout: str = "", stderr: str = "") -> clidocs.Run:
    def run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, code, stdout, stderr)

    return run


def test_command_runs_typer_docs_for_the_module() -> None:
    assert clidocs.typer_docs_command("nbkp.cli", "nbkp", python="py") == [
        "py", "-m", "typer", "nbkp.cli", "utils", "docs", "--name", "nbkp",
    ]  # fmt: skip


def test_generate_puts_the_header_first_and_ends_with_one_newline() -> None:
    content = clidocs.generate(["typer"], run=completed(0, "# `nbkp`\n\nUsage.\n\n"))
    assert content == f"{clidocs.HEADER}\n\n# `nbkp`\n\nUsage.\n"


def test_generate_reports_typers_stderr() -> None:
    with pytest.raises(clidocs.ClidocsError) as raised:
        clidocs.generate(["typer"], run=completed(1, stderr="No module named nbkp"))
    assert raised.value.detail == "No module named nbkp"

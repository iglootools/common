from pathlib import Path

from typer.testing import CliRunner

from iglootools.cli import app

runner = CliRunner()


def test_init_refuses_a_git_checkout(git_repo: Path) -> None:
    result = runner.invoke(app, ["--root", str(git_repo), "workspace", "init"])
    assert result.exit_code == 2
    assert "is a git checkout" in result.output
    assert not (git_repo / ".iglootools-workspace").exists()

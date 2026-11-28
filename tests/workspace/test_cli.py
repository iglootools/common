from pathlib import Path

import pytest
from typer.testing import CliRunner

from iglootools.cli import app
from iglootools.workspace import cli as workspace_cli
from iglootools.workspace.clone import CloneAction, CloneResult
from iglootools.workspace.plugins import PluginSync
from iglootools.workspace.status import RepositoryStatus
from iglootools.workspace.sync import SyncResult
from iglootools.workspace.toolchain import SetupResult

runner = CliRunner()


def test_init_refuses_a_git_checkout(git_repo: Path) -> None:
    result = runner.invoke(app, ["--root", str(git_repo), "workspace", "init"])
    assert result.exit_code == 2
    assert "is a git checkout" in result.output
    assert not (git_repo / ".iglootools-workspace").exists()


class TestPrintStatus:
    def test_each_row_is_marked_by_how_its_repository_stands(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        table = tmp_path / "status.txt"
        rows = [
            RepositoryStatus("clean", cloned=True, branch="main"),
            RepositoryStatus("dirty", cloned=True, branch="main", changes=2),
            RepositoryStatus("detached", cloned=True),
            RepositoryStatus("absent", cloned=False),
            RepositoryStatus("broken", cloned=True, problem="GitHub said no"),
        ]

        workspace_cli.print_status(rows, table)

        text = table.read_text(encoding="utf-8")
        for line in ("✓ clean", "⚠ dirty", "⚠ detached", "\N{EN DASH} absent"):
            assert line in text
        assert "✗ broken" in text
        assert capsys.readouterr().err == "✗ broken: GitHub said no\n"


class TestPrintSync:
    def test_a_block_is_marked_by_the_worst_its_repository_had(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        synced = [
            SyncResult("quiet"),
            SyncResult("warned", warnings=["left on feat/x"]),
            SyncResult("broken", problems=["cannot fast-forward"]),
        ]

        ok = workspace_cli.print_sync(
            SetupResult(),
            [],
            synced,
            PluginSync([], []),
            dry_run=False,
        )

        out, err = capsys.readouterr()
        assert not ok
        assert out.splitlines() == [
            "✓ quiet: up to date",
            "⚠ warned:",
            "✗ broken:",
            "3 synced, 0 with branches kept, 1 warning(s), 1 problem(s).",
        ]
        assert err.splitlines() == ["  ⚠ left on feat/x", "  ✗ cannot fast-forward"]

    def test_a_dry_run_labels_each_line_before_its_mark(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        workspace_cli.print_sync(
            SetupResult(),
            [CloneResult("new", CloneAction.CLONED)],
            [],
            PluginSync([], []),
            dry_run=True,
        )

        assert capsys.readouterr().out.splitlines() == [
            "[dry-run] ✓ Would clone new",
            "[dry-run] 0 synced, 0 with branches kept, 0 warning(s), 0 problem(s).",
        ]

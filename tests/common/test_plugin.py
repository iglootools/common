import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from iglootools.common import plugin
from iglootools.common.adopt import Outcome, Result
from iglootools.common.plugin import PluginError, PluginFailureKind, Sync, SyncResult


def _settings(root: Path, settings: object) -> Path:
    (root / ".claude").mkdir()
    (root / ".claude" / "settings.json").write_text(
        json.dumps(settings),
        encoding="utf-8",
    )
    return root


class TestIsEnabled:
    def test_a_project_without_settings_does_not_enable_it(
        self,
        tmp_path: Path,
    ) -> None:
        assert not plugin.is_enabled(tmp_path)

    def test_a_project_enabling_it_in_its_settings_does(self, tmp_path: Path) -> None:
        root = _settings(tmp_path, {"enabledPlugins": {plugin.PLUGIN: True}})
        assert plugin.is_enabled(root)

    def test_a_project_enabling_only_other_plugins_does_not(
        self,
        tmp_path: Path,
    ) -> None:
        root = _settings(tmp_path, {"enabledPlugins": {"other@market": True}})
        assert not plugin.is_enabled(root)

    def test_settings_that_are_not_json_are_an_error(self, tmp_path: Path) -> None:
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / "settings.json").write_text("{", encoding="utf-8")
        with pytest.raises(PluginError) as raised:
            plugin.is_enabled(tmp_path)
        assert raised.value.kind == PluginFailureKind.UNREADABLE_SETTINGS


class FakeClaude:
    """Fake `claude plugin`: list the given installs; record each command."""

    def __init__(
        self,
        installs: list[dict[str, str]],
        *,
        failing: str | None = None,
    ) -> None:
        self.installs = installs
        self.failing = failing
        self.commands: list[list[str]] = []

    def __call__(
        self,
        command: Sequence[str],
        _directory: Path,
    ) -> subprocess.CompletedProcess[str]:
        self.commands.append(list(command))
        if self.failing in command:
            return subprocess.CompletedProcess(command, 1, "", "network is down")
        match list(command):
            case ["claude", "plugin", "list", "--json"]:
                listed = json.dumps(self.installs)
                return subprocess.CompletedProcess(command, 0, listed, "")
            case _:
                return subprocess.CompletedProcess(command, 0, "", "")


def _install(root: Path, version: str) -> dict[str, str]:
    return {
        "id": plugin.PLUGIN,
        "scope": "project",
        "projectPath": str(root),
        "version": version,
    }


class TestUpdate:
    def test_it_updates_at_project_scope_and_reads_the_version_back(
        self,
        tmp_path: Path,
    ) -> None:
        claude = FakeClaude([_install(tmp_path, "2.0.0")])
        result = plugin.update(tmp_path, "2.0.0", run=claude)
        assert result == SyncResult(Sync.CURRENT, "2.0.0")
        assert claude.commands == [
            ["claude", "plugin", "update", plugin.PLUGIN, "--scope", "project"],
            ["claude", "plugin", "list", "--json"],
        ]

    def test_a_project_with_no_install_of_its_own_is_not_installed(
        self,
        tmp_path: Path,
    ) -> None:
        # `claude plugin update` succeeds there, reporting the version other
        # projects have, so only the list tells.
        other = tmp_path / "other"
        claude = FakeClaude([_install(other, "2.0.0")])
        result = plugin.update(tmp_path, "2.0.0", run=claude)
        assert result == SyncResult(Sync.NOT_INSTALLED, None)

    def test_a_failed_update_is_an_error_carrying_its_reason(
        self,
        tmp_path: Path,
    ) -> None:
        claude = FakeClaude([], failing="update")
        with pytest.raises(PluginError) as raised:
            plugin.update(tmp_path, "2.0.0", run=claude)
        assert raised.value.kind == PluginFailureKind.COMMAND_FAILED
        assert "network is down" in raised.value.detail


def test_refreshing_the_marketplace_names_it(tmp_path: Path) -> None:
    claude = FakeClaude([])
    plugin.refresh_marketplace(tmp_path, run=claude)
    assert claude.commands == [
        ["claude", "plugin", "marketplace", "update", plugin.MARKETPLACE],
    ]


@pytest.mark.parametrize(
    ("installed", "sync"),
    [
        ("2.0.0", Sync.CURRENT),
        ("2.1.0", Sync.OTHER_VERSION),
        (None, Sync.NOT_INSTALLED),
    ],
)
def test_the_install_is_classified_against_the_adopted_release(
    installed: str | None,
    sync: Sync,
) -> None:
    assert plugin.classify_sync(installed, "2.0.0").sync == sync


@pytest.mark.parametrize(
    ("result", "on_release"),
    [
        (Result.MERGED, True),
        (Result.UP_TO_DATE, True),
        (Result.OPENED, False),
        (Result.REFUSED, False),
    ],
)
def test_only_a_merged_or_up_to_date_project_is_on_the_release(
    result: Result,
    *,
    on_release: bool,
) -> None:
    assert Outcome(result, "").on_release == on_release

import json
from pathlib import Path

import pytest

from iglootools.common import plugin
from iglootools.common.adopt import Outcome, Result
from iglootools.common.plugin import PluginError, PluginFailureKind, Sync


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

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

from iglootools.workspace import plugins
from iglootools.workspace.plugins import PluginAction, PluginStep

IGLOOTOOLS = "iglootools@iglootools-plugins"
PYRIGHT = "pyright-lsp@claude-plugins-official"


class FakeClaude:
    """Plays `claude plugin`: keeps a list of installs, and records each command."""

    def __init__(
        self,
        installs: dict[tuple[str, Path], str],
        *,
        fail: str = "",
        known: tuple[str, ...] = ("claude-plugins-official", "iglootools-plugins"),
        disabled: frozenset[str] = frozenset(),
    ) -> None:
        self.installs = installs
        self.disabled = disabled
        self.fail = fail
        self.known = list(known)
        self.commands: list[tuple[list[str], Path]] = []

    def __call__(
        self,
        command: Sequence[str],
        directory: Path,
    ) -> subprocess.CompletedProcess[str]:
        self.commands.append((list(command), directory))
        match list(command):
            case ["claude", "plugin", "list", "--json"]:
                # Claude Code says whether a plugin is on for the directory asked in.
                entries = [
                    {
                        "id": plugin,
                        "version": version,
                        "scope": "project",
                        "projectPath": str(path),
                        "enabled": path == directory.resolve()
                        and plugin not in self.disabled,
                    }
                    for (plugin, path), version in self.installs.items()
                ]
                return subprocess.CompletedProcess(command, 0, json.dumps(entries), "")
            case ["claude", "plugin", "marketplace", "list", "--json"]:
                listed = json.dumps([{"name": name} for name in self.known])
                return subprocess.CompletedProcess(command, 0, listed, "")
            case ["claude", "plugin", "marketplace", "add", "iglootools/common"]:
                self.known.append("iglootools-plugins")
                return subprocess.CompletedProcess(command, 0, "", "")
            case ["claude", "plugin", "install" | "update", plugin, *_]:
                if plugin == self.fail:
                    return subprocess.CompletedProcess(command, 1, "", "network down")
                self.installs[(plugin, directory.resolve())] = "2.6.0"
                return subprocess.CompletedProcess(command, 0, "", "")
            case _:
                return subprocess.CompletedProcess(command, 0, "", "")


def _project(
    workspace: Path,
    name: str,
    enabled: list[str],
    *,
    declares: bool = True,
) -> tuple[str, Path]:
    path = workspace / name
    (path / ".claude").mkdir(parents=True)
    marketplaces = {
        "iglootools-plugins": {
            "source": {"source": "github", "repo": "iglootools/common"},
        },
    }
    settings = {
        "enabledPlugins": dict.fromkeys(enabled, True),
        **({"extraKnownMarketplaces": marketplaces} if declares else {}),
    }
    (path / ".claude/settings.json").write_text(json.dumps(settings), encoding="utf-8")
    return name, path


def test_an_installed_plugin_is_updated_and_a_missing_one_installed(
    tmp_path: Path,
) -> None:
    nbkp = _project(tmp_path, "nbkp", [IGLOOTOOLS, PYRIGHT])
    claude = FakeClaude({(IGLOOTOOLS, nbkp[1].resolve()): "2.5.0"})
    result = plugins.sync_plugins([nbkp], tmp_path, dry_run=False, run=claude)
    assert result.steps == [
        PluginStep("nbkp", IGLOOTOOLS, PluginAction.UPDATE, "2.6.0"),
        PluginStep("nbkp", PYRIGHT, PluginAction.INSTALL, "2.6.0"),
    ]
    assert result.problems == []
    assert (
        ["claude", "plugin", "install", PYRIGHT, "--scope", "project"],
        nbkp[1],
    ) in claude.commands


def test_each_marketplace_is_refreshed_once(tmp_path: Path) -> None:
    projects = [
        _project(tmp_path, "nbkp", [IGLOOTOOLS, PYRIGHT]),
        _project(tmp_path, "photree", [IGLOOTOOLS]),
    ]
    claude = FakeClaude({})
    plugins.sync_plugins(projects, tmp_path, dry_run=False, run=claude)
    refreshed = [c for c, _ in claude.commands if c[2:4] == ["marketplace", "update"]]
    assert refreshed == [
        ["claude", "plugin", "marketplace", "update", "claude-plugins-official"],
        ["claude", "plugin", "marketplace", "update", "iglootools-plugins"],
    ]


def test_a_dry_run_only_reads(tmp_path: Path) -> None:
    nbkp = _project(tmp_path, "nbkp", [IGLOOTOOLS])
    claude = FakeClaude({})
    result = plugins.sync_plugins([nbkp], tmp_path, dry_run=True, run=claude)
    assert result.steps == [PluginStep("nbkp", IGLOOTOOLS, PluginAction.INSTALL)]
    assert [c for c, _ in claude.commands] == [
        ["claude", "plugin", "marketplace", "list", "--json"],
        ["claude", "plugin", "list", "--json"],
    ]


def test_a_failed_install_is_that_plugin_s_problem_alone(tmp_path: Path) -> None:
    nbkp = _project(tmp_path, "nbkp", [IGLOOTOOLS, PYRIGHT])
    claude = FakeClaude({}, fail=PYRIGHT)
    result = plugins.sync_plugins([nbkp], tmp_path, dry_run=False, run=claude)
    assert result.steps == [
        PluginStep("nbkp", IGLOOTOOLS, PluginAction.INSTALL, "2.6.0"),
        PluginStep(
            "nbkp",
            PYRIGHT,
            PluginAction.INSTALL,
            problem="claude plugin install failed: network down",
        ),
    ]


def test_unreadable_settings_are_a_problem_and_the_rest_go_on(tmp_path: Path) -> None:
    nbkp = _project(tmp_path, "nbkp", [IGLOOTOOLS])
    broken = tmp_path / "photree"
    (broken / ".claude").mkdir(parents=True)
    (broken / ".claude/settings.json").write_text("[]", encoding="utf-8")
    result = plugins.sync_plugins(
        [nbkp, ("photree", broken)],
        tmp_path,
        dry_run=False,
        run=FakeClaude({}),
    )
    assert [step.project for step in result.steps] == ["nbkp"]
    assert result.problems == ["photree: .claude/settings.json: not a JSON object"]


def test_a_marketplace_the_machine_lacks_is_added_from_its_declaration(
    tmp_path: Path,
) -> None:
    nbkp = _project(tmp_path, "nbkp", [IGLOOTOOLS])
    claude = FakeClaude({}, known=())
    result = plugins.sync_plugins([nbkp], tmp_path, dry_run=False, run=claude)
    assert result.added == ["iglootools-plugins"]
    assert result.problems == []
    assert result.steps == [
        PluginStep("nbkp", IGLOOTOOLS, PluginAction.INSTALL, "2.6.0"),
    ]
    marketplace = [c for c, _ in claude.commands if c[2] == "marketplace"]
    assert [
        "claude",
        "plugin",
        "marketplace",
        "add",
        "iglootools/common",
    ] in marketplace
    assert not [c for c in marketplace if c[3] == "update"]


def test_an_unknown_undeclared_marketplace_is_a_problem(tmp_path: Path) -> None:
    nbkp = _project(tmp_path, "nbkp", [IGLOOTOOLS], declares=False)
    result = plugins.sync_plugins(
        [nbkp],
        tmp_path,
        dry_run=False,
        run=FakeClaude({}, known=()),
    )
    assert result.added == []
    assert result.problems == [
        (
            "marketplace iglootools-plugins is not known here, and no project "
            "declares where it is"
        ),
    ]


def test_a_plugin_installed_but_turned_off_in_its_project_is_a_problem(
    tmp_path: Path,
) -> None:
    nbkp = _project(tmp_path, "nbkp", [IGLOOTOOLS, PYRIGHT])
    claude = FakeClaude({}, disabled=frozenset({PYRIGHT}))
    result = plugins.sync_plugins([nbkp], tmp_path, dry_run=False, run=claude)
    assert result.steps == [
        PluginStep("nbkp", IGLOOTOOLS, PluginAction.INSTALL, "2.6.0"),
        PluginStep(
            "nbkp",
            PYRIGHT,
            PluginAction.INSTALL,
            "2.6.0",
            problem="installed, but not enabled in the project: a "
            ".claude/settings.local.json may turn it off",
        ),
    ]
    listings = [d for c, d in claude.commands if c[2:4] == ["list", "--json"]]
    assert nbkp[1] in listings

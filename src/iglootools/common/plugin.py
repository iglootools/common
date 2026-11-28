"""
Read the Claude Code plugins a project enables, and judge an install against a release.

A project commits which plugins it enables in `.claude/settings.json`, but which version
it loads is recorded on each machine; iglootools.workspace.plugins installs and updates
them. After an adopt, the iglootools plugin is classified against the adopted release.
"""

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import cast

PLUGIN = "iglootools@iglootools-plugins"
SETTINGS = Path(".claude/settings.json")


class PluginFailureKind(StrEnum):
    """How reading the project's settings or running `claude plugin` went wrong."""

    UNREADABLE_SETTINGS = "unreadable-settings"
    COMMAND_FAILED = "command-failed"


class PluginError(RuntimeError):
    """The project's plugin could not be checked or updated: kind and detail."""

    def __init__(self, kind: PluginFailureKind, detail: str) -> None:
        """Build the error from its kind and what went wrong."""
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail


class Sync(StrEnum):
    """Where an update left the plugin, measured against the adopted release."""

    CURRENT = "current"
    OTHER_VERSION = "other-version"
    NOT_INSTALLED = "not-installed"


@dataclass(frozen=True)
class SyncResult:
    """Where an update left the plugin, and the version installed, if any."""

    sync: Sync
    installed: str | None


def is_enabled(root: Path) -> bool:
    """
    Tell whether the project at *root* enables the plugin in its committed settings.

    Raises PluginError when `.claude/settings.json` exists but is not a JSON object.
    """
    return PLUGIN in enabled_plugins(root)


def enabled_plugins(root: Path) -> list[str]:
    """
    List the plugins the project at *root* enables in its committed settings, by id.

    An id is `<plugin>@<marketplace>`, set to true under `enabledPlugins`; a project
    without `.claude/settings.json` enables none. Raises PluginError when the file
    exists but is not a JSON object.
    """
    enabled = _settings(root).get("enabledPlugins")
    if not isinstance(enabled, dict):
        return []
    return sorted(
        str(name)
        for name, on in cast("dict[str, object]", enabled).items()
        if on is True
    )


def declared_marketplaces(root: Path) -> dict[str, str]:
    """
    Map each marketplace the project at *root* declares to what `marketplace add` takes.

    Read from `extraKnownMarketplaces`: a GitHub source becomes its `owner/repo`, a git
    or URL source its URL, a directory its path; other kinds are left out. Raises
    PluginError when `.claude/settings.json` exists but is not a JSON object.
    """
    declared = _settings(root).get("extraKnownMarketplaces")
    if not isinstance(declared, dict):
        return {}
    sources = {
        str(name): _source_argument(entry)
        for name, entry in cast("dict[str, object]", declared).items()
    }
    return {name: source for name, source in sources.items() if source}


def _source_argument(entry: object) -> str:
    if not isinstance(entry, dict):
        return ""
    source = cast("dict[str, object]", entry).get("source")
    if not isinstance(source, dict):
        return ""
    fields = cast("dict[str, object]", source)
    match fields.get("source"):
        case "github":
            return str(fields.get("repo", ""))
        case "git" | "url":
            return str(fields.get("url", ""))
        case "directory":
            return str(fields.get("path", ""))
        case _:
            return ""


def _settings(root: Path) -> dict[str, object]:
    """Return the project's committed settings, {} without any; raise if invalid."""
    path = root / SETTINGS
    if not path.is_file():
        return {}
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise PluginError(
            PluginFailureKind.UNREADABLE_SETTINGS,
            f"{SETTINGS}: {error}",
        ) from error
    if not isinstance(settings, dict):
        raise PluginError(
            PluginFailureKind.UNREADABLE_SETTINGS,
            f"{SETTINGS}: not a JSON object",
        )
    return cast("dict[str, object]", settings)


def classify_sync(installed: str | None, version: str) -> SyncResult:
    """Decide where the plugin stands, from the installed and the adopted versions."""
    match installed:
        case None:
            return SyncResult(Sync.NOT_INSTALLED, None)
        case _ if installed == version:
            return SyncResult(Sync.CURRENT, installed)
        case _:
            return SyncResult(Sync.OTHER_VERSION, installed)

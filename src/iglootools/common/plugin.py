"""
Bring the Claude Code plugin a project loads up to the release it adopted.

Adopting a release moves the pins a repository commits, but which plugin version a
project loads is recorded on each machine, in Claude Code's own list of installs, and
the marketplace clone behind it is not refreshed on its own: the plugin is pinned to its
version string so a guideline change lands deliberately (docs/installation.md). So after
an adopt, the project would keep loading the old guidelines until someone ran
`claude plugin update` in it. These functions run it.
"""

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import cast

from iglootools.github.client import Run, capture

PLUGIN = "iglootools@iglootools-plugins"
MARKETPLACE = "iglootools-plugins"
SETTINGS = Path(".claude/settings.json")
INSTALL_COMMAND = f"claude plugin install {PLUGIN} --scope project"
"""What installs the plugin for a project that enables it but never installed it."""


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


def refresh_marketplace(root: Path, *, run: Run = capture) -> None:
    """
    Fetch the marketplace again, so an update can see the newest release.

    Run once per machine, not per project: every project reads the same clone. Raises
    PluginError when the command fails.
    """
    _claude(root, ["plugin", "marketplace", "update", MARKETPLACE], run)


def update(root: Path, version: str, *, run: Run = capture) -> SyncResult:
    """
    Update the plugin at project scope in *root*, and say where that left it.

    The marketplace serves common's default branch, not a tag, so the plugin lands on
    the newest release there, which is *version* unless a later one exists. Not
    concurrent-safe: Claude Code rewrites one list of installs for every project.
    Raises PluginError when a command fails.
    """
    _claude(root, ["plugin", "update", PLUGIN, "--scope", "project"], run)
    return classify_sync(read_installed_version(root, run=run), version)


def classify_sync(installed: str | None, version: str) -> SyncResult:
    """Decide where the plugin stands, from the installed and the adopted versions."""
    match installed:
        case None:
            return SyncResult(Sync.NOT_INSTALLED, None)
        case _ if installed == version:
            return SyncResult(Sync.CURRENT, installed)
        case _:
            return SyncResult(Sync.OTHER_VERSION, installed)


def read_installed_version(root: Path, *, run: Run = capture) -> str | None:
    """
    Return the plugin version installed at project scope for *root*, if any.

    Raises PluginError when `claude plugin list` fails or prints something other than
    the JSON list it documents.
    """
    listed = _claude(root, ["plugin", "list", "--json"], run)
    try:
        entries = json.loads(listed)
    except ValueError as error:
        raise PluginError(
            PluginFailureKind.COMMAND_FAILED,
            f"claude plugin list --json printed no JSON: {error}",
        ) from error
    project = root.resolve()
    return next(
        (
            str(entry["version"])
            for entry in entries
            if entry.get("id") == PLUGIN
            and entry.get("scope") == "project"
            and Path(entry.get("projectPath", "")).resolve() == project
        ),
        None,
    )


def _claude(root: Path, arguments: list[str], run: Run) -> str:
    command = ["claude", *arguments]
    result = run(command, root)
    if result.returncode != 0:
        reason = (result.stderr or result.stdout).strip() or "no reason given"
        raise PluginError(
            PluginFailureKind.COMMAND_FAILED,
            f"`{' '.join(command)}` failed: {reason}",
        )
    return result.stdout

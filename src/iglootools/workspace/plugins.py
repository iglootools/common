"""
Bring the Claude Code plugins each project enables up to date, at project scope.

A project commits which plugins it enables, in `.claude/settings.json`, but whether
one is installed, and which version, is recorded only on the machine. Each marketplace
the plugins come from is added where the machine lacks it, from where a project declares
it under `extraKnownMarketplaces`, and refreshed otherwise; then each enabled plugin is
updated where it is installed for the project and installed where it is not. A session
in any project then loads what the project asks for, at the newest version its
marketplace serves, once Claude Code is restarted or its plugins reloaded there.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from iglootools.common.plugin import (
    PluginError,
    PluginFailureKind,
    declared_marketplaces,
    enabled_plugins,
)
from iglootools.github.client import Run, capture


class PluginAction(StrEnum):
    """What a project's plugin needed: an update, or a first install."""

    UPDATE = "update"
    INSTALL = "install"


@dataclass(frozen=True)
class PluginStep:
    """
    One plugin of one project: what it needed, the version it ended on, any failure.

    *version* is None in a dry run, or when it could not be read back.
    """

    project: str
    plugin: str
    action: PluginAction
    version: str | None = None
    problem: str = ""


@dataclass(frozen=True)
class PluginSync:
    """
    What syncing the plugins did, or would do in a dry run.

    Every project's plugin steps, the problems no single plugin has, and the
    marketplaces added.
    """

    steps: list[PluginStep]
    problems: list[str]
    added: list[str] = field(default_factory=list[str])


type Installs = dict[tuple[str, Path], str]
"""The version installed for each (plugin, project directory), at project scope."""


def sync_plugins(
    projects: Sequence[tuple[str, Path]],
    directory: Path,
    *,
    dry_run: bool,
    run: Run = capture,
) -> PluginSync:
    """
    Update or install every plugin each of *projects* enables, one project at a time.

    First adds each marketplace the plugins need that the machine lacks, from where a
    project declares it, and refreshes the others. One project at a time, since Claude
    Code keeps a single list of installs for every project. The commands that concern
    no single project run in *directory*. A dry run reads what is there and says what
    it would do. Raises PluginError when `claude` cannot list what is installed.
    """
    enabled, unreadable = _read_enabled(projects)
    needed = sorted(
        {plugin.split("@", 1)[-1] for ids in enabled.values() for plugin in ids},
    )
    added, marketplace_problems = _prepare_marketplaces(
        needed,
        projects,
        directory,
        dry_run=dry_run,
        run=run,
    )
    installs = installed(directory, run=run)
    steps = [
        _step(name, path, plugin, installs, dry_run=dry_run, run=run)
        for name, path in projects
        for plugin in enabled.get(name, [])
    ]
    return PluginSync(
        steps=steps if dry_run else _confirm(steps, projects, run=run),
        problems=[*unreadable, *marketplace_problems],
        added=added,
    )


def _confirm(
    steps: Sequence[PluginStep],
    projects: Sequence[tuple[str, Path]],
    *,
    run: Run,
) -> list[PluginStep]:
    """
    Read back, from inside each project, the version of each plugin and that it is on.

    Claude Code says whether a plugin is enabled for the directory it is asked in, so
    each project is asked in its own: a plugin installed but turned off there, as a
    personal `.claude/settings.local.json` can, is a problem of its step.
    """
    names = {step.project for step in steps if not step.problem}
    listed = {
        name: _active_or_problem(path, run=run)
        for name, path in projects
        if name in names
    }
    return [
        step if step.problem else _confirmed(step, listed[step.project])
        for step in steps
    ]


def _active_or_problem(path: Path, *, run: Run) -> dict[str, tuple[str, bool]] | str:
    try:
        return active_in(path, run=run)
    except PluginError as error:
        return error.detail


def _confirmed(
    step: PluginStep,
    listed: dict[str, tuple[str, bool]] | str,
) -> PluginStep:
    if isinstance(listed, str):
        return replace(step, problem=listed)
    match listed.get(step.plugin):
        case None:
            return replace(
                step,
                problem=f"claude plugin {step.action} succeeded, but Claude Code does "
                "not list the plugin for the project",
            )
        case (version, False):
            return replace(
                step,
                version=version,
                problem="installed, but not enabled in the project: a "
                ".claude/settings.local.json may turn it off",
            )
        case (version, True):
            return replace(step, version=version)


def _prepare_marketplaces(
    needed: Sequence[str],
    projects: Sequence[tuple[str, Path]],
    directory: Path,
    *,
    dry_run: bool,
    run: Run,
) -> tuple[list[str], list[str]]:
    """
    Add the *needed* marketplaces the machine lacks, refresh the others.

    Return the ones added (or to add, in a dry run) and a problem for each that is
    unknown and undeclared, or whose add or refresh failed.
    """
    known = known_marketplaces(directory, run=run)
    declared = _declared(projects)
    missing = [name for name in needed if name not in known]
    to_add = [name for name in missing if name in declared]
    undeclared = [
        f"marketplace {name} is not known here, and no project declares where it is"
        for name in missing
        if name not in declared
    ]
    if dry_run:
        return to_add, undeclared
    return to_add, [
        *undeclared,
        *_marketplace_command(to_add, "add", declared, directory, run=run),
        *_marketplace_command(
            [name for name in needed if name in known],
            "update",
            {},
            directory,
            run=run,
        ),
    ]


def known_marketplaces(directory: Path, *, run: Run = capture) -> set[str]:
    """
    Return the names of the marketplaces this machine knows.

    Raises PluginError when `claude plugin marketplace list --json` fails or prints
    no JSON list.
    """
    result = run(["claude", "plugin", "marketplace", "list", "--json"], directory)
    if result.returncode != 0:
        raise PluginError(
            PluginFailureKind.COMMAND_FAILED,
            "claude plugin marketplace list --json failed: "
            f"{_reason(result.stderr, result.stdout)}",
        )
    try:
        entries = json.loads(result.stdout)
    except ValueError as error:
        raise PluginError(
            PluginFailureKind.COMMAND_FAILED,
            f"claude plugin marketplace list --json printed no JSON: {error}",
        ) from error
    return {str(entry["name"]) for entry in entries}


def _declared(projects: Sequence[tuple[str, Path]]) -> dict[str, str]:
    """Merge the marketplaces every readable project declares, by name."""
    return {
        name: source
        for _, path in projects
        for declared in [_declared_or_none(path)]
        if declared is not None
        for name, source in declared.items()
    }


def _declared_or_none(path: Path) -> dict[str, str] | None:
    try:
        return declared_marketplaces(path)
    except PluginError:
        return None  # _read_enabled reports the unreadable file


def _marketplace_command(
    names: Sequence[str],
    verb: str,
    sources: dict[str, str],
    directory: Path,
    *,
    run: Run,
) -> list[str]:
    """
    Run `claude plugin marketplace <verb>` for each of *names*; a problem per failure.

    *add* takes each one's declared source from *sources*; *update* takes its name.
    """
    results = [
        (
            name,
            run(
                ["claude", "plugin", "marketplace", verb, sources.get(name, name)],
                directory,
            ),
        )
        for name in names
    ]
    past = {"add": "added", "update": "refreshed"}.get(verb, verb)
    return [
        f"marketplace {name} not {past}: {_reason(result.stderr, result.stdout)}"
        for name, result in results
        if result.returncode != 0
    ]


def _read_enabled(
    projects: Sequence[tuple[str, Path]],
) -> tuple[dict[str, list[str]], list[str]]:
    """Return each project's enabled plugins, and a problem for each unreadable file."""
    read = {name: _enabled_or_problem(path) for name, path in projects}
    return (
        {name: found for name, found in read.items() if isinstance(found, list)},
        [f"{name}: {found}" for name, found in read.items() if isinstance(found, str)],
    )


def _enabled_or_problem(path: Path) -> list[str] | str:
    try:
        return enabled_plugins(path)
    except PluginError as error:
        return error.detail


def installed(directory: Path, *, run: Run = capture) -> Installs:
    """
    Return every plugin installed at project scope, by plugin and project directory.

    Raises PluginError when `claude plugin list --json` fails or prints no JSON list.
    """
    return {
        (str(entry["id"]), Path(entry["projectPath"]).resolve()): str(
            entry.get("version"),
        )
        for entry in _list(directory, run=run)
        if entry.get("scope") == "project" and entry.get("projectPath")
    }


def active_in(path: Path, *, run: Run = capture) -> dict[str, tuple[str, bool]]:
    """
    Map each plugin installed for the project at *path* to its version and whether on.

    Asked from inside the project, where Claude Code computes whether each is enabled.
    Raises PluginError as installed() does.
    """
    here = path.resolve()
    return {
        str(entry["id"]): (str(entry.get("version")), entry.get("enabled") is True)
        for entry in _list(path, run=run)
        if entry.get("scope") == "project"
        and entry.get("projectPath")
        and Path(entry["projectPath"]).resolve() == here
    }


def _list(directory: Path, *, run: Run) -> list[dict[str, Any]]:
    """Return what `claude plugin list --json` prints, run in *directory*."""
    result = run(["claude", "plugin", "list", "--json"], directory)
    if result.returncode != 0:
        raise PluginError(
            PluginFailureKind.COMMAND_FAILED,
            "claude plugin list --json failed: "
            f"{_reason(result.stderr, result.stdout)}",
        )
    try:
        entries = json.loads(result.stdout)
    except ValueError as error:
        raise PluginError(
            PluginFailureKind.COMMAND_FAILED,
            f"claude plugin list --json printed no JSON: {error}",
        ) from error
    return list(entries)


def _step(
    name: str,
    path: Path,
    plugin: str,
    installs: Installs,
    *,
    dry_run: bool,
    run: Run,
) -> PluginStep:
    action = (
        PluginAction.UPDATE
        if (plugin, path.resolve()) in installs
        else PluginAction.INSTALL
    )
    if dry_run:
        return PluginStep(name, plugin, action)
    result = run(["claude", "plugin", str(action), plugin, "--scope", "project"], path)
    if result.returncode != 0:
        return PluginStep(
            name,
            plugin,
            action,
            problem=f"claude plugin {action} failed: "
            f"{_reason(result.stderr, result.stdout)}",
        )
    return PluginStep(name, plugin, action)


def _reason(stderr: str, stdout: str) -> str:
    return (stderr or stdout).strip() or "no reason given"

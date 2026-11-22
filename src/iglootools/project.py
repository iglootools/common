"""
The project a command works on, read from its pyproject.toml.

Every setting has a default that fits nbkp and photree, so a project only writes the
`[tool.iglootools]` keys it needs to change:

    [tool.iglootools]
    package = "nbkp"                            # default: [project] name, importable

    [tool.iglootools.docs]
    cli-module = "nbkp.cli"                     # default: <package>.cli
    cli-name = "nbkp"                           # default: [project] name
    cli-reference = "docs/cli-reference.md"
    architecture = "docs/architecture.md"
    depgraph-exclude = ["nbkp.templates"]       # default: none

    [tool.iglootools.demo]
    script = "demo/demo.sh"                     # what `demo record` runs
    recording = "demo/demo.cast"                # where it writes the cast
    window-size = "160x45"
    workflow = "demo.yml"
    artifact = "demo-recording"
    cast = "demo.cast"
    readme = "README.md"
"""

import re
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, TypeIs, cast


class ProjectErrorKind(StrEnum):
    """Why the tools cannot work from a pyproject.toml."""

    NO_PYPROJECT = "no-pyproject"
    NO_PROJECT_NAME = "no-project-name"
    INVALID_SETTING = "invalid-setting"


class ProjectError(ValueError):
    """A pyproject.toml the tools cannot work from."""

    def __init__(
        self,
        kind: ProjectErrorKind,
        path: Path,
        setting: str | None = None,
    ) -> None:
        """Build the error from its kind, the file, and the setting at fault, if any."""
        super().__init__(f"{kind}: {path} {setting or ''}".rstrip())
        self.kind = kind
        self.path = path
        self.setting = setting


@dataclass(frozen=True)
class DocsSettings:
    """`[tool.iglootools.docs]`: what the docs commands generate, and where."""

    cli_module: str
    cli_name: str
    """The program name the CLI reference documents."""
    cli_reference: Path
    architecture: Path
    depgraph_exclude: tuple[str, ...]


@dataclass(frozen=True)
class DemoSettings:
    """`[tool.iglootools.demo]`: how the demo is recorded and published."""

    script: Path
    recording: Path
    window_size: str
    workflow: str
    artifact: str
    cast: str
    readme: Path


@dataclass(frozen=True)
class Project:
    """The project a command works on, with every setting resolved."""

    root: Path
    name: str
    """The [project] name, which is also the distribution name."""
    package: str
    """The import name of the project's top-level package."""
    requirements: tuple[str, ...]
    """[project] dependencies and every optional-dependencies extra, as written."""
    fallback_version: str | None
    """[tool.uv-dynamic-versioning] fallback-version, when the project sets one."""
    docs: DocsSettings
    demo: DemoSettings


def load_project(root: Path) -> Project:
    """Read *root*/pyproject.toml. Paths in the result are absolute, under *root*."""
    path = root / "pyproject.toml"
    try:
        pyproject = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ProjectError(ProjectErrorKind.NO_PYPROJECT, path) from None
    project_table: dict[str, Any] = pyproject.get("project", {})
    tool: dict[str, Any] = pyproject.get("tool", {})
    settings: dict[str, Any] = tool.get("iglootools", {})
    name = _project_name(project_table, path)
    package = (
        _string(settings, "package", path, None) or re.sub(r"[-.]+", "_", name).lower()
    )
    return Project(
        root=root,
        name=name,
        package=package,
        requirements=(
            *project_table.get("dependencies", []),
            *(
                requirement
                for extra in project_table.get("optional-dependencies", {}).values()
                for requirement in extra
            ),
        ),
        fallback_version=tool.get("uv-dynamic-versioning", {}).get("fallback-version"),
        docs=_docs_settings(settings.get("docs", {}), root, package, name, path),
        demo=_demo_settings(settings.get("demo", {}), root, path),
    )


def _project_name(project_table: dict[str, Any], path: Path) -> str:
    match project_table.get("name"):
        case str(name) if name:
            return name
        case _:
            raise ProjectError(ProjectErrorKind.NO_PROJECT_NAME, path)


def _docs_settings(
    table: dict[str, Any],
    root: Path,
    package: str,
    name: str,
    path: Path,
) -> DocsSettings:
    return DocsSettings(
        cli_module=_string(table, "cli-module", path, f"{package}.cli"),
        cli_name=_string(table, "cli-name", path, name),
        cli_reference=root
        / _string(table, "cli-reference", path, "docs/cli-reference.md"),
        architecture=root
        / _string(table, "architecture", path, "docs/architecture.md"),
        depgraph_exclude=_strings(table, "depgraph-exclude", path),
    )


def _demo_settings(table: dict[str, Any], root: Path, path: Path) -> DemoSettings:
    return DemoSettings(
        script=root / _string(table, "script", path, "demo/demo.sh"),
        recording=root / _string(table, "recording", path, "demo/demo.cast"),
        window_size=_string(table, "window-size", path, "160x45"),
        workflow=_string(table, "workflow", path, "demo.yml"),
        artifact=_string(table, "artifact", path, "demo-recording"),
        cast=_string(table, "cast", path, "demo.cast"),
        readme=root / _string(table, "readme", path, "README.md"),
    )


def _string[D: str | None](
    table: dict[str, Any],
    key: str,
    path: Path,
    default: D,
) -> str | D:
    match table.get(key, default):
        case str(value) if value:
            return value
        case None if default is None:
            return default
        case _:
            raise ProjectError(ProjectErrorKind.INVALID_SETTING, path, key)


def _is_strings(value: object) -> TypeIs[list[str]]:
    return isinstance(value, list) and all(
        isinstance(item, str) for item in cast("list[object]", value)
    )


def _strings(table: dict[str, Any], key: str, path: Path) -> tuple[str, ...]:
    match table.get(key, []):
        case values if _is_strings(values):
            return tuple(values)
        case _:
            raise ProjectError(ProjectErrorKind.INVALID_SETTING, path, key)

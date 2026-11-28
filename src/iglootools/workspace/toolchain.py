"""
The workspace's own setup: the iglootools command at common's newest release.

The workspace is set up as a project without Python of its own is
(guidelines/project-setup/iglootools-cli.md): a `pyproject.toml` declaring the command
as a dev dependency pinned to the release, locked in `uv.lock` and installed in `.venv`,
and a `mise.toml` that makes `iglootools` work there bare, as in every project.
Workspace sync writes both files for each new release, which is what keeps them on it.

The `mise.toml` is not a template: it holds the entries of common's own `mise.toml` at
the release that INHERITED names, with their values, so a guideline change reaches the
workspace through common's file, which follows the guidelines. mise applies the
workspace's `mise.toml` in every project below it too, so INHERITED names only what
each project sets the same way: the tools, the uv variables, sourcing the uv
environment and installing it, both of which mise does for the nearest uv project.
"""

import json
import re
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from textwrap import dedent
from typing import cast

from iglootools.common import pins
from iglootools.github import contents
from iglootools.github.client import GitHub, Run

MISE_CONFIG = "mise.toml"
PYPROJECT = "pyproject.toml"
HEADER = (
    "# Written by `iglootools workspace sync` for the newest release of\n"
    "# iglootools/common, and rewritten for the next: edits here are lost.\n"
)

type KeyPath = tuple[str, ...]
"""A key in a TOML document, table by table: ("settings", "python", "uv_venv_auto")."""

INHERITED: tuple[KeyPath, ...] = (
    ("tools", "python"),
    ("tools", "uv"),
    ("env", "UV_PYTHON"),
    ("env", "UV_PYTHON_DOWNLOADS"),
    ("env", "UV_PYTHON_PREFERENCE"),
    ("settings", "experimental"),
    ("settings", "python", "uv_venv_auto"),
    ("deps", "uv", "auto"),
)
"""
The entries the workspace's `mise.toml` takes from common's, at the release.

Only what every project sets the same way: mise applies the workspace's file in each
project below it, where anything else would override the project's own.
"""

PYTHON: KeyPath = ("tools", "python")
_BARE_KEY = re.compile(r"[A-Za-z0-9_-]+")


class ToolchainErrorKind(StrEnum):
    """Why common's newest release gives no toolchain."""

    NO_RELEASE = "no-release"
    NO_FILE = "no-file"
    MISSING_PIN = "missing-pin"


class ToolchainError(ValueError):
    """
    Common's newest release could not be read: there is none, or it lacks a pin.

    *tag* is the release read, *missing* the files or pins it lacks.
    """

    def __init__(
        self,
        kind: ToolchainErrorKind,
        tag: str = "",
        missing: Sequence[str] = (),
    ) -> None:
        """Build the error from its kind, the release and what it lacks."""
        super().__init__(f"{kind}: {tag} {', '.join(missing)}".strip())
        self.kind = kind
        self.tag = tag
        self.missing = tuple(missing)


class UnrenderableValueError(TypeError):
    """A value of common's `mise.toml` the workspace file cannot write as TOML."""

    def __init__(self, value: object) -> None:
        """Build the error from the value."""
        super().__init__(f"no TOML form for {type(value).__name__} {value!r}")
        self.value = value


@dataclass(frozen=True)
class Toolchain:
    """
    Common's newest release, and what the workspace's files take from it.

    The Python range common supports, and each `mise.toml` entry INHERITED names, with
    its value.
    """

    version: str
    requires_python: str
    mise: tuple[tuple[KeyPath, object], ...]

    @property
    def python(self) -> str:
        """Return the Python version common pins."""
        return str(dict(self.mise)[PYTHON])


def recommended(github: GitHub) -> Toolchain:
    """
    Read common's newest release, and the entries the workspace takes from it.

    Raises ToolchainError when there is no release, or it lacks a file or an entry;
    GitHubError when GitHub cannot be asked.
    """
    version = pins.latest_release(github)
    if version is None:
        raise ToolchainError(ToolchainErrorKind.NO_RELEASE)
    return at_release(github, version)


def at_release(github: GitHub, version: str) -> Toolchain:
    """
    Read common's release *version*, and the entries the workspace takes from it.

    Raises ToolchainError when it lacks a file or an entry; GitHubError when GitHub
    cannot be asked, or has no such release.
    """
    tag = f"v{version}"
    mise = _read_toml(github, tag, MISE_CONFIG)
    requires = lookup(
        _read_toml(github, tag, PYPROJECT),
        ("project", "requires-python"),
    )
    entries, missing = select(mise, INHERITED)
    absent = [
        *(f"{MISE_CONFIG} {describe_key(path)}" for path in missing),
        *([] if isinstance(requires, str) else [f"{PYPROJECT} requires-python"]),
    ]
    if absent:
        raise ToolchainError(ToolchainErrorKind.MISSING_PIN, tag, absent)
    return Toolchain(version, str(requires), entries)


def select(
    document: Mapping[str, object],
    paths: Sequence[KeyPath],
) -> tuple[tuple[tuple[KeyPath, object], ...], list[KeyPath]]:
    """Return each of *paths* found in *document* with its value, and those missing."""
    found = [(path, lookup(document, path)) for path in paths]
    return (
        tuple((path, value) for path, value in found if value is not None),
        [path for path, value in found if value is None],
    )


def lookup(document: object, path: KeyPath) -> object | None:
    """Return the value at *path* in *document*; None if a table on the way lacks it."""
    if not path:
        return document
    if not isinstance(document, dict):
        return None
    return lookup(cast("dict[str, object]", document).get(path[0]), path[1:])


def describe_key(path: KeyPath) -> str:
    """Return *path* as written in the file: `[settings] python.uv_venv_auto`."""
    return f"[{path[0]}] {'.'.join(path[1:])}"


def _read_toml(github: GitHub, tag: str, path: str) -> dict[str, object]:
    """Return the TOML file *path* of common at *tag*; raise when there is none."""
    text = contents.read_text(github, pins.COMMON, path, ref=tag)
    if text is None:
        raise ToolchainError(ToolchainErrorKind.NO_FILE, tag, [path])
    return tomllib.loads(text)


def render_mise_config(toolchain: Toolchain) -> str:
    """
    Return the workspace's `mise.toml`: each inherited entry under its table.

    A key below the table is written dotted (`python.uv_venv_auto = "source"`), which
    TOML reads as the nested table common's file declares.
    """
    tables = dict.fromkeys(path[0] for path, _ in toolchain.mise)
    sections = [
        "\n".join(
            [
                f"[{table}]",
                *(
                    f"{'.'.join(map(_key, path[1:]))} = {_value(value)}"
                    for path, value in toolchain.mise
                    if path[0] == table
                ),
            ],
        )
        for table in tables
    ]
    return (
        HEADER
        + "# Taken from common's mise.toml. mise applies this file in every project\n"
        + "# below it as well, so it holds only what each project sets alike.\n\n"
        + "\n\n".join(sections)
        + "\n"
    )


def _key(key: str) -> str:
    return key if _BARE_KEY.fullmatch(key) else json.dumps(key)


def _value(value: object) -> str:
    """Return *value* as TOML: a string, boolean, number, list or inline table."""
    match value:
        case bool():
            return "true" if value else "false"
        case str():
            return json.dumps(value)
        case int() | float():
            return str(value)
        case list():
            return (
                "["
                + ", ".join(_value(item) for item in cast("list[object]", value))
                + "]"
            )
        case dict():
            pairs = cast("dict[str, object]", value).items()
            return "{ " + ", ".join(f"{_key(k)} = {_value(v)}" for k, v in pairs) + " }"
        case _:
            raise UnrenderableValueError(value)


def render_pyproject(toolchain: Toolchain) -> str:
    """Return the workspace's `pyproject.toml` for *toolchain*."""
    return HEADER + dedent(f"""\
        # The iglootools command, for running it in the workspace.

        [project]
        name = "iglootools-workspace"
        version = "0"
        requires-python = "{toolchain.requires_python}"

        [dependency-groups]
        dev = [
          "iglootools @ git+https://github.com/{pins.COMMON.slug}@v{toolchain.version}",
        ]

        [tool.uv]
        package = false
        """)


@dataclass(frozen=True)
class SetupResult:
    """What setting the workspace up did, or would do; and what failed, if anything."""

    done: list[str] = field(default_factory=list[str])
    problems: list[str] = field(default_factory=list[str])


def set_up(
    workspace: Path,
    toolchain: Toolchain,
    *,
    dry_run: bool,
    run: Run,
) -> SetupResult:
    """
    Write the workspace's two files for *toolchain* where they differ, then install.

    Trusts the `mise.toml` it writes, and runs `uv sync` through mise, which locks and
    installs the command, whenever a file changed or nothing is installed yet. A dry
    run writes nothing and says what it would do. *run* is given the environment the
    command should see, not this process's.
    """
    wanted = {
        MISE_CONFIG: render_mise_config(toolchain),
        PYPROJECT: render_pyproject(toolchain),
    }
    stale = [name for name, text in wanted.items() if _read(workspace / name) != text]
    installed = (workspace / "uv.lock").is_file() and (workspace / ".venv").is_dir()
    if not stale and installed:
        return SetupResult()
    written = [f"{'would write' if dry_run else 'wrote'} {name}" for name in stale]
    if dry_run:
        return SetupResult(
            [*written, f"would install iglootools {toolchain.version} with uv"],
        )
    for name in stale:
        (workspace / name).write_text(wanted[name], encoding="utf-8")
    commands = [
        ["mise", "trust", "--quiet", str(workspace / MISE_CONFIG)],
        ["mise", "exec", "--", "uv", "sync", "--python", toolchain.python],
    ]
    for command in commands:
        result = run(command, workspace)
        if result.returncode != 0:
            reason = (result.stderr or result.stdout).strip()
            return SetupResult(written, [f"`{' '.join(command)}` failed: {reason}"])
    return SetupResult(
        [*written, f"installed iglootools {toolchain.version} with uv"],
    )


def _read(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.is_file() else None

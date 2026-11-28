import base64
import json
import subprocess
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from textwrap import dedent

import pytest

from iglootools.github.client import GitHub
from iglootools.workspace import toolchain
from iglootools.workspace.toolchain import (
    SetupResult,
    Toolchain,
    ToolchainError,
    ToolchainErrorKind,
)

ROOT = Path(__file__).resolve().parents[2]
MISE = dedent("""\
    [tools]
    python = "3.15.2"
    uv = "0.13.7"
    shellcheck = "0.11.0"

    [env]
    UV_PYTHON = { value = "{{ tools.python.path }}", tools = true }
    UV_PYTHON_DOWNLOADS = "never"
    UV_PYTHON_PREFERENCE = "only-system"

    [settings]
    lockfile = true
    experimental = true
    python.uv_venv_auto = "source"

    [deps.uv]
    auto = true

    [tasks.lint]
    run = "ruff check ."
    """)
TOOLCHAIN = Toolchain(
    "2.5.0",
    ">=3.14,<3.16",
    toolchain.select(tomllib.loads(MISE), toolchain.INHERITED)[0],
)
PYPROJECT = '[project]\nname = "iglootools"\nrequires-python = ">=3.14,<3.16"\n'


def _github(
    files: Mapping[str, str],
    tags: Sequence[str] = ("v2.4.1", "v2.5.0"),
) -> GitHub:
    def transport(
        _method: str,
        url: str,
        _headers: Mapping[str, str],
        _body: bytes | None,
    ) -> tuple[int, bytes]:
        path = url.removeprefix("https://api.github.com/repos/iglootools/common")
        if path.startswith("/tags?"):
            listed = [{"name": tag} for tag in tags] if path.endswith("page=1") else []
            return 200, json.dumps(listed).encode()
        name, _, ref = path.removeprefix("/contents/").partition("?ref=")
        assert ref == "v2.5.0", "read at the newest release"
        if name not in files:
            return 404, b'{"message": "Not Found"}'
        content = base64.b64encode(files[name].encode()).decode()
        return 200, json.dumps({"content": content}).encode()

    return GitHub("t", transport=transport)


def test_the_recommended_toolchain_is_common_s_newest_release_and_its_pins() -> None:
    github = _github({"mise.toml": MISE, "pyproject.toml": PYPROJECT})
    assert toolchain.recommended(github) == TOOLCHAIN


def test_a_release_without_a_pin_names_what_it_lacks() -> None:
    lacking = MISE.replace('python.uv_venv_auto = "source"\n', "")
    github = _github({"mise.toml": lacking, "pyproject.toml": PYPROJECT})
    with pytest.raises(ToolchainError) as raised:
        toolchain.recommended(github)
    assert (raised.value.kind, raised.value.tag, raised.value.missing) == (
        ToolchainErrorKind.MISSING_PIN,
        "v2.5.0",
        ("mise.toml [settings] python.uv_venv_auto",),
    )


def test_no_release_at_all_is_an_error() -> None:
    with pytest.raises(ToolchainError) as raised:
        toolchain.recommended(_github({}, tags=()))
    assert raised.value.kind == ToolchainErrorKind.NO_RELEASE


def test_the_workspace_mise_config_holds_the_inherited_entries_only() -> None:
    written = tomllib.loads(toolchain.render_mise_config(TOOLCHAIN))
    assert written == {
        "tools": {"python": "3.15.2", "uv": "0.13.7"},
        "env": {
            "UV_PYTHON": {"value": "{{ tools.python.path }}", "tools": True},
            "UV_PYTHON_DOWNLOADS": "never",
            "UV_PYTHON_PREFERENCE": "only-system",
        },
        "settings": {"experimental": True, "python": {"uv_venv_auto": "source"}},
        "deps": {"uv": {"auto": True}},
    }


def test_every_inherited_entry_is_in_common_s_own_mise_config() -> None:
    # Common's mise.toml is the guidelines' working example: an entry renamed or
    # dropped there must be renamed or dropped in INHERITED too, or sync stops
    # setting the workspace up.
    common = tomllib.loads((ROOT / "mise.toml").read_text(encoding="utf-8"))
    entries, missing = toolchain.select(common, toolchain.INHERITED)
    assert [toolchain.describe_key(path) for path in missing] == []
    written = tomllib.loads(
        toolchain.render_mise_config(Toolchain("2.5.0", ">=3.14", entries)),
    )
    assert {
        path: toolchain.lookup(written, path) for path in toolchain.INHERITED
    } == dict(entries)


def test_the_workspace_pyproject_pins_the_release() -> None:
    pyproject = toolchain.render_pyproject(TOOLCHAIN)
    assert (
        '"iglootools @ git+https://github.com/iglootools/common@v2.5.0",' in pyproject
    )
    assert 'requires-python = ">=3.14,<3.16"' in pyproject
    assert "package = false" in pyproject


def test_a_value_toml_cannot_hold_is_refused() -> None:
    odd = Toolchain("2.5.0", ">=3.14", ((("tools", "python"), object()),))
    with pytest.raises(toolchain.UnrenderableValueError):
        toolchain.render_mise_config(odd)


class FakeTools:
    """Play mise and uv: `uv sync` makes the lock and the environment."""

    def __init__(self, *, failing: str = "") -> None:
        self.failing = failing
        self.commands: list[list[str]] = []

    def __call__(
        self,
        command: Sequence[str],
        directory: Path,
    ) -> subprocess.CompletedProcess[str]:
        self.commands.append(list(command))
        if self.failing in command:
            return subprocess.CompletedProcess(command, 1, "", "no network")
        if "sync" in command:
            (directory / "uv.lock").write_text("lock", encoding="utf-8")
            (directory / ".venv").mkdir(exist_ok=True)
        return subprocess.CompletedProcess(command, 0, "", "")


def test_set_up_writes_trusts_and_installs_then_has_nothing_left(
    tmp_path: Path,
) -> None:
    tools = FakeTools()
    first = toolchain.set_up(tmp_path, TOOLCHAIN, dry_run=False, run=tools)
    assert first == SetupResult(
        [
            "wrote mise.toml",
            "wrote pyproject.toml",
            "installed iglootools 2.5.0 with uv",
        ],
    )
    assert tools.commands == [
        ["mise", "trust", "--quiet", str(tmp_path / "mise.toml")],
        ["mise", "exec", "--", "uv", "sync", "--python", "3.15.2"],
    ]
    assert (
        toolchain.set_up(tmp_path, TOOLCHAIN, dry_run=False, run=tools) == SetupResult()
    )


def test_a_new_release_rewrites_only_what_changed(tmp_path: Path) -> None:
    toolchain.set_up(tmp_path, TOOLCHAIN, dry_run=False, run=FakeTools())
    newer = Toolchain("2.6.0", ">=3.14,<3.16", TOOLCHAIN.mise)
    result = toolchain.set_up(tmp_path, newer, dry_run=False, run=FakeTools())
    assert result.done == ["wrote pyproject.toml", "installed iglootools 2.6.0 with uv"]
    assert "@v2.6.0" in (tmp_path / "pyproject.toml").read_text(encoding="utf-8")


def test_a_dry_run_writes_nothing(tmp_path: Path) -> None:
    tools = FakeTools()
    result = toolchain.set_up(tmp_path, TOOLCHAIN, dry_run=True, run=tools)
    assert result.done == [
        "would write mise.toml",
        "would write pyproject.toml",
        "would install iglootools 2.5.0 with uv",
    ]
    assert tools.commands == []
    assert list(tmp_path.iterdir()) == []


def test_a_failed_install_is_a_problem(tmp_path: Path) -> None:
    result = toolchain.set_up(
        tmp_path,
        TOOLCHAIN,
        dry_run=False,
        run=FakeTools(failing="sync"),
    )
    assert result.done == ["wrote mise.toml", "wrote pyproject.toml"]
    assert result.problems == [
        "`mise exec -- uv sync --python 3.15.2` failed: no network",
    ]

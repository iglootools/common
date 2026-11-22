from pathlib import Path
from textwrap import dedent

import pytest

from iglootools.project import ProjectError, ProjectErrorKind, load_project


def write_pyproject(root: Path, content: str) -> Path:
    (root / "pyproject.toml").write_text(dedent(content), encoding="utf-8")
    return root


def test_defaults_come_from_the_project_name(tmp_path: Path) -> None:
    project = load_project(write_pyproject(tmp_path, '[project]\nname = "my-tool"\n'))
    assert project.package == "my_tool"
    assert project.docs.cli_module == "my_tool.cli"
    assert project.docs.cli_name == "my-tool"
    assert project.docs.cli_reference == tmp_path / "docs/cli-reference.md"
    assert project.docs.architecture == tmp_path / "docs/architecture.md"
    assert project.docs.depgraph_exclude == ()
    assert project.name == "my-tool"
    assert project.demo.script == tmp_path / "demo/demo.sh"
    assert project.demo.recording == tmp_path / "demo/demo.cast"
    assert project.demo.workflow == "demo.yml"
    assert project.demo.readme == tmp_path / "README.md"
    assert project.demo.poster == tmp_path / "demo/demo.svg"
    assert project.fallback_version is None


def test_settings_override_the_defaults(tmp_path: Path) -> None:
    project = load_project(
        write_pyproject(
            tmp_path,
            """\
            [project]
            name = "nbkp"
            dependencies = ["typer>=0.27"]
            optional-dependencies = { docker = ["docker>=7"] }

            [tool.uv-dynamic-versioning]
            fallback-version = "0.0.0"

            [tool.iglootools]
            package = "nbkp_core"

            [tool.iglootools.docs]
            depgraph-exclude = ["nbkp_core.templates"]
            architecture = "ARCHITECTURE.md"
            """,
        ),
    )
    assert project.package == "nbkp_core"
    assert project.docs.cli_module == "nbkp_core.cli"
    assert project.docs.architecture == tmp_path / "ARCHITECTURE.md"
    assert project.docs.depgraph_exclude == ("nbkp_core.templates",)
    assert project.requirements == ("typer>=0.27", "docker>=7")
    assert project.fallback_version == "0.0.0"


@pytest.mark.parametrize(
    ("content", "kind", "setting"),
    [
        ("[tool.ruff]\n", ProjectErrorKind.NO_PROJECT_NAME, None),
        (
            '[project]\nname = "x"\n[tool.iglootools.docs]\ndepgraph-exclude = "x"\n',
            ProjectErrorKind.INVALID_SETTING,
            "depgraph-exclude",
        ),
        (
            '[project]\nname = "x"\n[tool.iglootools]\npackage = 3\n',
            ProjectErrorKind.INVALID_SETTING,
            "package",
        ),
    ],
)
def test_invalid_pyproject_is_reported_by_kind(
    tmp_path: Path,
    content: str,
    kind: ProjectErrorKind,
    setting: str | None,
) -> None:
    with pytest.raises(ProjectError) as raised:
        load_project(write_pyproject(tmp_path, content))
    assert (raised.value.kind, raised.value.setting) == (kind, setting)


def test_missing_pyproject_is_reported(tmp_path: Path) -> None:
    with pytest.raises(ProjectError) as raised:
        load_project(tmp_path)
    assert raised.value.kind == ProjectErrorKind.NO_PYPROJECT

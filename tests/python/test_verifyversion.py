"""
The guard against 0.0.0 wheels.

It is the only check between a fallback-versioned wheel and PyPI, where a version number
can never be reused. Ported from nbkp's tests.
"""

import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from iglootools.cli import app

PYPROJECT = """\
[project]
name = "nbkp"

[tool.uv-dynamic-versioning]
fallback-version = "0.0.0"
"""


def project(root: Path, pyproject: str = PYPROJECT) -> Path:
    (root / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    (root / "dist").mkdir()
    return root


def wheel(root: Path, version: str, *, filename_version: str | None = None) -> Path:
    path = root / "dist" / f"nbkp-{filename_version or version}-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            f"nbkp-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.4\nName: nbkp\nVersion: {version}\n",
        )
    return path


def verify(root: Path) -> tuple[int, str]:
    result = CliRunner().invoke(app, ["--root", str(root), "python", "verify-version"])
    return result.exit_code, result.output


def test_fallback_version_fails(tmp_path: Path) -> None:
    wheel(project(tmp_path), "0.0.0")
    code, output = verify(tmp_path)
    assert code == 1
    assert "dist/nbkp-0.0.0-py3-none-any.whl" in output


def test_fallback_among_good_wheels_fails(tmp_path: Path) -> None:
    wheel(project(tmp_path), "1.2.3")
    wheel(tmp_path, "0.0.0")
    assert verify(tmp_path)[0] == 1


def test_empty_dist_dir_fails(tmp_path: Path) -> None:
    """A build that produced no wheel must not pass as verified."""
    assert verify(project(tmp_path))[0] == 1


@pytest.mark.parametrize("version", ["1.0.0.dev0", "10.0.0", "0.2.1.post5.dev0"])
def test_real_version_passes(tmp_path: Path, version: str) -> None:
    wheel(project(tmp_path), version)
    assert verify(tmp_path) == (0, f"nbkp-{version}-py3-none-any.whl: {version}\n")


def test_version_read_from_metadata_not_filename(tmp_path: Path) -> None:
    wheel(project(tmp_path), "0.0.0", filename_version="1.0.0")
    assert verify(tmp_path)[0] == 1


def test_wheel_without_metadata_is_an_error(tmp_path: Path) -> None:
    with zipfile.ZipFile(
        project(tmp_path) / "dist" / "nbkp-1.0.0-py3-none-any.whl",
        "w",
    ) as zf:
        zf.writestr("nbkp/__init__.py", "")
    code, output = verify(tmp_path)
    assert code == 1
    assert "no .dist-info/METADATA" in output


def test_a_project_without_a_fallback_version_is_an_error(tmp_path: Path) -> None:
    wheel(project(tmp_path, '[project]\nname = "nbkp"\n'), "1.0.0")
    code, output = verify(tmp_path)
    assert code == 1
    assert "fallback-version" in output

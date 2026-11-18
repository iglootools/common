from collections.abc import Sequence
from pathlib import Path

import pytest

from iglootools.python import environment


def touch(root: Path, *names: str) -> None:
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()


def test_build_artifacts_skip_the_environment_and_git(tmp_path: Path) -> None:
    touch(
        tmp_path,
        "dist/pkg-1.0.whl",
        "build/lib/pkg.py",
        "pkg.egg-info/PKG-INFO",
        "pkg/__pycache__/mod.cpython-314.pyc",
        "pkg/stray.pyc",
        ".venv/lib/__pycache__/x.pyc",
        ".git/hooks/__pycache__/y.pyc",
        "pkg/module.py",
    )
    assert environment.build_artifacts(tmp_path) == [
        tmp_path / "build",
        tmp_path / "dist",
        tmp_path / "pkg.egg-info",
        tmp_path / "pkg/__pycache__",
        tmp_path / "pkg/stray.pyc",
    ]


def test_remove_deletes_directories_and_files(tmp_path: Path) -> None:
    touch(tmp_path, "dist/a.whl", "pkg/stray.pyc", "pkg/module.py")
    environment.remove([tmp_path / "dist", tmp_path / "pkg/stray.pyc"])
    assert sorted(p.name for p in tmp_path.rglob("*")) == ["module.py", "pkg"]


class Recorder:
    def __init__(self, status: int = 0, writes: str | None = None) -> None:
        self.calls: list[tuple[tuple[str, ...], Path]] = []
        self.status = status
        self.writes = writes

    def __call__(self, command: Sequence[str], directory: Path) -> int:
        self.calls.append((tuple(command), directory))
        if self.writes:
            touch(directory, self.writes)
        return self.status


def test_build_empties_dist_first_and_reports_what_was_built(tmp_path: Path) -> None:
    touch(tmp_path, "dist/stale-0.1.whl")
    run = Recorder(writes="dist/pkg-1.0.whl")
    assert environment.build(tmp_path, run=run) == [tmp_path / "dist/pkg-1.0.whl"]
    assert run.calls == [(("uv", "build", "--sdist", "--wheel"), tmp_path)]


def test_a_failed_build_says_which_command_failed(tmp_path: Path) -> None:
    with pytest.raises(environment.EnvironmentCommandError) as raised:
        environment.build(tmp_path, run=Recorder(status=2))
    assert (raised.value.command, raised.value.status) == (
        ("uv", "build", "--sdist", "--wheel"),
        2,
    )


def test_reinstall_deletes_the_venv_then_reinstalls(tmp_path: Path) -> None:
    touch(tmp_path, ".venv/bin/python")
    run = Recorder()
    environment.reinstall(tmp_path, run=run)
    assert not (tmp_path / ".venv").exists()
    assert run.calls == [(("mise", "deps", "install", "uv", "--force"), tmp_path)]

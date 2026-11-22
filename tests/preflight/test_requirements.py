import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from iglootools.preflight import requirements
from iglootools.preflight.requirements import CLAUDE, GIT, GITHUB_TOKEN, MISE, Result


def _which(*present: str) -> requirements.Which:
    return lambda name: f"/usr/bin/{name}" if name in present else None


def _gh(stdout: str, returncode: int = 0) -> requirements.Run:
    def run(
        command: Sequence[str],
        _directory: Path,
    ) -> subprocess.CompletedProcess[str]:
        assert list(command) == ["gh", "auth", "token"]
        return subprocess.CompletedProcess(command, returncode, stdout, "")

    return run


def test_programs_are_found_on_path(tmp_path: Path) -> None:
    results = requirements.check(
        (GIT, CLAUDE),
        tmp_path,
        environ={},
        which=_which("git"),
    )
    assert results == [
        Result(GIT, ok=True, detail="/usr/bin/git"),
        Result(CLAUDE, ok=False, detail="not on PATH"),
    ]


@pytest.mark.parametrize(
    ("environ", "which", "run", "expected"),
    [
        (
            {"GH_TOKEN": "t"},
            _which(),
            _gh(""),
            Result(GITHUB_TOKEN, ok=True, detail="from GH_TOKEN"),
        ),
        (
            {"GITHUB_TOKEN": "t"},
            _which(),
            _gh(""),
            Result(GITHUB_TOKEN, ok=True, detail="from GITHUB_TOKEN"),
        ),
        (
            {},
            _which("gh"),
            _gh("gho_x\n"),
            Result(GITHUB_TOKEN, ok=True, detail="from gh"),
        ),
        (
            {},
            _which("gh"),
            _gh("", returncode=1),
            Result(GITHUB_TOKEN, ok=False, detail="gh is not logged in"),
        ),
        (
            {},
            _which(),
            _gh(""),
            Result(
                GITHUB_TOKEN,
                ok=False,
                detail="no GH_TOKEN or GITHUB_TOKEN, and no gh",
            ),
        ),
    ],
)
def test_the_github_token_comes_from_the_environment_or_gh(
    tmp_path: Path,
    environ: dict[str, str],
    which: requirements.Which,
    run: requirements.Run,
    expected: Result,
) -> None:
    assert requirements.check(
        (GITHUB_TOKEN,),
        tmp_path,
        environ=environ,
        which=which,
        run=run,
    ) == [expected]


def test_each_requirement_names_the_subsystems_that_need_it() -> None:
    assert requirements.needed_by(GIT) == ["github", "common"]
    assert requirements.needed_by(MISE) == ["common", "build"]
    assert requirements.needed_by(CLAUDE) == ["common"]


def test_preflight_checks_every_requirement_once() -> None:
    assert requirements.ALL == (GIT, GITHUB_TOKEN, MISE, CLAUDE)

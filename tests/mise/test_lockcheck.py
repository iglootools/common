import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from iglootools.mise import lockcheck

STAGED = {"mise.toml": '[tools]\nuv = "0.13.7"\n', "mise.lock": "[[tools.uv]]\nold\n"}


class FakeTools:
    """`git show :<file>` answers from STAGED; `mise lock` writes *regenerated*."""

    def __init__(self, regenerated: str, lock_status: int = 0) -> None:
        self.regenerated = regenerated
        self.lock_status = lock_status
        self.lock_env: Mapping[str, str] = {}

    def __call__(
        self, command: Sequence[str], directory: Path, env: Mapping[str, str]
    ) -> subprocess.CompletedProcess[str]:
        match list(command):
            case ["git", "show", spec]:
                name = spec.removeprefix(":")
                found = name in STAGED
                return subprocess.CompletedProcess(
                    command, 0 if found else 128, STAGED.get(name, ""), ""
                )
            case ["mise", "lock"]:
                self.lock_env = env
                assert (directory / "mise.toml").read_text() == STAGED["mise.toml"]
                (directory / "mise.lock").write_text(self.regenerated)
                return subprocess.CompletedProcess(
                    command, self.lock_status, "", "network down"
                )
            case _:
                raise AssertionError(f"unexpected command {command}")


def test_an_unchanged_lock_is_up_to_date(tmp_path: Path) -> None:
    result = lockcheck.compare(tmp_path, run=FakeTools(STAGED["mise.lock"]), environ={})
    assert result.up_to_date


def test_a_changed_lock_is_reported_as_a_diff(tmp_path: Path) -> None:
    result = lockcheck.compare(
        tmp_path, run=FakeTools("[[tools.uv]]\nnew\n"), environ={}
    )
    assert not result.up_to_date
    assert "-old\n" in result.diff()
    assert "+new\n" in result.diff()


def test_mise_lock_runs_without_the_python_override_and_trusts_only_scratch(
    tmp_path: Path,
) -> None:
    tools = FakeTools(STAGED["mise.lock"])
    lockcheck.compare(
        tmp_path, run=tools, environ={"MISE_PYTHON_VERSION": "3.9", "PATH": "/bin"}
    )
    assert "MISE_PYTHON_VERSION" not in tools.lock_env
    assert tools.lock_env["PATH"] == "/bin"
    assert tools.lock_env["MISE_TRUSTED_CONFIG_PATHS"] != str(tmp_path)


def test_a_failing_mise_lock_is_an_error_not_a_pass(tmp_path: Path) -> None:
    tools = FakeTools(STAGED["mise.lock"], lock_status=1)
    with pytest.raises(lockcheck.LockCheckError) as raised:
        lockcheck.compare(tmp_path, run=tools, environ={})
    assert (raised.value.kind, raised.value.detail) == (
        lockcheck.LockCheckErrorKind.MISE_LOCK_FAILED,
        "network down",
    )


def test_an_unstaged_file_is_reported(tmp_path: Path) -> None:
    def no_lock(
        command: Sequence[str], directory: Path, env: Mapping[str, str]
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            command, 128 if "lock" in command[2] else 0, "", ""
        )

    with pytest.raises(lockcheck.LockCheckError) as raised:
        lockcheck.compare(tmp_path, run=no_lock, environ={})
    assert (raised.value.kind, raised.value.detail) == (
        lockcheck.LockCheckErrorKind.NOT_STAGED,
        "mise.lock",
    )

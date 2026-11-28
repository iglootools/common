import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from iglootools.github.client import Run, capture
from iglootools.workspace import clone
from iglootools.workspace.clone import CloneAction, CloneProtocol, CloneResult
from iglootools.workspace.repositories import OrganizationRepository
from tests.conftest import commit, git


def _origin(tmp_path: Path, name: str) -> Path:
    """Create a bare repository with one commit on main, standing in for GitHub."""
    bare = tmp_path / "github" / f"{name}.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(bare))
    seed = tmp_path / "seed" / name
    git(tmp_path, "clone", "-q", str(bare), str(seed))
    git(seed, "switch", "-q", "-c", "main")
    commit(seed, "first")
    git(seed, "push", "-q", "origin", "main")
    return bare


def _repository(tmp_path: Path, name: str) -> OrganizationRepository:
    bare = _origin(tmp_path, name)
    return OrganizationRepository(
        name,
        archived=False,
        default_branch="main",
        ssh_url=str(bare),
        https_url=str(bare),
    )


def _as_github(origins: dict[str, str]) -> Run:
    """Run git for real, but answer `remote get-url` with the GitHub URL given."""

    def run(
        command: Sequence[str],
        directory: Path,
    ) -> subprocess.CompletedProcess[str]:
        if list(command) == ["git", "remote", "get-url", "origin"]:
            url = origins[directory.name]
            return subprocess.CompletedProcess(command, 0, f"{url}\n", "")
        return capture(command, directory)

    return run


@pytest.mark.parametrize(
    ("origins", "protocol"),
    [
        ([], CloneProtocol.SSH),
        (["git@github.com:iglootools/nbkp.git"], CloneProtocol.SSH),
        (["https://github.com/iglootools/nbkp.git"], CloneProtocol.HTTPS),
        (
            [
                "https://github.com/iglootools/nbkp.git",
                "git@github.com:iglootools/photree.git",
            ],
            CloneProtocol.SSH,
        ),
    ],
)
def test_infer_protocol_follows_the_checkouts_already_there(
    origins: list[str],
    protocol: CloneProtocol,
) -> None:
    assert clone.infer_protocol(origins) == protocol


def test_a_missing_repository_is_cloned(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository = _repository(tmp_path, "nbkp")
    result = clone.clone_one(
        workspace,
        repository,
        CloneProtocol.SSH,
        fetch=True,
        dry_run=False,
    )
    assert result == CloneResult("nbkp", CloneAction.CLONED)
    assert (workspace / "nbkp" / "first").is_file()


def test_a_dry_run_clones_nothing(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository = _repository(tmp_path, "nbkp")
    result = clone.clone_one(
        workspace,
        repository,
        CloneProtocol.SSH,
        fetch=True,
        dry_run=True,
    )
    assert result == CloneResult("nbkp", CloneAction.CLONED)
    assert not (workspace / "nbkp").exists()


def test_a_checkout_already_there_is_fetched(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    repository = _repository(tmp_path, "nbkp")
    git(tmp_path, "clone", "-q", repository.ssh_url, str(workspace / "nbkp"))
    run = _as_github({"nbkp": "git@github.com:iglootools/nbkp.git"})
    result = clone.clone_one(
        workspace,
        repository,
        CloneProtocol.SSH,
        fetch=True,
        dry_run=False,
        run=run,
    )
    assert result == CloneResult("nbkp", CloneAction.FETCHED)
    unfetched = clone.clone_one(
        workspace,
        repository,
        CloneProtocol.SSH,
        fetch=False,
        dry_run=False,
        run=run,
    )
    assert unfetched == CloneResult("nbkp", CloneAction.PRESENT)


def test_a_checkout_of_another_repository_is_reported_not_touched(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    repository = _repository(tmp_path, "nbkp")
    git(tmp_path, "clone", "-q", repository.ssh_url, str(workspace / "nbkp"))
    run = _as_github({"nbkp": "git@github.com:someone/nbkp.git"})
    result = clone.clone_one(
        workspace,
        repository,
        CloneProtocol.SSH,
        fetch=True,
        dry_run=False,
        run=run,
    )
    assert result == CloneResult(
        "nbkp",
        CloneAction.FAILED,
        "its origin is someone/nbkp, not iglootools/nbkp",
    )


def test_a_directory_that_is_not_a_checkout_is_reported(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "nbkp").mkdir(parents=True)
    result = clone.clone_one(
        workspace,
        _repository(tmp_path, "nbkp"),
        CloneProtocol.SSH,
        fetch=True,
        dry_run=False,
    )
    assert result.action == CloneAction.FAILED
    assert result.problem.endswith("exists but is not a git checkout")


def test_a_clone_that_fails_says_why(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    missing = OrganizationRepository(
        "gone",
        archived=False,
        default_branch="main",
        ssh_url=str(tmp_path / "nowhere.git"),
        https_url="",
    )
    result = clone.clone_one(
        workspace,
        missing,
        CloneProtocol.SSH,
        fetch=True,
        dry_run=False,
    )
    assert result.action == CloneAction.FAILED
    assert result.problem.startswith(f"git clone {tmp_path / 'nowhere.git'} failed: ")

from pathlib import Path

import pytest

from iglootools.workspace.location import (
    SENTINEL,
    Workspace,
    WorkspaceError,
    WorkspaceErrorKind,
    WorkspaceSource,
    resolve_workspace,
)


def _tree(tmp_path: Path) -> tuple[Path, Path]:
    """Return a workspace directory and common's checkout inside it."""
    workspace = tmp_path / "Workspace" / "iglootools"
    checkout = workspace / "common"
    checkout.mkdir(parents=True)
    return workspace, checkout


def test_the_environment_variable_names_the_workspace(tmp_path: Path) -> None:
    workspace, checkout = _tree(tmp_path)
    (checkout / SENTINEL).mkdir()
    found = resolve_workspace(
        checkout,
        environ={"IGLOOTOOLS_WORKSPACE": str(workspace)},
    )
    assert found == Workspace(workspace, WorkspaceSource.ENVIRONMENT)


def test_a_leading_tilde_is_the_home_directory(tmp_path: Path) -> None:
    workspace, checkout = _tree(tmp_path)
    found = resolve_workspace(
        checkout,
        environ={
            "IGLOOTOOLS_WORKSPACE": "~/Workspace/iglootools",
            "HOME": str(tmp_path),
        },
    )
    assert found.path == workspace


@pytest.mark.parametrize("value", ["", "  "])
def test_an_empty_variable_falls_back_to_the_sentinel(
    tmp_path: Path,
    value: str,
) -> None:
    workspace, checkout = _tree(tmp_path)
    (workspace / SENTINEL).mkdir()
    found = resolve_workspace(checkout, environ={"IGLOOTOOLS_WORKSPACE": value})
    assert found == Workspace(workspace, WorkspaceSource.SENTINEL)


@pytest.mark.parametrize(
    ("value", "kind"),
    [
        ("Workspace/iglootools", WorkspaceErrorKind.RELATIVE),
        ("/no/such/directory", WorkspaceErrorKind.NOT_A_DIRECTORY),
    ],
)
def test_an_unusable_variable_is_an_error_even_with_a_sentinel(
    tmp_path: Path,
    value: str,
    kind: WorkspaceErrorKind,
) -> None:
    workspace, checkout = _tree(tmp_path)
    (workspace / SENTINEL).mkdir()
    with pytest.raises(WorkspaceError) as raised:
        resolve_workspace(checkout, environ={"IGLOOTOOLS_WORKSPACE": value})
    assert (raised.value.kind, raised.value.configured) == (kind, value)


def test_the_nearest_sentinel_above_the_start_wins(tmp_path: Path) -> None:
    workspace, checkout = _tree(tmp_path)
    (tmp_path / SENTINEL).mkdir()
    (workspace / SENTINEL).mkdir()
    found = resolve_workspace(checkout / "src", environ={})
    assert found == Workspace(workspace, WorkspaceSource.SENTINEL)


def test_a_file_named_like_the_sentinel_marks_nothing(tmp_path: Path) -> None:
    workspace, checkout = _tree(tmp_path)
    (workspace / SENTINEL).touch()
    with pytest.raises(WorkspaceError) as raised:
        resolve_workspace(checkout, environ={})
    assert raised.value.kind == WorkspaceErrorKind.NOT_FOUND


def test_nothing_configured_is_an_error_naming_where_the_search_began(
    tmp_path: Path,
) -> None:
    _, checkout = _tree(tmp_path)
    with pytest.raises(WorkspaceError) as raised:
        resolve_workspace(checkout, environ={})
    assert (raised.value.kind, raised.value.start) == (
        WorkspaceErrorKind.NOT_FOUND,
        checkout,
    )

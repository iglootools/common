import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from iglootools.docs import depgraph

# Trimmed from real pydeps --show-dot output: node ids, labels, and edges that point from a
# dependency to its dependent.
DOT = """\
digraph G {
    config [label="config" fillcolor="#ffffff"];
    sync [label="sync" fillcolor="#ffffff"];
    cli [label="cli" fillcolor="#ffffff"];
    config -> sync [fillcolor="#000000"];
    sync -> cli [fillcolor="#000000"];
    config -> cli [fillcolor="#000000"];
}
"""


def test_parse_dot_reverses_edges_to_point_at_the_dependency() -> None:
    graph = depgraph.parse_dot(DOT)
    assert graph.nodes == ("cli", "config", "sync")
    assert graph.edges == (("cli", "config"), ("cli", "sync"), ("sync", "config"))


def test_mermaid_marks_packages_with_a_slash_and_is_sorted() -> None:
    mermaid = depgraph.to_mermaid(
        depgraph.parse_dot(DOT), is_package=lambda label: label == "sync"
    )
    assert mermaid == (
        "graph TD\n"
        '    cli["cli"]\n'
        '    config["config"]\n'
        '    sync["sync/"]\n'
        "\n"
        "    cli --> config\n"
        "    cli --> sync\n"
        "    sync --> config"
    )


def test_splice_replaces_only_the_marked_section() -> None:
    document = f"# Architecture\n\n{depgraph.BEGIN_MARKER}\nold\n{depgraph.END_MARKER}\n\nAfter.\n"
    assert depgraph.splice(document, "NEW") == "# Architecture\n\nNEW\n\nAfter.\n"


def test_splice_without_markers_is_an_error() -> None:
    with pytest.raises(depgraph.DepgraphError) as raised:
        depgraph.splice("# Architecture\n", "NEW")
    assert raised.value.kind == depgraph.DepgraphErrorKind.MARKERS_MISSING


def test_third_party_imports_maps_requirements_to_import_names() -> None:
    distributions = {
        "yaml": ["PyYAML"],
        "typer": ["typer"],
        "rich": ["rich"],
        "_cffi_backend": ["cffi"],
    }
    requirements = ["pyyaml>=6.0,<7.0", "typer[all]>=0.27", "Rich ; python_version>'3'"]
    assert depgraph.third_party_imports(requirements, distributions) == [
        "rich",
        "typer",
        "yaml",
    ]


def test_pydeps_command_excludes_only_when_given_something() -> None:
    command = depgraph.pydeps_command(Path("/src/pkg"), [], python="py")
    assert command[:4] == ["py", "-m", "pydeps", "/src/pkg"]
    assert "--exclude" not in command
    assert depgraph.pydeps_command(Path("/src/pkg"), ["a", "b"])[-3:] == [
        "--exclude",
        "a",
        "b",
    ]


def completed(code: int, stdout: str = "", stderr: str = "") -> depgraph.Run:
    def run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, code, stdout, stderr)

    return run


def test_run_pydeps_needs_graphviz() -> None:
    with pytest.raises(depgraph.DepgraphError) as raised:
        depgraph.run_pydeps(["pydeps"], run=completed(0, DOT), which=lambda _: None)
    assert raised.value.kind == depgraph.DepgraphErrorKind.GRAPHVIZ_MISSING


def test_run_pydeps_reports_its_stderr_on_failure() -> None:
    with pytest.raises(depgraph.DepgraphError) as raised:
        depgraph.run_pydeps(
            ["pydeps"], run=completed(2, stderr="boom"), which=lambda _: "/bin/dot"
        )
    assert (raised.value.kind, raised.value.detail) == (
        depgraph.DepgraphErrorKind.PYDEPS_FAILED,
        "boom",
    )


def test_package_directory_of_a_missing_package_is_an_error() -> None:
    with pytest.raises(depgraph.DepgraphError) as raised:
        depgraph.package_directory("no_such_package_here")
    assert raised.value.kind == depgraph.DepgraphErrorKind.PACKAGE_NOT_FOUND

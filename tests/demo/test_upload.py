import json
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from iglootools.demo import upload
from iglootools.project import DemoSettings

SETTINGS = DemoSettings(
    script=Path("demo/demo.sh"),
    recording=Path("demo/demo.cast"),
    window_size="160x45",
    workflow="demo.yml",
    artifact="demo-recording",
    cast="demo.cast",
    readme=Path("README.md"),
    poster=Path("demo/demo.svg"),
)
RUN: dict[str, object] = {
    "databaseId": 42,
    "createdAt": "2026-11-17T10:00:00Z",
    "headBranch": "main",
    "displayTitle": "release v1.2.0",
}


class FakeGh:
    """Answers commands by their first words, and records every command it was given."""

    def __init__(
        self,
        answers: dict[str, Callable[[Sequence[str]], tuple[int, str]]],
    ) -> None:
        self.answers = answers
        self.commands: list[list[str]] = []

    def __call__(self, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        self.commands.append(list(command))
        key = next(k for k in self.answers if " ".join(command).startswith(k))
        code, out = self.answers[key](command)
        return subprocess.CompletedProcess(command, code, out, "" if code == 0 else out)


def test_latest_run_prefers_main_and_falls_back_to_any_branch() -> None:
    gh = FakeGh(
        {
            "gh run list": lambda c: (0, json.dumps([] if "--branch" in c else [RUN])),
        },
    )
    found = upload.latest_run(SETTINGS, run=gh)
    assert (found.run_id, found.branch) == ("42", "main")
    assert [("--branch" in c) for c in gh.commands] == [True, False]


def test_no_successful_run_is_an_error() -> None:
    with pytest.raises(upload.DemoError) as raised:
        upload.latest_run(SETTINGS, run=FakeGh({"gh run list": lambda _: (0, "[]")}))
    assert raised.value.kind == upload.DemoErrorKind.NO_SUCCESSFUL_RUN


def test_a_failing_gh_command_carries_its_stderr() -> None:
    with pytest.raises(upload.DemoError) as raised:
        upload.view_run("42", run=FakeGh({"gh run view": lambda _: (1, "not found")}))
    assert (raised.value.kind, raised.value.detail) == (
        upload.DemoErrorKind.COMMAND_FAILED,
        "not found",
    )


def test_download_finds_the_cast_anywhere_in_the_artifact(tmp_path: Path) -> None:
    def download(command: Sequence[str]) -> tuple[int, str]:
        cast = Path(command[command.index("--dir") + 1]) / "nested" / "demo.cast"
        cast.parent.mkdir()
        cast.write_text('{"title": "nbkp 1.2.0"}\n', encoding="utf-8")
        return 0, ""

    run = upload.WorkflowRun.from_json(RUN)
    cast = upload.download_cast(
        SETTINGS,
        run,
        tmp_path,
        run=FakeGh({"gh run download": download}),
    )
    assert upload.cast_title(cast) == "nbkp 1.2.0"


def test_an_artifact_without_the_cast_is_an_error(tmp_path: Path) -> None:
    run = upload.WorkflowRun.from_json(RUN)
    with pytest.raises(upload.DemoError) as raised:
        upload.download_cast(
            SETTINGS,
            run,
            tmp_path,
            run=FakeGh({"gh run download": lambda _: (0, "")}),
        )
    assert raised.value.kind == upload.DemoErrorKind.NO_CAST_IN_ARTIFACT


@pytest.mark.parametrize(
    ("header", "title"),
    [('{"title": "x"}', "x"), ('{"version": 2}', None), ("not json", None)],
)
def test_cast_title(tmp_path: Path, header: str, title: str | None) -> None:
    cast = tmp_path / "demo.cast"
    cast.write_text(f'{header}\n[0.1, "o", "hi"]\n', encoding="utf-8")
    assert upload.cast_title(cast) == title


def test_recording_url_is_read_from_any_server() -> None:
    output = "View the recording at:\n\n    https://asciinema.example/a/AbC123.\n"
    assert upload.recording_url(output) == "https://asciinema.example/a/AbC123"
    assert upload.recording_url("Error: unauthorized") is None


def test_apply_embed_repoints_the_first_embed_at_the_repository_image() -> None:
    readme = (
        "# nbkp\n\n[![asciicast](https://asciinema.org/a/old.svg)](https://asciinema.org/a/old)\n"
        "Later: [![asciicast](x.svg)](x)\n"
    )
    update = upload.apply_embed(readme, "https://asciinema.org/a/new", "demo/demo.svg")
    assert (update.found, update.changed) == (True, True)
    assert update.content.startswith(
        "# nbkp\n\n[![asciicast](demo/demo.svg)](https://asciinema.org/a/new)\n",
    )
    assert update.content.endswith("Later: [![asciicast](x.svg)](x)\n")


def test_apply_embed_reports_a_missing_or_unchanged_embed() -> None:
    assert upload.apply_embed("# no embed\n", "u", "demo/demo.svg").found is False
    current = upload.render_embed("https://asciinema.org/a/same", "demo/demo.svg")
    unchanged = upload.apply_embed(
        current,
        "https://asciinema.org/a/same",
        "demo/demo.svg",
    )
    assert unchanged.changed is False


SVG = b'<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg"></svg>\n'


def test_download_poster_saves_asciinemas_svg_of_the_recording(tmp_path: Path) -> None:
    fetched: list[str] = []

    def fetch(url: str) -> bytes:
        fetched.append(url)
        return SVG

    poster = tmp_path / "demo" / "demo.svg"
    upload.download_poster("https://asciinema.org/a/AbC", poster, fetch=fetch)
    assert fetched == ["https://asciinema.org/a/AbC.svg"]
    assert poster.read_bytes() == SVG


@pytest.mark.parametrize(
    ("answer", "detail"),
    [
        (b"<html>Not found</html>", "not an SVG image"),
        (OSError("timed out"), "timed out"),
    ],
)
def test_download_poster_refuses_what_is_not_an_svg(
    tmp_path: Path,
    answer: bytes | OSError,
    detail: str,
) -> None:
    def fetch(_url: str) -> bytes:
        if isinstance(answer, OSError):
            raise answer
        return answer

    poster = tmp_path / "demo.svg"
    with pytest.raises(upload.DemoError) as raised:
        upload.download_poster("https://asciinema.org/a/AbC", poster, fetch=fetch)
    assert (raised.value.kind, raised.value.detail) == (
        upload.DemoErrorKind.POSTER_FAILED,
        detail,
    )
    assert not poster.exists()


def test_commit_demo_commits_the_readme_and_a_new_poster_only(git_repo: Path) -> None:
    git = ["git", "-C", str(git_repo), "-c", "user.name=t", "-c", "user.email=t@t"]
    readme, poster, other = (git_repo / name for name in ("README.md", "demo.svg", "x"))
    readme.write_text("v1\n", encoding="utf-8")
    subprocess.run([*git, "add", "README.md"], check=True)
    subprocess.run([*git, "commit", "-qm", "init"], check=True)
    readme.write_text("v2\n", encoding="utf-8")
    poster.write_bytes(SVG)
    other.write_text("unrelated\n", encoding="utf-8")

    def run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [*git, *command[3:]],
            capture_output=True,
            text=True,
            check=False,
        )

    workflow_run = upload.WorkflowRun.from_json(RUN)
    summary = upload.commit_demo(
        (readme, poster),
        "https://asciinema.org/a/AbC",
        workflow_run,
        git_repo,
        run=run,
    )
    assert "point the demo at AbC" in summary
    committed = subprocess.run(
        [*git, "show", "--name-only", "--format=", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.split()  # fmt: skip
    assert committed == ["README.md", "demo.svg"]


def test_upload_failure_keeps_asciinemas_message(tmp_path: Path) -> None:
    gh = FakeGh({"asciinema upload": lambda _: (1, "connection timed out")})
    with pytest.raises(upload.DemoError) as raised:
        upload.upload(tmp_path / "demo.cast", run=gh)
    assert (raised.value.kind, raised.value.detail) == (
        upload.DemoErrorKind.UPLOAD_FAILED,
        "connection timed out",
    )


def test_has_uncommitted_changes(git_repo: Path) -> None:
    readme = git_repo / "README.md"
    readme.write_text("v1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(git_repo), "add", "README.md"], check=True)
    subprocess.run(
        ["git", "-C", str(git_repo), "-c", "user.name=t", "-c", "user.email=t@t",
         "commit", "-qm", "init"],
        check=True,
    )  # fmt: skip
    assert upload.has_uncommitted_changes(readme, git_repo) is False
    readme.write_text("v2\n", encoding="utf-8")
    assert upload.has_uncommitted_changes(readme, git_repo) is True

"""Publishing the demo that CI recorded to asciinema.org.

GitHub-hosted runners have no route to asciinema.org, so the demo workflow records the cast
and keeps it as an artifact, and this is the manual half: download the artifact, upload the
cast unchanged (its title was written into the header at record time), point the README's
asciicast embed at the new recording, and commit that one file.
"""

import json
import re
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from iglootools.project import DemoSettings

type Capture = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]
"""Runs a command and returns its result with stdout and stderr captured."""

# Release-triggered runs land on the default branch and their recordings carry a release
# version; a pull request branch would title the cast with a .devN version.
PREFERRED_BRANCH = "main"
_RUN_FIELDS = "databaseId,createdAt,headBranch,displayTitle"
# [![asciicast](<url>.svg)](<url>), the embed near the top of the README.
_EMBED = re.compile(r"\[!\[asciicast\]\([^)]*\)\]\([^)]*\)")
# asciinema prints the recording URL on success. The server need not be asciinema.org.
_RECORDING_URL = re.compile(r"https?://\S+?/a/[A-Za-z0-9]+")


class DemoErrorKind(StrEnum):
    TOOL_MISSING = "tool-missing"
    COMMAND_FAILED = "command-failed"
    NO_SUCCESSFUL_RUN = "no-successful-run"
    NO_CAST_IN_ARTIFACT = "no-cast-in-artifact"
    UPLOAD_FAILED = "upload-failed"


class DemoError(RuntimeError):
    def __init__(
        self,
        kind: DemoErrorKind,
        command: Sequence[str] = (),
        detail: str = "",
    ) -> None:
        super().__init__(f"{kind}: {' '.join(command)} {detail}".rstrip())
        self.kind = kind
        self.command = tuple(command)
        self.detail = detail


@dataclass(frozen=True)
class WorkflowRun:
    run_id: str
    created_at: str
    branch: str
    title: str

    @staticmethod
    def from_json(payload: dict[str, object]) -> WorkflowRun:
        """One entry of `gh run list --json` or `gh run view --json`."""
        return WorkflowRun(
            run_id=str(payload.get("databaseId", "")),
            created_at=str(payload.get("createdAt", "")),
            branch=str(payload.get("headBranch", "")),
            title=str(payload.get("displayTitle", "")),
        )


@dataclass(frozen=True)
class ReadmeUpdate:
    found: bool
    changed: bool
    content: str


def capture(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise DemoError(DemoErrorKind.TOOL_MISSING, command) from None


def _stdout(command: Sequence[str], run: Capture) -> str:
    result = run(command)
    if result.returncode != 0:
        raise DemoError(DemoErrorKind.COMMAND_FAILED, command, result.stderr)
    return result.stdout


def _runs(
    settings: DemoSettings, branch: str | None, run: Capture
) -> list[WorkflowRun]:
    output = _stdout(
        [
            "gh", "run", "list", "--workflow", settings.workflow,
            "--status", "success", "--limit", "1", "--json", _RUN_FIELDS,
            *(["--branch", branch] if branch else []),
        ],
        run,
    )  # fmt: skip
    return [WorkflowRun.from_json(entry) for entry in json.loads(output or "[]")]


def view_run(run_id: str, run: Capture = capture) -> WorkflowRun:
    output = _stdout(["gh", "run", "view", run_id, "--json", _RUN_FIELDS], run)
    return WorkflowRun.from_json(json.loads(output))


def latest_run(settings: DemoSettings, run: Capture = capture) -> WorkflowRun:
    """The newest successful run, preferring the default branch.

    Tag-triggered runs report the tag as their branch, so the branch-scoped search can come
    back empty for a release; any successful run is the fallback.
    """
    candidates = [
        *_runs(settings, PREFERRED_BRANCH, run),
        *_runs(settings, None, run),
    ]
    if not candidates:
        raise DemoError(DemoErrorKind.NO_SUCCESSFUL_RUN)
    return candidates[0]


def download_cast(
    settings: DemoSettings,
    workflow_run: WorkflowRun,
    destination: Path,
    run: Capture = capture,
) -> Path:
    _stdout(
        [
            "gh", "run", "download", workflow_run.run_id,
            "--name", settings.artifact, "--dir", str(destination),
        ],
        run,
    )  # fmt: skip
    casts = sorted(destination.rglob(settings.cast))
    if not casts:
        raise DemoError(DemoErrorKind.NO_CAST_IN_ARTIFACT, detail=workflow_run.run_id)
    return casts[0]


def cast_title(cast: Path) -> str | None:
    """The title in the cast's JSON header, or None when there is none to read."""
    with cast.open(encoding="utf-8") as handle:
        header = handle.readline()
    try:
        parsed = json.loads(header)
    except json.JSONDecodeError:
        return None
    match parsed:
        case {"title": str(title)} if title:
            return title
        case _:
            return None


def upload(cast: Path, run: Capture = capture) -> str:
    """Upload *cast*; returns everything asciinema printed, which holds the URL."""
    command = ["asciinema", "upload", str(cast)]
    result = run(command)
    if result.returncode != 0:
        raise DemoError(DemoErrorKind.UPLOAD_FAILED, command, result.stderr)
    return f"{result.stdout}{result.stderr}"


def recording_url(upload_output: str) -> str | None:
    match = _RECORDING_URL.search(upload_output)
    return match.group(0).rstrip(".,") if match else None


def render_embed(url: str) -> str:
    return f"[![asciicast]({url}.svg)]({url})"


def apply_embed(readme: str, url: str) -> ReadmeUpdate:
    """Point the README's asciicast embed at *url*."""
    updated, count = _EMBED.subn(lambda _: render_embed(url), readme, count=1)
    return ReadmeUpdate(found=count == 1, changed=updated != readme, content=updated)


def has_uncommitted_changes(path: Path, root: Path) -> bool:
    """Checked before uploading: a pathspec `git commit` takes the whole file, so
    committing on top of an edit in progress would sweep it up."""
    return any(
        subprocess.run(
            ["git", "-C", str(root), "diff", *scope, "--quiet", "--", str(path)],
            check=False,
        ).returncode
        != 0
        for scope in ([], ["--cached"])
    )


def commit_readme(
    readme: Path,
    url: str,
    workflow_run: WorkflowRun,
    root: Path,
    run: Capture = capture,
) -> str:
    """Commit the embed change on its own; returns the new commit's one-line summary."""
    message = (
        f"docs(readme): point the demo at {url.rsplit('/', 1)[-1]}\n\n"
        f"Uploaded the recording from demo workflow run {workflow_run.run_id} "
        f"({workflow_run.branch}) with `iglootools demo upload`.\n\n"
        f"{url}\n"
    )
    _stdout(
        ["git", "-C", str(root), "commit", "--message", message, "--", str(readme)], run
    )
    return _stdout(["git", "-C", str(root), "log", "-1", "--oneline"], run).strip()

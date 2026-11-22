"""Move a project to a release of iglootools/common, through a pull request."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from iglootools.common import pins
from iglootools.github import local, merge, pulls
from iglootools.github.client import GitHub, Repository, Run, capture


@dataclass(frozen=True)
class Plan:
    version: str
    sha: str
    files: dict[Path, pins.Rewrite]

    @property
    def changed(self) -> bool:
        return bool(self.files)


def plan(root: Path, github: GitHub, version: str) -> Plan:
    """Every file under *root* whose pins on common would move to *version*."""
    sha = pins.tag_commit(github, version)
    files = {
        path: rewritten
        for path in pins.candidate_files(root)
        for rewritten in [pins.rewrite(path.read_text(encoding="utf-8"), version, sha)]
        if rewritten.text != path.read_text(encoding="utf-8")
    }
    return Plan(version, sha, files)


def steps(root: Path, found: Plan, *, merge_it: bool) -> list[str]:
    """What adopt would do with *found*, after moving the pins, one step per line."""
    branch = f"chore/iglootools-{found.version}"
    return [
        f"Would create {branch} from the default branch, up to date.",
        *(["Would regenerate uv.lock."] if (root / "uv.lock").is_file() else []),
        f"Would commit and push: chore: move to iglootools {found.version}.",
        "Would open a pull request into the default branch.",
        "Would merge it once every check has passed, then delete the branch."
        if merge_it
        else "Would stop there (--no-merge).",
    ]


def commit_message(version: str) -> str:
    return (
        f"chore: move to iglootools {version}\n\n"
        "Every pin on iglootools/common moves to the release: the reusable workflows,\n"
        "the Renovate presets and the iglootools command."
    )


@dataclass(frozen=True)
class Outcome:
    pull_number: int | None
    merged: bool
    reason: str


def adopt(
    root: Path,
    github: GitHub,
    repository: Repository,
    found: Plan,
    *,
    merge_it: bool,
    report: Callable[[str], None],
    sleep: Callable[[float], None],
    now: Callable[[], float],
    run: Run = capture,
) -> Outcome:
    """Open a pull request moving *root* to *found*'s version, and merge it when green."""
    base = pulls.default_branch(github, repository)
    branch = f"chore/iglootools-{found.version}"
    local.start_branch(root, base, branch, run=run)
    for path, rewritten in found.files.items():
        path.write_text(rewritten.text, encoding="utf-8")
    paths = [str(path.relative_to(root)) for path in found.files]
    if (root / "uv.lock").is_file():
        report("Updating uv.lock")
        result = run(
            ["mise", "exec", "--", "uv", "lock", "--upgrade-package", "iglootools"],
            root,
        )
        if result.returncode != 0:
            raise local.GitStepError(f"uv lock: {result.stderr.strip()}")
        paths.append("uv.lock")
    local.commit_and_push(root, paths, commit_message(found.version), branch, run=run)
    number = pulls.open_pull(
        github,
        repository,
        head=branch,
        base=base,
        title=f"chore: move to iglootools {found.version}",
        body=f"Moves every pin on iglootools/common to {found.version}.",
    )
    report(f"Opened {repository.slug}#{number}")
    if not merge_it:
        return Outcome(number, False, "opened, not merged (--no-merge)")
    outcome = merge.merge_when_green(
        github, repository, number, sleep=sleep, now=now, report=report
    )
    if outcome.merged and outcome.branch_deleted:
        local.clean_local(root, branch, base, run=run)
    return Outcome(number, outcome.merged, outcome.reason)

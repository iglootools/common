"""
Cut a release of iglootools/common, as docs/releasing-and-publishing.md describes.

The version bump goes through a pull request merged once green, like any change. Only
then are the two tags made, on the merge commit: `iglootools--v<version>`, which `claude
plugin tag` creates and the plugin installs by, and the plain `v<version>`, which
projects pin the workflows, presets and command by. Both must name the same commit, and
the release checks that they do.
"""

import base64
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from http import HTTPStatus
from pathlib import Path

from iglootools.common.pins import COMMON, VERSION
from iglootools.github import events, local, merge, pulls
from iglootools.github.client import GitHub, GitHubError, Repository, Run, capture

PLUGIN_JSON = Path(".claude-plugin") / "plugin.json"
_VERSION_FIELD = re.compile(r'("version"\s*:\s*")[^"]*(")')


def version_tuple(version: str) -> tuple[int, ...]:
    """Return an X.Y.Z *version* as integers, which compare in release order."""
    return tuple(int(part) for part in version.split("."))


class VersionFieldError(ValueError):
    """plugin.json has no version field to bump."""

    def __init__(self) -> None:
        """Build the error; it has no fields."""
        super().__init__("plugin.json has no version field")


class WrongRepositoryError(ValueError):
    """A release was started in a repository other than iglootools/common."""

    def __init__(self, repository: Repository) -> None:
        """Build the error from the repository the release was started in."""
        super().__init__(f"releases are cut in {COMMON.slug}, not {repository.slug}")
        self.repository = repository


class TagMismatchError(RuntimeError):
    """The plain tag and the plugin tag name different commits."""

    def __init__(self, plain_tag: str, plugin_tag: str) -> None:
        """Build the error from the two tags' names."""
        super().__init__(f"{plain_tag} and {plugin_tag} name different commits")
        self.plain_tag = plain_tag
        self.plugin_tag = plugin_tag


def bump(text: str, version: str) -> str:
    """
    Set the version in plugin.json's *text* to *version*, leaving the rest untouched.

    Raises VersionFieldError when *text* has no version field.
    """
    bumped, count = _VERSION_FIELD.subn(rf"\g<1>{version}\g<2>", text, count=1)
    if count != 1:
        raise VersionFieldError
    return bumped


class Stage(StrEnum):
    """A step of a release: the version bump, then each of the two tags."""

    BUMP = "bump"
    PLUGIN_TAG = "plugin-tag"
    PLAIN_TAG = "plain-tag"


@dataclass(frozen=True)
class Plan:
    """What a release still has to do, from what GitHub already has."""

    stages: tuple[Stage, ...]
    reason: str
    problem: str | None = None


FULL = (Stage.BUMP, Stage.PLUGIN_TAG, Stage.PLAIN_TAG)


def plan(current: str, version: str, *, plugin_tag: bool, plain_tag: bool) -> Plan:
    """
    Plan the stages left to release *version*.

    *current* is the default branch's plugin.json version, *plugin_tag* and *plain_tag*
    whether `iglootools--v<version>` and `v<version>` exist.

    A release that stopped half way is resumed rather than refused, and one that is
    complete changes nothing. Tags that disagree with plugin.json are left to a person.
    """
    if not VERSION.match(version):
        return Plan((), "", f"give the version as X.Y.Z, not {version!r}")
    if plugin_tag and plain_tag:
        return Plan((), f"{version} is already released")
    if version_tuple(current) == version_tuple(version):
        if plain_tag:
            return Plan((), "", f"v{version} exists without iglootools--v{version}")
        if plugin_tag:
            return Plan((Stage.PLAIN_TAG,), f"resuming: iglootools--v{version} exists")
        return Plan(
            (Stage.PLUGIN_TAG, Stage.PLAIN_TAG),
            "resuming: the bump has merged",
        )
    if version_tuple(version) < version_tuple(current):
        return Plan((), "", f"{version} is not newer than the current {current}")
    if plugin_tag or plain_tag:
        return Plan(
            (),
            "",
            f"a {version} tag exists, but plugin.json is still {current}",
        )
    return Plan(FULL, f"releasing {version}, after {current}")


def steps(found: Plan, version: str) -> list[str]:
    """List what release would do for *found*, one step per line."""
    lines = {
        Stage.BUMP: [
            (
                f"Would create chore/release-{version} from the default branch, "
                "up to date."
            ),
            (
                f"Would set {PLUGIN_JSON} to {version}, commit, push and open a "
                "pull request."
            ),
            "Would merge it once every check has passed, then delete the branch.",
        ],
        Stage.PLUGIN_TAG: [
            (
                "Would run `claude plugin validate .` and "
                f"`claude plugin tag --push` on the default branch, creating "
                f"iglootools--v{version}."
            ),
        ],
        Stage.PLAIN_TAG: [
            (
                f"Would tag iglootools--v{version}'s commit v{version}, push it, "
                "and check both tags name it."
            ),
        ],
    }
    return [found.reason[0].upper() + found.reason[1:] + "."] + [
        line for stage in found.stages for line in lines[stage]
    ]


def tag_exists(github: GitHub, name: str) -> bool:
    """Tell whether common has the tag *name* on GitHub."""
    try:
        github.get(f"/repos/{COMMON.slug}/git/ref/tags/{name}")
    except GitHubError as error:
        if error.status == HTTPStatus.NOT_FOUND:
            return False
        raise
    return True


def remote_version(github: GitHub, branch: str) -> str:
    """
    Return the plugin.json version on *branch* on GitHub.

    Read from GitHub because a stale checkout may lag it.
    """
    content = github.get(f"/repos/{COMMON.slug}/contents/{PLUGIN_JSON}?ref={branch}")
    return str(json.loads(base64.b64decode(content["content"]))["version"])


def plan_from_github(github: GitHub, version: str) -> Plan:
    """Plan the release of *version* from what common's default branch and tags hold."""
    base = pulls.default_branch(github, COMMON)
    return plan(
        remote_version(github, base),
        version,
        plugin_tag=tag_exists(github, f"iglootools--v{version}"),
        plain_tag=tag_exists(github, f"v{version}"),
    )


@dataclass(frozen=True)
class Outcome:
    """Whether a release completed, why not if not, and its bump's pull request."""

    pull_number: int | None
    released: bool
    reason: str


def release(
    root: Path,
    github: GitHub,
    repository: Repository,
    version: str,
    found: Plan,
    *,
    report: events.Report,
    sleep: Callable[[float], None],
    now: Callable[[], float],
    run: Run = capture,
) -> Outcome:
    """Run *found*'s stages: bump and merge once green, then tag both ways."""
    if repository != COMMON:
        raise WrongRepositoryError(repository)
    base = pulls.default_branch(github, repository)
    number: int | None = None
    if Stage.BUMP in found.stages:
        branch = f"chore/release-{version}"
        local.start_branch(root, base, branch, run=run)
        plugin_json = root / PLUGIN_JSON
        plugin_json.write_text(
            bump(plugin_json.read_text(encoding="utf-8"), version),
            encoding="utf-8",
        )
        local.commit_and_push(
            root,
            [str(PLUGIN_JSON)],
            f"chore: release {version}",
            branch,
            run=run,
        )
        number = pulls.open_pull(
            github,
            repository,
            head=branch,
            base=base,
            title=f"chore: release {version}",
            body=f"Release {version}.",
        )
        report(
            events.Event(
                events.Stage.OPENED,
                f"Opened {repository.slug}#{number}",
                number,
            ),
        )
        merged = merge.merge_when_green(
            github,
            repository,
            number,
            sleep=sleep,
            now=now,
            report=report,
        )
        if not merged.merged:
            return Outcome(number, released=False, reason=merged.reason)
        local.clean_local(root, branch, base, run=run)
    else:
        local.sync(root, base, run=run)
    if Stage.PLUGIN_TAG in found.stages:
        plugin_tag(root, run=run)
    if Stage.PLAIN_TAG in found.stages:
        plain_tag(root, version, report=report, run=run)
    return Outcome(number, released=True, reason=f"released {version}")


def plugin_tag(root: Path, *, run: Run) -> None:
    """
    Validate the plugin and tag it with `claude plugin tag --push`, in *root*.

    Raises GitStepError with claude's message when either command fails.
    """
    for command in (
        ["claude", "plugin", "validate", "."],
        ["claude", "plugin", "tag", "--push", "-m", "Release %s"],
    ):
        result = run(command, root)
        if result.returncode != 0:
            raise local.GitStepError(
                local.GitStepFailureKind.COMMAND_FAILED,
                command,
                result.stderr.strip() or result.stdout.strip(),
            )


def plain_tag(root: Path, version: str, *, report: events.Report, run: Run) -> None:
    """
    Tag the plugin tag's commit v<version>, push it, and check both name one commit.

    Raises TagMismatchError when they name different commits.
    """
    plugin_tag = f"iglootools--v{version}"
    plain_tag = f"v{version}"
    local.git(root, "fetch", "-q", "--tags", run=run)
    local.git(
        root,
        "tag",
        "-a",
        plain_tag,
        "-m",
        f"Release {version}",
        f"{plugin_tag}^{{}}",
        run=run,
    )
    local.git(root, "push", "-q", "origin", plain_tag, run=run)
    commits = {
        local.git(root, "rev-parse", ref, run=run).strip()
        for ref in (f"{plain_tag}^{{}}", f"{plugin_tag}^{{}}")
    }
    if len(commits) != 1:
        raise TagMismatchError(plain_tag, plugin_tag)
    report(events.Event(events.Stage.TAGGED, f"Tagged {plugin_tag} and {plain_tag}"))

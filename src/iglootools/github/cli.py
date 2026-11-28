"""The `iglootools github` commands: merging, pruning, linting and workflow steps."""

import os
import shutil
import time
from pathlib import Path
from typing import Annotated

import typer

from iglootools.cliwiring import display_path, ensure, invocation, say, warn
from iglootools.github import linkreport, lint, local, merge, prune, releasetag
from iglootools.github.actions import AnnotationLevel, append_outputs, format_annotation
from iglootools.github.client import (
    GitHub,
    GitHubError,
    Repository,
    origin_repository,
    parse_slug,
    resolve_token,
)
from iglootools.preflight import requirements

app = typer.Typer(
    help="Work with the project's GitHub repository.",
    no_args_is_help=True,
)

REPO_OPTION = typer.Option(
    "--repo",
    help="owner/name of the repository; default: the origin remote.",
)


def _repository(ctx: typer.Context, slug: str | None) -> Repository:
    if slug is not None:
        match parse_slug(slug):
            case None:
                warn(f"--repo takes owner/name, not {slug!r}.")
                raise typer.Exit(2)
            case repository:
                return repository
    try:
        return origin_repository(invocation(ctx).root)
    except GitHubError as error:
        warn(f"{error.detail}.")
        raise typer.Exit(2) from None


def _preview_merge(
    github: GitHub,
    repository: Repository,
    pr: int,
    *,
    delete_branch: bool,
) -> None:
    try:
        found = merge.preview(github, repository, pr)
    except GitHubError as error:
        warn(f"{repository.slug}#{pr}: {error.detail}")
        raise typer.Exit(1) from None
    for line in merge.describe(found, delete_branch=delete_branch):
        say(f"[dry-run] {repository.slug}#{pr}: {line}")
    if found.verdict.action == merge.Action.REFUSE:
        raise typer.Exit(1)


def _is_origin(ctx: typer.Context, repository: Repository) -> bool:
    """Whether the checkout under --root is a clone of *repository*."""
    try:
        return origin_repository(invocation(ctx).root) == repository
    except GitHubError:
        return False


def github_session(ctx: typer.Context, slug: str | None) -> tuple[Repository, GitHub]:
    """
    Return the repository to work on and an authenticated client.

    Exits 2, saying why, when either cannot be had.
    """
    return _repository(ctx, slug), github_client(ctx)


def github_client(ctx: typer.Context) -> GitHub:
    """Return a GitHub client with the user's token; exit 2 when there is none."""
    try:
        return GitHub(resolve_token(invocation(ctx).root, environ=os.environ))
    except GitHubError as error:
        warn(f"No GitHub token: {error.detail}.")
        raise typer.Exit(2) from None


@app.command("merge-when-green")
def merge_when_green(
    ctx: typer.Context,
    pr: Annotated[int, typer.Argument(help="Number of the pull request.", min=1)],
    repo: Annotated[str | None, REPO_OPTION] = None,
    timeout: Annotated[
        int,
        typer.Option(help="Give up after this many seconds.", min=1),
    ] = 1800,
    *,
    keep_branch: Annotated[
        bool,
        typer.Option("--keep-branch", help="Do not delete the branch."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Say what it would do, and stop."),
    ] = False,
) -> None:
    """
    Merge a pull request once every check has passed, then delete its branch.

    Waits until every check on the head commit has reported, including the ones a
    ruleset requires that have not started yet. Refuses when a check fails or GitHub
    blocks the merge for another reason. Merges with a merge commit, deletes the branch
    on GitHub, and, when the checkout has it, locally too.
    """
    ensure(ctx, requirements.GITHUB)
    repository = _repository(ctx, repo)
    github = github_client(ctx)
    if dry_run:
        _preview_merge(github, repository, pr, delete_branch=not keep_branch)
        return
    try:
        outcome = merge.merge_when_green(
            github,
            repository,
            pr,
            sleep=time.sleep,
            now=time.monotonic,
            report=lambda event: say(f"{repository.slug}#{pr}: {event.detail}"),
            timeout=timeout,
            delete_branch=not keep_branch,
        )
    except GitHubError as error:
        warn(f"{repository.slug}#{pr}: {error.detail}")
        raise typer.Exit(1) from None
    if not outcome.merged:
        warn(f"{repository.slug}#{pr}: not merged, {outcome.reason}.")
        raise typer.Exit(1)
    say(f"{repository.slug}#{pr}: {outcome.reason}.")
    if outcome.branch_deleted:
        say(f"Deleted {outcome.pull.head_ref} on GitHub.")
    if outcome.branch_deleted and _is_origin(ctx, repository):
        cleanup = local.clean_local(
            invocation(ctx).root,
            outcome.pull.head_ref,
            outcome.pull.base_ref,
        )
        if cleanup.switched_to_base:
            say(f"Switched to an up-to-date {outcome.pull.base_ref}.")
        if cleanup.deleted:
            say(f"Deleted the local {outcome.pull.head_ref}.")
        if cleanup.problem:
            warn(f"Local cleanup stopped: {cleanup.problem}")


@app.command("prune-branches")
def prune_branches(
    ctx: typer.Context,
    repo: Annotated[str | None, REPO_OPTION] = None,
    *,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Show what would be deleted."),
    ] = False,
) -> None:
    """
    Delete every branch whose latest pull request has merged, on GitHub and locally.

    Keeps the default branch, protected branches, branches with an open pull request,
    branches whose latest pull request was closed without merging, and branches that
    never had one, such as gh-pages. Local branches are deleted with `git branch -d`, so
    one carrying commits the default branch lacks is kept and reported.
    """
    ensure(ctx, requirements.GITHUB)
    repository = _repository(ctx, repo)
    github = github_client(ctx)
    root = invocation(ctx).root
    on_origin = _is_origin(ctx, repository)
    locals_ = local.local_branches(root) if on_origin else []
    try:
        default_branch, branches = prune.gather(github, repository, locals_)
        decisions = prune.plan(branches, default_branch)
        for decision in decisions:
            name = decision.branch.name
            if not decision.delete:
                say(f"Keep {name}: {decision.reason}.")
                continue
            if dry_run:
                say(f"[dry-run] Would delete {name}: {decision.reason}.")
                continue
            if decision.branch.on_remote:
                prune.delete_remote(github, repository, name)
            if decision.branch.local:
                cleanup = local.clean_local(root, name, default_branch)
                if cleanup.problem:
                    warn(f"Kept the local {name}: {cleanup.problem}")
                    continue
            say(f"Deleted {name}: {decision.reason}.")
    except GitHubError as error:
        warn(f"{repository.slug}: {error.detail}")
        raise typer.Exit(1) from None


GITHUB_OUTPUT_OPTION = typer.Option(
    "--github-output",
    envvar="GITHUB_OUTPUT",
    help="Step output file to append to; default: $GITHUB_OUTPUT.",
)


def _annotate(level: AnnotationLevel, message: str) -> None:
    say(format_annotation(level, message))


def _outputs(path: Path | None, values: dict[str, str]) -> None:
    if path is not None:
        append_outputs(path, values)


@app.command("checkout-release")
def checkout_release_cmd(
    ctx: typer.Context,
    tag: Annotated[
        str,
        typer.Option(
            help="Release tag to check out, such as v1.2.0; empty: the v* tag on HEAD.",
        ),
    ] = "",
    event: Annotated[
        str,
        typer.Option(
            envvar="GITHUB_EVENT_NAME",
            help="Event that started the run; default: $GITHUB_EVENT_NAME.",
        ),
    ] = "",
    github_output: Annotated[Path | None, GITHUB_OUTPUT_OPTION] = None,
    *,
    allow_untagged: Annotated[
        bool,
        typer.Option(
            "--allow-untagged",
            help="Build HEAD when there is no tag, rather than failing.",
        ),
    ] = False,
) -> None:
    """
    Check out the release a workflow run builds: the tag asked for, or the one on HEAD.

    For the jobs a release starts (publish, demo, a site deploy), right after
    actions/checkout. With no tag anywhere, a workflow_run sets the `skip` output, since
    the release run released nothing; any other run fails, unless --allow-untagged.
    Refuses a tag not shaped v<digit>… or that the repository does not have. Sets the
    `skip` and `tag` step outputs.
    """
    ensure(ctx, (requirements.GIT,))
    root = invocation(ctx).root
    plan = releasetag.plan_checkout(
        requested=tag,
        head_tag=releasetag.head_release_tag(root),
        event=event,
        allow_untagged=allow_untagged,
    )
    head = releasetag.short_head(root)
    match plan.action:
        case releasetag.CheckoutAction.SKIP:
            _annotate(
                AnnotationLevel.NOTICE,
                f"{head} carries no v* tag, so the release run did not release. "
                "Nothing to do.",
            )
            _outputs(github_output, {"skip": "true", "tag": ""})
        case releasetag.CheckoutAction.USE_HEAD:
            _annotate(
                AnnotationLevel.NOTICE,
                f"{head} carries no v* tag; building the branch head as dispatched.",
            )
            _outputs(github_output, {"skip": "false", "tag": ""})
        case releasetag.CheckoutAction.REFUSE:
            _annotate(
                AnnotationLevel.ERROR,
                f"{head} carries no v* tag. "
                "Dispatch with -f tag=vX.Y.Z, or --ref vX.Y.Z.",
            )
            raise typer.Exit(1)
        case releasetag.CheckoutAction.CHECKOUT:
            _checkout_release(root, plan.tag)
            _outputs(github_output, {"skip": "false", "tag": plan.tag})


def _checkout_release(root: Path, tag: str) -> None:
    if not releasetag.is_release_tag(root, tag):
        _annotate(
            AnnotationLevel.ERROR,
            f"{tag} is not a release tag of this repository.",
        )
        raise typer.Exit(1)
    try:
        releasetag.checkout_tag(root, tag)
    except releasetag.CheckoutError as error:
        _annotate(AnnotationLevel.ERROR, f"Could not check out {tag}: {error.detail}")
        raise typer.Exit(1) from None
    say(f"Checked out {tag} ({releasetag.short_head(root)}).")


def _run_url(environ: dict[str, str]) -> str:
    """Return the run's page, from the variables every Actions run sets, or empty."""
    parts = [environ.get(name, "") for name in _RUN_VARIABLES]
    return "{}/{}/actions/runs/{}".format(*parts) if all(parts) else ""


_RUN_VARIABLES = ("GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "GITHUB_RUN_ID")


def _read_report(path: Path, root: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as error:
        warn(f"{display_path(path, root)} exists but cannot be read: {error}")
        raise typer.Exit(1) from None


@app.command("link-report")
def link_report_cmd(
    ctx: typer.Context,
    *,
    report: Annotated[
        Path,
        typer.Option(help="lychee's Markdown report."),
    ] = Path("lychee/out.md"),
    title: Annotated[
        str,
        typer.Option(help="Title of the issue that reports broken links."),
    ] = "Link Checker Report",
    labels: Annotated[
        str,
        typer.Option(help="Comma-separated labels for that issue."),
    ] = "report, automated issue",
    repo: Annotated[
        str | None,
        typer.Option(
            "--repo",
            envvar="GITHUB_REPOSITORY",
            help="owner/name of the repository; default: $GITHUB_REPOSITORY, "
            "else the origin remote.",
        ),
    ] = None,
    run_url: Annotated[
        str | None,
        typer.Option(help="The run to link to; default: the current Actions run."),
    ] = None,
) -> None:
    """
    Keep one issue reporting broken links, from a lychee report.

    Files the issue when links are broken, or updates the open one, and closes it once
    none are. Fails, showing the report, when lychee did not complete a run, rather than
    filing an empty issue. Run by the shared link checker, reusable-check-links.yml.
    """
    root = invocation(ctx).root
    path = report if report.is_absolute() else root / report
    text = _read_report(path, root)
    outcome = linkreport.classify_report(text)
    if outcome == linkreport.LinkCheckOutcome.NOT_RAN:
        _annotate(
            AnnotationLevel.ERROR,
            f"lychee did not complete a run: {display_path(path, root)} has no "
            "summary. Check the arguments in reusable-check-links.yml.",
        )
        say(text if text is not None else "(no report)")
        raise typer.Exit(1)
    ensure(ctx, requirements.GITHUB)
    repository, github = github_session(ctx, repo)
    url = run_url if run_url is not None else _run_url(dict(os.environ))
    issue = linkreport.ReportIssue(
        repository,
        title,
        [label.strip() for label in labels.split(",") if label.strip()],
    )
    try:
        _act_on_report(
            github,
            issue,
            outcome,
            linkreport.fit_body(text or "", url),
            url,
        )
    except GitHubError as error:
        warn(f"{repository.slug}: {error.detail}")
        raise typer.Exit(1) from None


def _act_on_report(
    github: GitHub,
    issue: linkreport.ReportIssue,
    outcome: linkreport.LinkCheckOutcome,
    body: str,
    run_url: str,
) -> None:
    open_report = linkreport.find_open_report(github, issue)
    action = linkreport.plan_report(
        broken=outcome == linkreport.LinkCheckOutcome.BROKEN,
        open_report=open_report,
    )
    slug = issue.repository.slug
    match (action, open_report):
        case (linkreport.ReportAction.CREATE, _):
            number = linkreport.file_report(github, issue, body)
            say(f"Broken links: filed {slug}#{number}.")
        case (linkreport.ReportAction.UPDATE, int() as number):
            linkreport.update_report(github, issue, number, body)
            say(f"Broken links: updated {slug}#{number}.")
        case (linkreport.ReportAction.CLOSE, int() as number):
            linkreport.close_report(github, issue, number, run_url)
            say(f"No broken links: closed {slug}#{number}.")
        case _:
            say("No broken links, and no open report.")


@app.command("lint")
def lint_cmd(ctx: typer.Context) -> None:
    """
    Run actionlint on every tracked workflow, with shellcheck on each run: script.

    Lints the .yml and .yaml files under .github/workflows/. Fails when shellcheck is
    missing rather than skipping it, as actionlint alone would.
    """
    root = invocation(ctx).root
    workflows = lint.workflow_files(root)
    if not workflows:
        say(f"No workflows to lint under {lint.WORKFLOWS_DIR}.")
        return
    shellcheck = shutil.which("shellcheck")
    if shellcheck is None:
        warn('shellcheck not found. Pin it in mise.toml: shellcheck = "0.11.0".')
        raise typer.Exit(1)
    say(f"Linting {len(workflows)} workflow(s) with actionlint")
    try:
        status = lint.run_in(lint.actionlint_command(workflows, shellcheck), root)
    except FileNotFoundError:
        warn('actionlint not found. Pin it in mise.toml: actionlint = "1.7.12".')
        raise typer.Exit(1) from None
    if status != 0:
        raise typer.Exit(status)

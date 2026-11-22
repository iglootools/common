# GitHub Workflow Guidelines

The rules every file under `.github/workflows/` follows. Read it before adding
or editing a workflow. The workflows every project calls from this repository
are in [shared-workflows.md](shared-workflows.md), releasing to PyPI is in
[pypi-publishing.md](pypi-publishing.md), and Renovate and Dependabot are in
[dependency-automation.md](dependency-automation.md).

<!-- toc -->
**On this page**

- [Structure](#structure)
  - [Keep workflows thin: set up the toolchain, then run one `ci-*` task](#keep-workflows-thin-set-up-the-toolchain-then-run-one-ci--task)
  - [Name every workflow after its own file](#name-every-workflow-after-its-own-file)
  - [Name each job after the task it runs, without `ci-`](#name-each-job-after-the-task-it-runs-without-ci-)
- [Security](#security)
  - [Declare `permissions` on every job, at least privilege](#declare-permissions-on-every-job-at-least-privilege)
  - [Pin every action to a commit SHA, with the tag in a trailing comment](#pin-every-action-to-a-commit-sha-with-the-tag-in-a-trailing-comment)
- [Toolchain](#toolchain)
  - [Pin the mise version in every `jdx/mise-action` step, under a `# renovate:` marker](#pin-the-mise-version-in-every-jdxmise-action-step-under-a--renovate-marker)
  - [Prefer tools whose mise backend is lockable](#prefer-tools-whose-mise-backend-is-lockable)
  - [Pair `install: false` with `env: false`](#pair-install-false-with-env-false)
- [Running](#running)
  - [Supersede runs that can be redone, but never a push to `main`](#supersede-runs-that-can-be-redone-but-never-a-push-to-main)
  - [Queue runs whose partial state cannot be redone](#queue-runs-whose-partial-state-cannot-be-redone)
  - [Build what a release triggers from its tag](#build-what-a-release-triggers-from-its-tag)
  - [Set `timeout-minutes` on every job](#set-timeout-minutes-on-every-job)
  - [Allow manual dispatch, except where it reaches production](#allow-manual-dispatch-except-where-it-reaches-production)
- [Rationale](#rationale)
  - [Name every workflow after its own file](#name-every-workflow-after-its-own-file-1)
  - [Pin every action to a commit SHA, with the tag in a trailing comment](#pin-every-action-to-a-commit-sha-with-the-tag-in-a-trailing-comment-1)
  - [Queue runs whose partial state cannot be redone](#queue-runs-whose-partial-state-cannot-be-redone-1)
<!-- tocstop -->

## Structure

### Keep workflows thin: set up the toolchain, then run one `ci-*` task

Build, check, test, package and demo logic lives in mise tasks, or in scripts
those tasks run. A job checks out, sets up mise, and runs a single
`mise run ci-<purpose>`.

**Why:** an inline `run:` line only runs on a runner, so reproducing a failure
means retyping YAML, and the next workflow that needs it copies it. A task runs
locally with the same command, and every workflow shares one definition.

```yaml
steps:
  - uses: actions/checkout@<sha> # v7
  - uses: jdx/mise-action@<sha> # v5
    with:
      # renovate: datasource=github-releases depName=jdx/mise
      version: <version>
  - run: mise run ci-preflight
```

- The YAML keeps only what exists in GitHub Actions alone: triggers,
  permissions, concurrency, environments and secrets, OIDC, `timeout-minutes`,
  steps that are actions (checkout, `pypa/gh-action-pypi-publish`,
  `actions/upload-artifact`), packages only the runner image lacks, and steps
  that make sense only in CI, such as synthesizing a throwaway Test PyPI
  version.
- The test for anything else: if it would make sense on a developer's machine,
  it belongs in a task.
- A `ci-*` task chains ordinary tasks and adds no logic of its own, as
  [mise.md › Give each workflow job one `ci-*` task](mise.md#give-each-workflow-job-one-ci--task)
  describes.

### Name every workflow after its own file

`name:` is the filename's stem, verbatim: `name: preflight` in `preflight.yml`,
`name: renovate-mise-lock` in `renovate-mise-lock.yml`.

**Why:** GitHub addresses a workflow by filename in some places and by name in
others, and two workflows sharing a name share a concurrency group and cancel
each other. [Rationale](#name-every-workflow-after-its-own-file-1)

- By filename: the status-badge URL, the REST `/actions/workflows/{file}`
  endpoint, `gh workflow run`, and the workflow PyPI's trusted publisher names.
- By name: the Actions UI, the `workflows:` list of a `workflow_run` trigger,
  and `${{ github.workflow }}`.

### Name each job after the task it runs, without `ci-`

The job that runs `ci-preflight` is `preflight`; the one that runs `ci-build` is
`build`.

**Why:** a failing check in a pull request then names the command that
reproduces it: `mise run preflight`.

- Where a workflow splits `preflight` across parallel jobs, each job takes its
  own task's name (`preflight-quick`, `test-docker`), and the job that waits on
  all of them, failing unless they all passed, is `preflight`.
- The workflow that runs on every pull request is `preflight.yml`, with
  `name: preflight`, holding the `preflight` job. Nothing is called `test`, `ci`
  or `check` that runs more than tests, CI plumbing or one check.
- The job name is the check name a ruleset requires, so renaming a required job
  changes the ruleset too, in the order
  [repository.md › Protect the default branch and release tags](repository.md#protect-the-default-branch-and-release-tags)
  gives.

## Security

### Declare `permissions` on every job, at least privilege

Every job carries a `permissions` block listing only what it uses. Comment each
`write` with what the job writes.

**Why:** a job without one inherits the repository's default token permissions,
read-write in older repositories and read-only in new organizations, so the same
workflow fails in one repository or quietly holds write access in the next.

```yaml
jobs:
  preflight:
    permissions:
      contents: read
```

- A block replaces the default completely: every scope it omits is set to none.
  A job that declares `id-token: write` to publish also needs `contents: read`
  to check out.
- Declare `contents: read` even where it seems to work without it.
  `actions/checkout` needs it only in a private repository: a public one falls
  back to an anonymous clone. A workflow verified in a public repository passes
  without it and then fails in a private one with
  `fatal: repository not found`.
- A called workflow's `permissions` is only a ceiling, as
  [shared-workflows.md › Declare permissions in the caller](shared-workflows.md#declare-permissions-in-the-caller)
  describes.

### Pin every action to a commit SHA, with the tag in a trailing comment

```yaml
- uses: actions/checkout@<sha> # v7
```

**Why:** a tag or branch can be repointed at new code that every workflow then
runs with no diff to review. The trailing comment is what Renovate reads to
update the pin.
[Rationale](#pin-every-action-to-a-commit-sha-with-the-tag-in-a-trailing-comment-1)

- A branch ref such as `pypa/gh-action-pypi-publish@release/v1` is pinned too,
  with the branch name as the comment.
- The shared Renovate preset, [renovate/base.json](../../renovate/base.json),
  pins newly added actions and keeps undatable digest updates from freezing.
  Extend it as
  [dependency-automation.md › Extend the shared Renovate presets](dependency-automation.md#extend-the-shared-renovate-presets)
  describes, rather than configuring either by hand.

## Toolchain

### Pin the mise version in every `jdx/mise-action` step, under a `# renovate:` marker

Set `version:` to the version `[tools]` was locked with locally, directly under
the marker comment:

```yaml
- uses: jdx/mise-action@<sha> # v5
  with:
    # renovate: datasource=github-releases depName=jdx/mise
    version: <version>
```

**Why:** without `version:` the action installs the latest mise, so the
toolchain resolver changes on whatever night mise ships, and `mise.lock` cannot
cover the binary that reads it. The marker is the pin's updater: Renovate's
`github-actions` manager reads no action inputs.

- The custom manager in [renovate/base.json](../../renovate/base.json) matches
  the marker followed by a literal `version:` line. A bare `version:` is the pin
  nothing updates that
  [general.md › Version Management](../coding/general.md#version-management)
  warns about.

### Prefer tools whose mise backend is lockable

Check with `mise registry <tool>`: a backend such as `aqua:` records
per-platform URLs and checksums in `mise.lock`, while `vfox:` records none and
`mise lock` cannot generate them.

**Why:** an unlockable tool makes `mise install --locked` fail on a fresh
runner, which forces `install: false` into every workflow and gives up checksum
and attestation verification for all tools to accommodate one.

- The one legitimate `install: false` is a workflow that runs where `mise.toml`
  is deliberately ahead of `mise.lock`: the
  [lock regenerator](shared-workflows.md#call-the-shared-lock-regenerator-on-renovate-branches)
  on Renovate branches.

### Pair `install: false` with `env: false`

A `jdx/mise-action` step that skips the install also skips exporting mise's
environment.

**Why:** after setup, `jdx/mise-action` exports mise's `[env]`, and a template
that resolves through the installed toolset, such as the `UV_PYTHON` pin
[python-tooling.md](python-tooling.md#pin-uv-to-mises-interpreter-by-absolute-path)
requires, fails with ``Field `python` is not defined`` when nothing is
installed, taking the setup step down.

- A project with no `{{ tools.* }}` template works without `env: false`, which
  is how the pairing gets dropped from a copy and stays latent until someone
  adds one.
- Nothing is lost: a workflow that skips the install needs the mise binary and
  the config, not a tool environment. A step that needs one variable restates
  it.

## Running

### Supersede runs that can be redone, but never a push to `main`

Every workflow has a concurrency group. A workflow whose half-finished run a
later run can redo from scratch uses this group, which cancels the run in flight
for a pull request or tag and gives every commit on `main` its own:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref == 'refs/heads/main' && format('main-{0}', github.event.workflow_run.head_sha || github.sha) || github.ref }}
  cancel-in-progress: true
```

**Why:** a superseded run costs only the compute already spent, and a per-commit
group on `main` means every commit there still gets a complete run.

- It covers anything that only reads and reports (preflight, lint, link check,
  build) and anything that writes somewhere a later run overwrites wholesale: a
  container tag, a docs site, a preview environment rebuilt on every deploy.
- `github.event.workflow_run.head_sha` comes before `github.sha` because, for a
  `workflow_run` event, `github.sha` is the default branch's head, not the
  triggering commit. Keyed on it, every `workflow_run` run lands in one group
  and cancels the one already going. The term is inert elsewhere, so use the
  expression verbatim everywhere.
- `actionlint` does not catch a misspelled `github.event.*` property: it exits 0
  on `github.event.workflow_run.head_shaa`. Check property names against the
  workflow-run object in the REST API.
- Interpolate `github.workflow` once, outside the `format()`. Inside it as well,
  the group reads `preflight-preflight-main-…`, which is hard to recognise in
  the API.
- A workflow that only runs on branches may key on the ref alone, as the lock
  regenerator's caller does (`renovate-mise-lock-${{ github.ref }}` with
  `cancel-in-progress: true`): one run per branch, the newest push winning.

### Queue runs whose partial state cannot be redone

When a run killed partway leaves state that no later run can redo, such as
publishing to PyPI, deploying to production, or creating tags and releases,
queue instead:

```yaml
concurrency:
  group: ${{ github.workflow }}
  cancel-in-progress: false
```

**Why:** PyPI files are immutable, so a publish cancelled between two uploads
leaves that version permanently half-populated, and the only way out is a new
version number. [Rationale](#queue-runs-whose-partial-state-cannot-be-redone-1)

- The test is whether the write can be replayed, not whether it is external.
- The key carries no ref or sha, so runs aimed at the same version from
  different triggers (a tag push, `workflow_run`, a manual dispatch) cannot
  overlap.
- GitHub keeps at most one run pending per group: a third arrival replaces the
  pending run, never the running one.
- A GitHub Pages deployment keeps the fixed `group: pages`, the documented
  convention for that action.

### Build what a release triggers from its tag

A job that a release starts (publish, demo, a site deploy) resolves the
release's `v*` tag and checks it out, right after `actions/checkout`: the tag a
dispatch names, otherwise the `v*` tag on the commit the run started on. nbkp's
[publish.yml](https://github.com/iglootools/nbkp/blob/main/.github/workflows/publish.yml)
shows the step.

**Why:** a run dispatched on a branch otherwise builds that branch's head, which
moves on with every merge, so a re-run publishes whatever `main` has become
under the release's name. Passing the tag as `--ref` avoids it only where the
job may run from a tag: an environment that accepts only `main`, as a GitHub
Pages deployment usually does, refuses that run.

- **Where the tag comes from.** A `tag` input on `workflow_dispatch`
  (`gh workflow run publish.yml -f tag=v1.2.0`), or `client_payload.tag` for
  `repository_dispatch`. Without one, the commit the checkout landed on: a
  `workflow_run` checks out the release run's `head_sha`
  ([pypi-publishing.md](pypi-publishing.md#check-out-the-released-commit-with-its-history-and-tags)),
  and a pushed tag or `--ref v1.2.0` checks out the tagged commit.
- **When there is no tag.** A `workflow_run` skips the rest of the job: the
  release run released nothing, as a dry run does. A manual publish or deploy
  fails, saying how to pass the tag. A manual demo records the branch head,
  which is how a change to the demo is tried out.
- **Refuse a tag the repository does not have**, or one not shaped `v<digit>…`,
  before checking it out. Pass the input to the script through `env:`; never
  interpolate `${{ }}` into `run:`, where a crafted value becomes shell.

### Set `timeout-minutes` on every job

Size one job-level timeout to the job (`timeout-minutes: 10` for most), rather
than per-step timeouts.

**Why:** a hung step, such as a stalled `apt-get` or a network call that never
returns, otherwise runs until GitHub's 6-hour default, wasting minutes and
delaying feedback.

### Allow manual dispatch, except where it reaches production

Give every workflow `workflow_dispatch` and `repository_dispatch` triggers,
unless a manual run could affect production.

**Why:** a workflow that can be run on demand, from the Actions UI or
`gh workflow run <file> --ref <branch>`, can be tested and debugged without a
dummy push.

- `publish.yml` keeps `workflow_dispatch` deliberately, to re-run a publish that
  never happened, as
  [pypi-publishing.md](pypi-publishing.md#chain-publish-to-release-with-workflow_run-and-also-listen-for-v-tags)
  describes.

## Rationale

### Name every workflow after its own file

Holding a mapping between file and name in your head is the small cost. Two
failures make it more than tidiness. A workflow with no `name:` gets
`github.workflow` set to its path, so its concurrency group silently changes
shape. Two workflows that share a `name:` share a `github.workflow`, which puts
them in the same concurrency group: with `cancel-in-progress: true` they cancel
each other, for no reason visible in either file. Filenames cannot collide
within a directory, so deriving the name from the file makes that collision
impossible.

### Pin every action to a commit SHA, with the tag in a trailing comment

A tag is a mutable pointer: whoever controls the action's repository can repoint
`v4` at new code, and every workflow that references it runs that code on its
next run. A branch ref is worse, since moving is what a branch is for. A commit
SHA is the only ref that cannot be repointed. The trailing comment is what turns
the pin from frozen into updatable: Renovate reads it to learn which version the
SHA stands for, and proposes the next one.

### Queue runs whose partial state cannot be redone

A deployment cancelled mid-rollout leaves part of the fleet on the new build and
the rest on the old, which no re-run reconstructs, because it cannot know how
far the killed run got. A release cancelled between the tag and the GitHub
release leaves a tag with no release. What these share is that the second
attempt cannot start from a clean slate. Waiting for the run ahead is cheap by
comparison.

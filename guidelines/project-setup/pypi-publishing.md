# PyPI Publishing Guidelines

How an iglootools Python package gets from a commit on `main` to a release on
PyPI: where the version comes from, how `release.yml`, `publish.yml` and
`publish-test.yml` hand off, how PyPI trusts them, and what to do when a publish
fails. Read it before editing one of those workflows or cutting a release by
hand. Every rule here exists because PyPI is append-only: a version number, once
taken, can never be uploaded again, so a mistake costs a version number rather
than a re-run. How the package is built is in
[python-tooling.md](python-tooling.md#build-and-packaging), and the rules every
workflow follows are in [workflows.md](workflows.md).

<!-- toc -->
**On this page**

- [The pipeline](#the-pipeline)
- [Versioning](#versioning)
  - [Derive the version from the git tag, never from `pyproject.toml`](#derive-the-version-from-the-git-tag-never-from-pyprojecttoml)
  - [Let the release workflow pick the bump from conventional commits](#let-the-release-workflow-pick-the-bump-from-conventional-commits)
  - [Pick the bump by hand when the commits undersell the change](#pick-the-bump-by-hand-when-the-commits-undersell-the-change)
- [Publishing](#publishing)
  - [Chain publish to release with `workflow_run`, and also listen for `v*` tags](#chain-publish-to-release-with-workflow_run-and-also-listen-for-v-tags)
  - [Build the release tag, never a branch head](#build-the-release-tag-never-a-branch-head)
  - [Check out the released commit, with its history and tags](#check-out-the-released-commit-with-its-history-and-tags)
  - [Build in CI, and verify before uploading](#build-in-ci-and-verify-before-uploading)
  - [Publish with trusted publishing, never an API token](#publish-with-trusted-publishing-never-an-api-token)
  - [Rehearse on Test PyPI with a throwaway version](#rehearse-on-test-pypi-with-a-throwaway-version)
- [When a publish fails](#when-a-publish-fails)
  - [Rerun a publish that failed before uploading anything](#rerun-a-publish-that-failed-before-uploading-anything)
  - [Verify on the version's own JSON endpoint](#verify-on-the-versions-own-json-endpoint)
<!-- tocstop -->

## The pipeline

| Workflow | Triggered by | Does |
|---|---|---|
| `release.yml` | `gh workflow run release.yml`, on `main` | picks the next version from conventional commits, pushes the `v<version>` tag, creates the GitHub release with the generated changelog |
| `publish.yml` | the `release` run completing (`workflow_run`), a pushed `v*` tag, or `gh workflow run publish.yml --ref <tag>` | builds and verifies the distributions at the tagged commit and uploads them to PyPI |
| `publish-test.yml` | `gh workflow run publish-test.yml` only | the same build and upload, to Test PyPI, under a throwaway version |

The normal release is one command:

```bash
gh workflow run release.yml
gh run list --workflow publish.yml   # then watch the publish it triggers
```

The project records its side of this, the workflows, the commands and the
trusted-publisher configuration, in `docs/releasing-and-publishing.md`, as
[layout.md › Record repository settings as commands in one place](../documentation/layout.md#record-repository-settings-as-commands-in-one-place)
describes.

## Versioning

### Derive the version from the git tag, never from `pyproject.toml`

`pyproject.toml` declares `dynamic = ["version"]`, and
[`uv-dynamic-versioning`](https://github.com/ninoseki/uv-dynamic-versioning)
computes it at build time: a tagged commit builds as `1.4.0`, an untagged one as
`1.4.0.post3.dev0+2a99beb`. The setup is in
[python-tooling.md](python-tooling.md#build-with-hatchling-and-uv-dynamic-versioning).

**Why:** the tag is the release, so there is no version-bump commit to forget,
and the number in the file and the number on PyPI cannot disagree.

- The cost: a build that cannot see the tags succeeds as `0.0.0`, through the
  required `fallback-version`.
  [Build in CI, and verify before uploading](#build-in-ci-and-verify-before-uploading)
  keeps that build from reaching PyPI.

### Let the release workflow pick the bump from conventional commits

`release.yml` calls the shared
[reusable-release.yml](../../.github/workflows/reusable-release.yml)
([shared-workflows.md](shared-workflows.md#call-the-shared-release-workflow)).
It runs
[`mathieudutour/github-tag-action`](https://github.com/mathieudutour/github-tag-action),
which bumps from the commit messages since the previous `v*` tag (`feat:` a
minor, `fix:` a patch, a `!` or a `BREAKING CHANGE:` footer a major), pushes the
tag, and creates the GitHub release with the changelog.

**Why:** the version follows from what the commits say they changed, with no
one deciding it per release.

- **Commit messages are the input, and nothing checks them.** The action's
  `default_bump` is `patch`, so a range of `chore:` and `docs:` commits, or
  messages that are not conventional at all, still releases as a patch.
  Merging with a merge commit
  ([repository.md](repository.md#merge-pull-requests-with-a-merge-commit)) is
  what keeps each branch commit's type visible to the action.
- The caller grants `contents: write`, and the tag ruleset allows creation
  ([repository.md](repository.md#protect-the-default-branch-and-release-tags)),
  so the tag can be pushed with `GITHUB_TOKEN`.
- The tags it creates are lightweight. Any `git describe` that reads them needs
  `--tags`: without it `git describe` sees only annotated tags, and finds none.

### Pick the bump by hand when the commits undersell the change

Commit types describe commits, not releases. A change whose commits are all
`chore:` can still deserve a minor release. Raising `requires-python` is the
recurring case, and it is released as a **minor**: not a patch, and not a major.

**Why:** dropping a Python version breaks no existing install, since an
installer on an older Python keeps resolving the last compatible release, but
users need to find it in the release notes, which a patch does not signal.

Skip `release.yml` and push the tag yourself:

```bash
git fetch origin
git log -1 origin/main                 # the merge commit `preflight` passed on
git tag v<version> origin/main
git push origin v<version>             # triggers publish.yml through `push: tags: v*`
gh release create v<version> --verify-tag --title v<version> --notes-file release-notes.md
```

- **Create the GitHub release by hand: nothing else will.** Nothing fails if you
  forget: PyPI has the version, the Releases page silently stops at the previous
  one, and the next automated changelog starts from your tag, so this release's
  changes are recorded nowhere. Write the notes in the action's shape (a
  `## [<version>](<compare-url>)` heading and a bullet per change), leading with
  what users must act on, such as the new Python requirement.
- **`--verify-tag` makes `gh` refuse to create the tag itself.** Without it, a
  typo in the tag name creates a new tag at the default branch head.
- **Check the commit before pushing.** The tag ruleset forbids moving or
  deleting a `v*` tag, so a tag pushed to the wrong commit stays, and the
  publish it triggers takes the version number with it.
- Use the action's format, `v` followed by the bare version, so the next
  automated release finds it as the previous tag.

## Publishing

### Chain publish to release with `workflow_run`, and also listen for `v*` tags

`publish.yml` listens for both the `release` run completing
(`workflow_run: {workflows: ["release"], types: [completed]}`) and a pushed `v*`
tag, and guards the job against a failed release with
`if: github.event.workflow_run.conclusion == 'success' || github.event_name != 'workflow_run'`,
as nbkp's
[publish.yml](https://github.com/iglootools/nbkp/blob/main/.github/workflows/publish.yml)
does.

**Why:** a tag pushed with `GITHUB_TOKEN` triggers no other workflow, which
GitHub does to prevent loops. A publish that listened only for tags would never
run after an automated release, and nothing would report it.

- Each release takes exactly one path: a tag pushed by the workflow fires no
  `push` event, and a tag pushed by hand runs no `release` workflow.
- The `if:` is required: `workflow_run` with `types: [completed]` fires when
  the release fails too.
- `workflows:` matches the release workflow's `name:`, not its filename, which
  is one more reason to
  [name every workflow after its file](workflows.md#name-every-workflow-after-its-own-file).
- `workflow_dispatch` re-runs a publish that never happened. Pass the tag, as
  `-f tag=v1.4.0` or `--ref v1.4.0`: the run then builds that tag whatever the
  branch head has become, and refuses to start without one, as
  [Build the release tag, never a branch head](#build-the-release-tag-never-a-branch-head)
  describes.
- `release.yml`, `publish.yml` and `publish-test.yml` queue rather than cancel,
  which also covers a manual dispatch that overlaps either path:
  [workflows.md › Queue runs whose partial state cannot be redone](workflows.md#queue-runs-whose-partial-state-cannot-be-redone).

### Build the release tag, never a branch head

Right after the checkout, resolve the release tag and check it out, as
[workflows.md › Build what a release triggers from its tag](workflows.md#build-what-a-release-triggers-from-its-tag)
describes, with a step that sets `skip=true` for a `workflow_run` on an untagged
commit, and `if: steps.release.outputs.skip != 'true'` on every later step, as
nbkp's
[publish.yml](https://github.com/iglootools/nbkp/blob/main/.github/workflows/publish.yml)
does. Declare the input on the trigger:

```yaml
workflow_dispatch:
  inputs:
    tag:
      description: Release tag to publish, such as v1.2.0.
      type: string
      required: false
```

**Why:** a dry run (`dry-run: true`) and a run dispatched on another branch both
complete successfully and push no tag, yet start the publish; and a manual
re-run from `main` would build whatever merged since the release. Either way the
build is a development version such as `1.4.0.post3.dev0+2a99beb`, which
`build-verify` lets through, and only PyPI's refusal of local versions (`+…`)
stands between it and PyPI.

### Check out the released commit, with its history and tags

```yaml
- uses: actions/checkout@<sha> # v7
  with:
    fetch-depth: 0
    fetch-tags: true
    ref: ${{ github.event.workflow_run.head_sha || github.sha }}
```

**Why:** the default checkout, and the default ref under `workflow_run`, both
build something other than the tagged version.

- **`fetch-depth: 0` and `fetch-tags: true`.** The default checkout is a single
  commit with no tags, which builds as `0.0.0`
  ([python-tooling.md](python-tooling.md#guard-against-a-000-release)).
- **`ref: github.event.workflow_run.head_sha`.** Under `workflow_run`,
  `github.sha` is the current head of the default branch, not the commit the
  release tagged. If anything merged in between, the publish would build a
  development version. The `|| github.sha` fallback covers the other triggers: a
  pushed tag or `--ref v1.4.0` lands on the tagged commit, and for a dispatch
  from a branch the next step checks out the tag it names.

### Build in CI, and verify before uploading

The job's work is one task, and the upload is the step after it:

```yaml
- run: mise run ci-build      # install, build, build-verify
- uses: pypa/gh-action-pypi-publish@<sha> # release/v1
```

**Why:** the upload publishes whatever is in `dist/`, so the build has to be
clean and checked in the same job.

- **`build` empties `dist/` first.** `uv build` does not clear it, and a stale
  artifact from an earlier build would be published alongside the current one,
  under a version that may already be taken.
- **`build-verify` runs before the upload, in the same job.** It fails on the
  fallback version. A guard after the upload, or only in `preflight.yml`, cannot
  stop it. Its design is in
  [python-tooling.md](python-tooling.md#guard-against-a-000-release).
- The workflow asserts the lock with `UV_LOCKED: 1`, as
  [python-tooling.md](python-tooling.md#assert-the-lock-in-ci-with-uv_locked1-and-in-lint-with-uv-lock---check)
  describes, so a release is built from exactly the locked dependencies or not
  at all.

### Publish with trusted publishing, never an API token

PyPI's [trusted publishing](https://docs.pypi.org/trusted-publishers/) replaces
a stored API token with a short-lived OIDC token that GitHub issues to one
workflow run.

**Why:** there is no secret to leak or rotate, and the token is accepted only
from the workflow, repository and environment PyPI was told to trust.

```yaml
jobs:
  pypi-publish:
    environment:
      name: pypi
      url: https://pypi.org/p/<package>/
    permissions:
      id-token: write   # the OIDC token the upload exchanges
      contents: read    # checkout
```

- **`id-token: write` at the job level**, with `contents: read` beside it, as
  [workflows.md › Declare `permissions` on every job](workflows.md#declare-permissions-on-every-job-at-least-privilege)
  explains.
- **A GitHub environment per index: `pypi` and `testpypi`.** The environment
  name is part of what PyPI checks. `environment.url` is only the link GitHub
  displays, not the `repository-url` the action uploads to.
- **Configure the publisher on each index**, under the project's *Publishing*
  settings, or as a *pending publisher* before the first release:

  | Field | PyPI | Test PyPI |
  |---|---|---|
  | Owner | `iglootools` | `iglootools` |
  | Repository name | `<repo>` | `<repo>` |
  | Workflow name | `publish.yml` | `publish-test.yml` |
  | Environment name | `pypi` | `testpypi` |

  The workflow name is the filename of the workflow that uploads, so each index
  trusts a different file. A mismatch in any field shows only when an upload is
  attempted, as an `invalid-publisher` error.
- **Do not move the upload into a reusable workflow.** Trusted publishing does
  not support it, which is why `publish.yml` and `publish-test.yml` are two
  near-copies
  ([shared-workflows.md](shared-workflows.md#keep-publishing-in-the-project)).
  A change to one is made to the other.

### Rehearse on Test PyPI with a throwaway version

`publish-test.yml` is a copy of `publish.yml` that only `workflow_dispatch` and
`repository_dispatch` trigger. It uses the `testpypi` environment,
`repository-url: https://test.pypi.org/legacy/` and `verbose: true`, and
synthesizes its version:

```yaml
- name: Resolve PyPI-compatible version
  run: |
    version=$(uv run iglootools python dev-version)
    echo "UV_DYNAMIC_VERSIONING_BYPASS=$version" >> "$GITHUB_ENV"
```

**Why:** Test PyPI enforces the same no-reuse rule as PyPI, and a rehearsal must
be repeatable. Without one, a broken `publish.yml` is first discovered on a real
release.

- Rehearse after changing anything on the publish path: the workflows, the
  build backend, the `build-constraint-dependencies`, the trusted-publisher
  settings.
- `iglootools python dev-version` prints the **base release** in the nearest
  tag with `.dev<UTC timestamp>`, not the full VCS version: appending to one
  that carries `.post5.dev0` gives two dev segments, invalid PEP 440, which
  stays hidden while the workflow is only dispatched from a tag.
- Assign it to a variable first: a failing command inside `echo "…$(…)"` does
  not fail the step.
- `UV_DYNAMIC_VERSIONING_BYPASS` is read before any VCS lookup, so it replaces
  the computed version unconditionally.
- This inline step is one of the CI-only steps
  [workflows.md](workflows.md#keep-workflows-thin-set-up-the-toolchain-then-run-one-ci--task)
  allows in YAML.

## When a publish fails

### Rerun a publish that failed before uploading anything

`pypa/gh-action-pypi-publish` signs every distribution with a Sigstore
attestation before uploading any of them, so a Sigstore outage, such as a
`502 Bad Gateway` from `rekor.sigstore.dev`, fails the job with nothing on PyPI.
Rerun the failed job:

```bash
gh run rerun <run-id> --failed
```

**Why:** with nothing uploaded, the second attempt starts from a clean slate.

- Confirm first that the failure came before the upload: read the log, then
  [check the version](#verify-on-the-versions-own-json-endpoint).
- If some files reached PyPI, a rerun fails on the first file that exists.
  Uploading the rest of that version is a deliberate, one-off step, not a
  retry.

### Verify on the version's own JSON endpoint

A green publish job is not yet a release users can install. Check that PyPI
serves the files:

```bash
curl -s https://pypi.org/pypi/<package>/<version>/json \
  | jq '{version: .info.version, requires_python: .info.requires_python, files: [.urls[].filename]}'
```

**Why:** the project-level `https://pypi.org/pypi/<package>/json` is cached and
can report the previous version for a while after a good upload, which makes a
good release look missing, or prompts a rerun of one that succeeded.

- Expect both the wheel and the sdist.

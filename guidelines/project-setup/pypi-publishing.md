# PyPI Publishing Guidelines

How an iglootools Python package gets from a commit on `main` to a release on PyPI. How the
package is *built* — hatchling, the version plugin, the `0.0.0` guard — is in
[python-tooling.md](python-tooling.md#build-and-packaging); the rules every workflow follows —
action pinning, concurrency, timeouts, thin jobs — are in [workflows.md](workflows.md); the
rulesets that keep a release tag from moving are in
[repository.md](repository.md#protect-the-default-branch-and-release-tags). This file covers what
is specific to releasing: where the version comes from, how the three workflows hand off to each
other, how PyPI trusts them, and what to do when a publish fails.

Every rule here exists because PyPI is append-only. A version number, once taken, can never be
uploaded again — not after a deletion, not with different contents. A mistake anywhere else in
CI costs a re-run; a mistake here costs a version number and leaves a permanent record of it.

## The pipeline

| Workflow | Triggered by | Does |
|---|---|---|
| `release.yml` | `gh workflow run release.yml`, on `main` | picks the next version from conventional commits, pushes the `v<version>` tag, creates the GitHub release with the generated changelog |
| `publish.yml` | the `release` run completing (`workflow_run`), a pushed `v*` tag, or `gh workflow run publish.yml --ref <tag>` | builds and verifies the distributions at the tagged commit and uploads them to PyPI |
| `publish-test.yml` | `gh workflow run publish-test.yml` only | the same build and upload, to Test PyPI, under a throwaway version |

The normal release is one command, and the rest follows from it:

```bash
gh workflow run release.yml
gh run list --workflow publish.yml   # then watch the publish it triggers
```

Record the project's side of this in `docs/release-publish.md`: the workflows, the commands, and
the trusted-publisher configuration below, so it can be re-created and reviewed rather than
living only in the PyPI and GitHub settings.

## Versioning

### Derive the version from the git tag, never from `pyproject.toml`

`pyproject.toml` declares `dynamic = ["version"]` and
[`uv-dynamic-versioning`](https://github.com/ninoseki/uv-dynamic-versioning) computes it at build
time: a tagged commit builds as `1.4.0`, an untagged one as `1.4.0.post3.dev0+2a99beb`. The
setup is in [python-tooling.md](python-tooling.md#build-backend). The tag is therefore the
release: there is no version-bump commit to forget, and no way for the number in the file and
the number on PyPI to disagree.

The cost is that a build which cannot see the tags has no version, and with the required
`fallback-version` it does not fail — it succeeds as `0.0.0`. Everything in
[Build in CI, and verify before uploading](#build-in-ci-and-verify-before-uploading) exists
to keep that build from reaching PyPI.

### Let the release workflow pick the bump from conventional commits

`release.yml` runs
[`mathieudutour/github-tag-action`](https://github.com/mathieudutour/github-tag-action), which
reads the commit messages since the previous `v*` tag and bumps accordingly — `feat:` a minor,
`fix:` a patch, a `!` or a `BREAKING CHANGE:` footer a major — then pushes the tag and hands its
changelog to `ncipollo/release-action`, which creates the GitHub release:

```yaml
- uses: actions/checkout@<sha> # v7
  with:
    fetch-depth: 0     # the action needs the previous tag and every commit since it
    fetch-tags: true
- id: tag-version
  uses: mathieudutour/github-tag-action@<sha> # v7.0.0
  with:
    github_token: ${{ secrets.GITHUB_TOKEN }}
    fetch_all_tags: true
- uses: ncipollo/release-action@<sha> # v1
  with:
    tag: ${{ steps.tag-version.outputs.new_tag }}
    name: ${{ steps.tag-version.outputs.new_tag }}
    body: ${{ steps.tag-version.outputs.changelog }}
```

Three things this depends on that nothing checks:

- **Commit messages are the input.** The action's `default_bump` is `patch`, so a range of
  `chore:` and `docs:` commits, or messages that are not conventional at all, still releases —
  as a patch. Merging with a merge commit, as [repository.md](repository.md#merge-pull-requests-with-a-merge-commit)
  requires, is what keeps each branch commit, and therefore its type, visible to the action.
- **The tag is created through the API with `GITHUB_TOKEN`**, which needs write access to
  contents. The workflow declares no `permissions:` block, so it relies on the repository's
  default workflow permissions being read and write. With the read-only default, the tag push is
  refused and the release fails.
- **The release tag ruleset must allow creation**, which it does: it forbids only deletion and
  update. See [repository.md](repository.md#protect-the-default-branch-and-release-tags).

The tags the action creates are lightweight (they point at the commit, with no tag object). Any
`git describe` that reads them needs `--tags`. Without it, `git describe` sees only annotated
tags, and in these repositories it finds none.

### Pick the bump by hand when the commits undersell the change

Commit types describe commits, not releases. A change whose commits are all `chore:` can still
deserve a minor release: raising `requires-python` is the recurring case. Dropping Python
versions is released as a **minor**, not a patch and not a major. It does not break anyone's
existing install — an installer on an older Python skips the new release and keeps resolving the
last compatible one — but users need to find it in the release notes, which a patch does not
signal.

When that happens, skip `release.yml` and push the tag yourself:

```bash
git fetch origin
git log -1 origin/main                 # the merge commit `test` passed on
git tag v1.4.0 origin/main
git push origin v1.4.0                 # triggers publish.yml through `push: tags: v*`
gh release create v1.4.0 --verify-tag --title v1.4.0 --notes-file release-notes.md
```

- **Create the GitHub release by hand: nothing else will.** The changelog and the release are
  produced by `release.yml`, which this path skips. Nothing fails if you forget. PyPI has the
  version and the Releases page silently stops at the previous one. The next automated
  changelog starts from the tag you pushed, so the changes in this release are recorded nowhere
  else. Write the notes in the shape the action generates (a `## [1.4.0](<compare-url>)` heading
  and a bullet per change), and lead with what users must act on, such as the new Python
  requirement and how to install with it.
- **`--verify-tag` makes `gh` refuse to create the tag itself.** Without it, a typo in the tag
  name creates a new tag at the default branch head, which is not necessarily the commit you
  checked.
- **Check the commit before pushing.** The release tag ruleset forbids moving or deleting a
  `v*` tag, so a tag pushed to the wrong commit stays there. The publish it triggers takes the
  version number with it.
- Use the action's version format: `v` followed by the bare version, so the next automated
  release finds it as the previous tag.

## Publishing

### Chain publish to release with `workflow_run`, and also listen for `v*` tags

A tag pushed with `GITHUB_TOKEN` does not trigger other workflows. GitHub suppresses those events
so workflows cannot trigger each other in a loop. A publish workflow that only listened for tag
pushes would therefore never run after an automated release, and nothing would report it:
the tag and the GitHub release exist, and PyPI never gets the version. So `publish.yml` listens
for both:

```yaml
on:
  push:
    tags: ['v*']          # tags pushed by a person (the manual path above)
  workflow_run:
    workflows: ["release"] # tags pushed by release.yml
    types: [completed]
  workflow_dispatch:      # gh workflow run publish.yml --ref <tag>
  repository_dispatch:

jobs:
  pypi-publish:
    if: >-
      github.event.workflow_run.conclusion == 'success'
      || github.event_name != 'workflow_run'
```

Each release takes exactly one of the two paths. A tag pushed by the workflow fires no `push`
event, and a tag pushed by hand runs no `release` workflow. The concurrency group below covers a
manual dispatch that overlaps with either.

The `if:` is required: `workflow_run` with `types: [completed]` fires when the triggering run
*fails* as well, so without the guard a failed release would still start a publish. The
`workflows:` list matches the release workflow's `name:`, not its filename, which is one more
reason to [name every workflow after its file](workflows.md).

`workflow_dispatch` is for re-running a publish that never happened. Always pass the tag as
`--ref`: from a branch, the build gets a development version such as
`1.4.0.post3.dev0+2a99beb`. `build-verify` lets that through, since it only rejects `0.0.0`, and
PyPI then rejects it at upload because it does not accept local versions (`+…`).

### Check out the released commit, with its history and tags

```yaml
- uses: actions/checkout@<sha> # v7
  with:
    fetch-depth: 0
    fetch-tags: true
    ref: ${{ github.event.workflow_run.head_sha || github.sha }}
```

- **`fetch-depth: 0` and `fetch-tags: true`.** The default checkout is a single commit with no
  tags, which builds as `0.0.0` (see
  [python-tooling.md](python-tooling.md#guard-against-a-000-release)).
- **`ref: github.event.workflow_run.head_sha`.** For a `workflow_run` event, `github.sha` is the
  *current* head of the default branch, not the commit the release ran on. If anything merged in
  between, the publish would check out a commit past the tag and build a development version.
  `head_sha` is the commit `release.yml` tagged. The `|| github.sha` fallback covers the other
  triggers, where `github.sha` is already the tagged commit.

### Build in CI, and verify before uploading

The job's work is one task, as [workflows.md](workflows.md) asks, and the upload is the step
after it:

```yaml
- run: mise run ci-build      # install, build, build-verify
- uses: pypa/gh-action-pypi-publish@<sha> # release/v1
```

- **`build` empties `dist/` first.** `uv build` does not clear the directory, and the publish
  action uploads every file it finds there. A stale artifact left from an earlier build would be
  published alongside the current one, under a version that may already be taken.
- **`build-verify` runs before the upload, in the same job.** It reads the built wheel's metadata
  and fails on the fallback version. A guard that runs after the upload, or only in `test.yml`,
  cannot stop it. Its design is in
  [python-tooling.md](python-tooling.md#guard-against-a-000-release).
- **`UV_LOCKED: 1` in the workflow `env`.** It is set for the same reason as in `test.yml`: a
  release is built from exactly the locked dependencies, or not at all.

### Publish with trusted publishing, never an API token

PyPI's [trusted publishing](https://docs.pypi.org/trusted-publishers/) replaces a stored API
token with a short-lived OIDC token that GitHub issues to one workflow run. There is no secret to
leak or rotate, and the token is accepted only from the workflow, repository and environment
that PyPI was told to trust.

```yaml
jobs:
  pypi-publish:
    environment:
      name: pypi
      url: https://pypi.org/p/<package>/
    permissions:
      id-token: write   # mandatory: without it there is no OIDC token to exchange
```

- **`id-token: write` at the job level.** Without it the action has no token to exchange, and
  the upload fails.
- **A GitHub environment per index: `pypi` and `testpypi`.** The environment name is part of
  what PyPI checks. `environment.url` is only the link GitHub displays next to the deployment. It
  is not the `repository-url` that tells the action where to upload.
- **Configure the publisher on each index**, under the project's *Publishing* settings (or as a
  *pending publisher* before the first release, when the project does not exist yet):

  | Field | PyPI | Test PyPI |
  |---|---|---|
  | Owner | `iglootools` | `iglootools` |
  | Repository name | `<repo>` | `<repo>` |
  | Workflow name | `publish.yml` | `publish-test.yml` |
  | Environment name | `pypi` | `testpypi` |

  The workflow name is the filename of the workflow that uploads, so each index trusts a
  different file. A mismatch in any field is reported only when an upload is attempted, as an
  `invalid-publisher` error.
- **Do not move the upload into a reusable workflow.** Trusted publishing does not support
  reusable workflows. That is why `publish.yml` and `publish-test.yml` are two near-copies
  instead of callers of a shared one (see [shared-workflows.md](shared-workflows.md)). When you
  change one, make the same change in the other.

### Queue publish runs, never cancel them

`release.yml`, `publish.yml` and `publish-test.yml` all use the queueing concurrency group, keyed
on the workflow name alone with `cancel-in-progress: false`. A publish cancelled between two file
uploads leaves a version that can never be completed, and a release cancelled between the tag
and the GitHub release leaves a tag with no release. The reasoning, and the group to copy, are in
[workflows.md](workflows.md).

### Rehearse on Test PyPI with a throwaway version

`publish-test.yml` is a copy of `publish.yml` with these differences:

- only `workflow_dispatch` and `repository_dispatch` trigger it
- it uses environment `testpypi` and `repository-url: https://test.pypi.org/legacy/`
- it sets `verbose: true` on the publish action
- it synthesizes a version, because Test PyPI enforces the same no-reuse rule as PyPI and a
  rehearsal must be repeatable:

```yaml
- name: Resolve PyPI-compatible version
  run: |
    base=$(git describe --tags --abbrev=0 --match 'v[0-9]*' 2>/dev/null | sed 's/^v//' || echo 0.0.0)
    ts=$(date -u +%Y%m%d%H%M%S)
    echo "UV_DYNAMIC_VERSIONING_BYPASS=${base}.dev${ts}" >> "$GITHUB_ENV"
```

Derive it from the **base release** in the tag, not from the full VCS version. Appending `.dev<ts>`
to a version that already carries `.post5.dev0` produces two dev segments, which is invalid
PEP 440. That bug stays hidden as long as the workflow is only dispatched from a tag.
`UV_DYNAMIC_VERSIONING_BYPASS` is read before any VCS lookup, so it replaces the computed version
unconditionally. This inline step is one of the CI-only steps
[workflows.md](workflows.md) allows to stay in YAML.

Rehearse after changing anything on the publish path: the workflows, the build backend, the
`build-constraint-dependencies`, the trusted-publisher settings. A broken `publish.yml` is
otherwise first discovered on a real release.

## When a publish fails

### Rerun a publish that failed before uploading anything

`pypa/gh-action-pypi-publish` signs each distribution with a Sigstore attestation *before*
uploading any of them. An outage at Sigstore therefore fails the job with nothing on PyPI. In one
real case the transparency log returned
`502 Server Error: Bad Gateway for url: https://rekor.sigstore.dev/api/v1/log/entries` while
attesting the sdist. Rerunning the failed job is then safe, because the second attempt starts
from a clean slate:

```bash
gh run rerun <run-id> --failed
```

Confirm the failure happened before the upload first. Read the log, then check the version as
described below. If some files did reach PyPI, a rerun fails on the first file that already
exists. The rest of that version can still be uploaded, but deciding how is a deliberate,
one-off step, not a retry.

### Verify on the version's own JSON endpoint

A green publish job is not yet a release users can install. Check that PyPI serves the files:

```bash
curl -s https://pypi.org/pypi/<package>/<version>/json \
  | jq '{version: .info.version, requires_python: .info.requires_python, files: [.urls[].filename]}'
```

Expect both the wheel and the sdist. Use the version-specific URL. The project-level
`https://pypi.org/pypi/<package>/json` is cached and can keep reporting the previous version for
a while after a successful upload, which can make a good release look missing, or lead you to
rerun one that already succeeded.

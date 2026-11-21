# Shared Workflow Guidelines

Five workflows are identical across projects, so they live in this repository as
`reusable-*.yml` and each project calls them from a thin stub. Read this before
adding or editing a caller of one. The rules every workflow follows are in
[workflows.md](workflows.md); changing a shared workflow here is in
[docs/releasing-and-publishing.md](../../docs/releasing-and-publishing.md#the-shared-workflows).
Publishing to PyPI stays in each project:
[Keep publishing in the project](#keep-publishing-in-the-project).

<!-- toc -->
**On this page**

- [Call any shared workflow the same way](#call-any-shared-workflow-the-same-way)
  - [Pin `uses:` to the commit a `v*` tag names](#pin-uses-to-the-commit-a-v-tag-names)
  - [Declare permissions in the caller](#declare-permissions-in-the-caller)
  - [Keep triggers and concurrency in the caller](#keep-triggers-and-concurrency-in-the-caller)
  - [Pass the mise version as an input named `version`](#pass-the-mise-version-as-an-input-named-version)
- [The shared workflows](#the-shared-workflows)
  - [Call the shared link checker instead of copying it](#call-the-shared-link-checker-instead-of-copying-it)
  - [Call the shared lock regenerator on Renovate branches](#call-the-shared-lock-regenerator-on-renovate-branches)
  - [Submit a uv project's dependency graph through the shared workflow](#submit-a-uv-projects-dependency-graph-through-the-shared-workflow)
  - [Re-inspect the submission action on every version bump](#re-inspect-the-submission-action-on-every-version-bump)
  - [Call the shared release workflow](#call-the-shared-release-workflow)
  - [Call the shared demo recorder](#call-the-shared-demo-recorder)
  - [Keep publishing in the project](#keep-publishing-in-the-project)
<!-- tocstop -->

## Call any shared workflow the same way

### Pin `uses:` to the commit a `v*` tag names

Pin the ref to a full commit SHA, with the version in a trailing comment:
`uses: iglootools/common/.github/workflows/<workflow>.yml@<sha> # v<version>`.

**Why:** a tag or branch ref here would change what CI does in every project at
once, with no diff anywhere to review. The trailing comment is what Renovate
reads to raise the update pull request.

- Resolve the SHA for a release with:

  ```bash
  gh api repos/iglootools/common/commits/v<version> --jq .sha
  ```

- Not `git ls-remote … refs/tags/v<version>`: for an annotated tag it returns
  the tag object's SHA, which also looks right, but Actions resolves `uses:` to
  a commit. Dereference it as `'refs/tags/v<version>^{}'`, or use the API call.
- Use the plain `v<version>` tag, not `iglootools--v<version>`:
  [releasing-and-publishing.md › Releasing](../../docs/releasing-and-publishing.md#releasing)
  says why there are two.
- This repository's own callers use a local path ref
  (`./.github/workflows/<workflow>.yml`), so it exercises each workflow as
  changed rather than as last released.

### Declare permissions in the caller

The calling job declares every permission the shared workflow needs. The
`permissions` block in the called workflow is a ceiling on what the caller
granted, never a grant of its own.

**Why:** a permission declared only in the shared workflow is never granted, and
the job fails at the step that needed it, for the link checker only on a run
that found a broken link.

- Each working example linked below shows its block. The header of each
  `reusable-*.yml` says what each grant is for.
- Declare the whole block: omitted scopes become none, and `contents: read`
  fails only in private repositories, as
  [workflows.md › Declare `permissions` on every job](workflows.md#declare-permissions-on-every-job-at-least-privilege)
  describes.

### Keep triggers and concurrency in the caller

The stub holds the `on:` triggers and the `concurrency` group, even where the
expression is the same in every project.

**Why:** concurrency governs the run the triggers create, and the triggers are
the caller's. A group defined in the called workflow depends on how GitHub
resolves `github.workflow` across the call boundary, and getting that wrong
groups unrelated workflows and cancels them silently.

- Pick the group by
  [workflows.md › Supersede runs that can be redone](workflows.md#supersede-runs-that-can-be-redone-but-never-a-push-to-main)
  and
  [Queue runs whose partial state cannot be redone](workflows.md#queue-runs-whose-partial-state-cannot-be-redone).

### Pass the mise version as an input named `version`

A shared workflow that sets up mise takes the caller's mise version as an input
named `version`, written under the `# renovate:` marker:

```yaml
with:
  # renovate: datasource=github-releases depName=jdx/mise
  version: <the version mise.lock was generated with>
```

**Why:** the version has to match the one the project's `mise.lock` was
generated with, which is a per-project fact. The custom manager in
[renovate/base.json](../../renovate/base.json), which every project extends,
matches the marker followed by a literal `version:` line, so any other name,
such as `mise-version`, silently freezes the pin.

## The shared workflows

### Call the shared link checker instead of copying it

nbkp's
[check-links.yml](https://github.com/iglootools/nbkp/blob/main/.github/workflows/check-links.yml)
is a working example.

**Why:** link checking is the same everywhere, so a fix to the lychee invocation
or the report reaches every project through one version bump.

- It keeps one report open at a time: a run that finds broken links updates the
  open issue titled with the caller's `issue-title`, or files one, and a run
  that finds none closes it. An open report is always current, and closing one
  by hand is safe.
- Without `issues: write` the run fails with a 403 only when it finds a broken
  link, which is the moment the report was wanted.
- `.lycheeignore` stays in the caller, and is the per-repository knob: the
  shared workflow checks out the calling repository. List hosts that answer from
  a browser but never from a GitHub-hosted runner there. They are blocked, not
  slow: a longer `--timeout` only delays the same failure, and each one buries a
  genuine 404 in known noise.

### Call the shared lock regenerator on Renovate branches

nbkp's
[renovate-mise-lock.yml](https://github.com/iglootools/nbkp/blob/main/.github/workflows/renovate-mise-lock.yml)
is a working example.

**Why:** Renovate's hosted runner has no `mise`, so it bumps `mise.toml` but
cannot regenerate `mise.lock`, and every tool bump stays red until someone runs
it by hand.

- It regenerates `uv.lock` too, when the repository has one. Renovate does not
  re-lock a pin its regex custom manager bumps, such as
  `build-constraint-dependencies`; why that leaves `uv.lock` stale is in
  [python-tooling.md](python-tooling.md#pin-the-build-backend-explicitly).
- It runs `dprint fmt` when the repository has a `dprint.json`, and commits what
  it changed with the lock files. Renovate writes `mise.toml`, `dprint.json`,
  `renovate.json` and the workflows in its own style, and without this
  `dprint check` holds its pull request red until someone runs `mise run fmt` on
  the branch.
- The caller declares nothing extra for either: uv, Python and dprint come from
  its `mise.toml`.
- It sets up mise with `install: false` and `env: false`, the one legitimate use
  ([workflows.md](workflows.md#pair-install-false-with-env-false)).

### Submit a uv project's dependency graph through the shared workflow

A uv project calls the submission workflow, from a workflow of its own:

```yaml
jobs:
  submit:
    permissions:
      contents: write
    uses: iglootools/common/.github/workflows/reusable-uv-dependency-submission.yml@<sha> # v<version>
```

**Why:** GitHub's dependency graph does not parse `uv.lock`, so a uv project's
graph is empty, and Dependabot alerts and security updates, which run from it,
are silently off.

- `package-ecosystem: "uv"` in `dependabot.yml` does not fix this. It configures
  Dependabot updates, which read the manifest directly. With
  `open-pull-requests-limit: 0` it produces nothing, because security updates
  run through alerts.
- It runs third-party code with `contents: write`, the permission that pushes
  commits and moves tags, and no narrower scope reaches the snapshot API. The
  workflow's header lists GitHub's complete set of scopes.
- The safeguards are therefore structural, and the shared workflow applies them:
  an immutable SHA pin, `persist-credentials: false` on checkout, and no other
  step that could use the grant. Its own workflow means nothing else in the
  caller shares the token.

### Re-inspect the submission action on every version bump

A Renovate pull request moving the `rmuir/uv-dependency-submission` pin in
`reusable-uv-dependency-submission.yml` is reviewed by reading the diff of the
action's own sources between the two commits.

**Why:** the bump swaps code that holds `contents: write` on every consuming
repository, so it is not a routine dependency update.

- Treat a new network call, a file write, an added dependency, or a change in
  how the token is passed as a reason to stop.
- The pin lives here rather than in each project so that the review happens
  once.

### Call the shared release workflow

Python projects that release from conventional commits
([pypi-publishing.md](pypi-publishing.md#let-the-release-workflow-pick-the-bump-from-conventional-commits))
call it from `release.yml`, as nbkp's
[release.yml](https://github.com/iglootools/nbkp/blob/main/.github/workflows/release.yml)
does.

**Why:** the stub's name is what the publish and demo workflows listen for.

- Keep the stub named `release`. `publish.yml` and `demo.yml` start on
  `workflow_run` of the caller's name, not the shared workflow's, for the reason
  [pypi-publishing.md](pypi-publishing.md#chain-publish-to-release-with-workflow_run-and-also-listen-for-v-tags)
  gives.
- Its concurrency group queues, as for any workflow that pushes a tag
  ([workflows.md](workflows.md#queue-runs-whose-partial-state-cannot-be-redone)).
- Rehearse with `dry-run: true` under `with:`: it writes the next version and
  changelog to the run summary and pushes nothing.

### Call the shared demo recorder

CLI projects with an asciinema demo ([cli-demo.md](cli-demo.md)) call it from
`demo.yml`, as nbkp's
[demo.yml](https://github.com/iglootools/nbkp/blob/main/.github/workflows/demo.yml)
does.

**Why:** the recording steps and their release guards are the same in every CLI
project.

- It runs `mise run ci-demo-record` and uploads the cast as the `demo-recording`
  artifact. Its inputs and guards are in `reusable-demo.yml`.
- It skips a `workflow_run` whose release failed or released nothing, with the
  checks
  [pypi-publishing.md](pypi-publishing.md#skip-a-release-run-that-did-not-release)
  describes.
- `apt-packages` lists the system packages the session calls beyond mise's
  tools. It replaces the default, `pv`, which demo-magic needs, so keep `pv` in
  the list.

### Keep publishing in the project

`publish.yml` and `publish-test.yml` stay the project's own files, written as
[pypi-publishing.md](pypi-publishing.md) describes, although they are
near-identical across projects.

**Why:** trusted publishing ties a PyPI project to a workflow file in the
publishing repository, and `pypa/gh-action-pypi-publish` does not support
running inside a reusable workflow.

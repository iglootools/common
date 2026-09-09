# Shared Workflow Guidelines

Three workflows are identical in every project, so they live in this repository as reusable
workflows and each project calls them with a thin stub. The general rules a workflow has to
follow — pinning, concurrency, timeouts, naming — are in
[workflows.md](workflows.md).

### Call the shared link checker instead of copying it

Link checking is identical in every project, so it lives here as a reusable workflow rather
than as a file each repository keeps its own copy of:

```
iglootools/common-guidelines/.github/workflows/reusable-check-links.yml
```

A consuming repository keeps only what is genuinely its own:

```yaml
name: check-links

on:
  workflow_dispatch:
  repository_dispatch:
  schedule:
    - cron: "00 18 * * 1"

concurrency:
  group: ${{ github.workflow }}-${{ github.ref == 'refs/heads/main' && format('main-{0}', github.event.workflow_run.head_sha || github.sha) || github.ref }}
  cancel-in-progress: true

jobs:
  check-links:
    permissions:
      contents: read
      issues: write
    uses: iglootools/common-guidelines/.github/workflows/reusable-check-links.yml@<sha> # v<version>
```

Four things about that stub are load-bearing:

- **Pin the `uses:` ref to a full commit SHA, with the version in a trailing comment**, for the
  same reason [actions are pinned](workflows.md) — a tag or branch ref can be repointed
  under you, and here it would change what CI does in every project at once with no diff
  anywhere to review. The trailing comment is what Renovate reads to raise the update PR, so
  the pin stays updatable rather than frozen. Resolve the SHA for a release with:

  ```bash
  gh api repos/iglootools/common-guidelines/commits/v<version> --jq .sha
  ```

  Not `git ls-remote refs/tags/v<version>`: for an annotated tag that returns the tag *object's*
  SHA, which is also 40-hex and also looks right, but Actions resolves a `uses:` ref to a
  commit. Dereference it as `'refs/tags/v<version>^{}'` or use the API call above.

  Releases carry two tags at the same commit: `iglootools--v<version>` for the plugin, and a
  plain `v<version>` for git refs like this one. The plain tag exists because Renovate resolves
  ordinary version tags and not the prefixed spelling.

- **Both permissions have to be in the caller.** A called workflow's `permissions` is a
  ceiling on what the caller granted, never a grant of its own, so declaring them only in the
  reusable workflow leaves the token without them. Note also that declaring *any* permission
  zeroes every one left out, so this block is not a place to list only what looks relevant:

  - Without `issues: write`, the run 403s while filing the issue — and only on a run that found
    a broken link, which is the moment you most wanted the report.
  - Without `contents: read`, `actions/checkout` cannot clone. **In a private repository only**:
    a public one keeps working, because checkout falls back to an anonymous clone. A stub
    verified against public repositories will therefore pass and still be wrong, which is how
    this reached a private caller as `fatal: repository not found`.

- **`concurrency` stays in the caller**, even though it is the same expression everywhere.
  Concurrency governs the run the *triggers* create, and the triggers are the caller's; a group
  defined in the called workflow would depend on how GitHub resolves `github.workflow` across
  the call boundary, and getting that wrong groups unrelated workflows together and cancels
  them — silently, which is the failure the [concurrency rules](workflows.md) exist to prevent.

- **`.lycheeignore` stays in the caller too**, and is the intended per-repository knob. The
  reusable workflow checks out the *calling* repository, because the `github` context inside a
  called workflow is the caller's, so lychee reads that repository's ignore file with no flag
  needed. Use it for hosts that answer normally from a browser but never from a GitHub-hosted
  runner. Those are blocked, not slow: raising `--timeout` for them only buys a longer wait
  before the same failure, and each one pads every report so a genuine 404 arrives buried in
  known-good noise.

### Call the shared mise.lock regenerator too

The other workflow that is identical everywhere, for the same reason and with the same shape:

```
iglootools/common-guidelines/.github/workflows/reusable-renovate-mise-lock.yml
```

```yaml
name: renovate-mise-lock

on:
  push:
    branches:
      - 'renovate/**'

concurrency:
  group: renovate-mise-lock-${{ github.ref }}
  cancel-in-progress: true

jobs:
  mise-lock:
    permissions:
      contents: write
    uses: iglootools/common-guidelines/.github/workflows/reusable-renovate-mise-lock.yml@<sha> # v<version>
    with:
      # renovate: datasource=github-releases depName=jdx/mise
      version: <the version mise.lock was generated with>
```

The mise version stays in the caller rather than becoming a constant in the shared workflow, for
two reasons that both point the same way. The [rule on pinning mise](workflows.md) requires it
to match the version the
project locked with locally, which is a per-project fact. And the pin is kept current by the
Renovate custom manager in the project's own `renovate.json` — this repository runs no Renovate,
so a version moved here would be exactly the pin nothing updates that
[coding.md](../coding.md) warns about.

That is also why the input is named `version` and not `mise-version`: the custom manager matches
a `# renovate:` marker followed by whitespace and a literal `version:` line, so a more
descriptive name would silently stop matching and freeze the pin.

### A uv project must submit its own dependency graph

GitHub's dependency graph does not parse `uv.lock`. A uv project therefore has an **empty**
graph, and because Dependabot alerts are generated *from* the graph and Dependabot security
updates are triggered *by* alerts, both are silently off. Migrating from Poetry to uv turns
vulnerability detection off without a single error: the old `poetry.lock` alerts are left
orphaned against a file that no longer exists, and no new alert can ever be raised.

Note that `package-ecosystem: "uv"` in `dependabot.yml` does not fix this. That entry is
supported, but it configures Dependabot *updates*, which read the manifest directly. Paired
with `open-pull-requests-limit: 0` — version updates off, security updates the only reason
Dependabot is there — it produces nothing at all, because the security path runs through
alerts.

Call the shared workflow, which submits the graph from `uv.lock`:

```yaml
jobs:
  submit:
    permissions:
      contents: write
    uses: iglootools/common-guidelines/.github/workflows/reusable-uv-dependency-submission.yml@<sha> # v<version>
```

**It runs third-party code with `contents: write`, and that grant cannot be narrowed.** There is
no `dependency-graph` permission scope — the complete set is `actions`, `artifact-metadata`,
`attestations`, `checks`, `contents`, `deployments`, `discussions`, `id-token`, `issues`,
`models`, `packages`, `pages`, `pull-requests`, `repository-projects`, `security-events`,
`statuses` — and the snapshot API sits behind `contents: write`, the same permission that pushes
commits and moves tags.

So the safeguards are structural rather than permission-based, and the shared workflow applies
them: an immutable commit-SHA pin, `persist-credentials: false` on checkout, and a job that
contains no other step which could use the grant. Callers should give it a workflow of its own
rather than adding it to an existing one, so nothing else shares the token.

**Re-inspect the action on every version bump.** A Renovate PR moving that pin is not a routine
dependency update: it swaps code that holds `contents: write` on the repository. Read the diff of
the action's own sources between the two commits, and treat a new network call, a file write, an
added dependency, or a change in how the token is passed as a reason to stop rather than a
detail. The pin living in this repository rather than in each project is deliberate — it makes
that review happen once, here, instead of once per consumer.

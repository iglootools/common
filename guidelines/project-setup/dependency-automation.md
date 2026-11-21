# Dependency Automation Guidelines

How Renovate and Dependabot divide the work, and the repository settings both
depend on. The workflow that regenerates `mise.lock` and `uv.lock` on Renovate
branches is in
[shared-workflows.md](shared-workflows.md).

- `renovate.json`: group all dependency updates into a single PR, delay
  updates by 14 days (`minimumReleaseAge`) to avoid adopting broken
  releases and limit risk of supply chain attacks. The shared rules come from
  [the presets in iglootools/common](#extend-the-shared-renovate-presets).

<!-- toc -->
**On this page**

- [Extend the shared Renovate presets](#extend-the-shared-renovate-presets)
- [Committing `renovate.json` does not turn Renovate on](#committing-renovatejson-does-not-turn-renovate-on)
  - [Validate and preview the config with Renovate itself](#validate-and-preview-the-config-with-renovate-itself)
- [Turn on the dependency graph, alerts and security updates](#turn-on-the-dependency-graph-alerts-and-security-updates)
- [Split Renovate and Dependabot by job, not by ecosystem](#split-renovate-and-dependabot-by-job-not-by-ecosystem)
- [Give every copy of a pin the same datasource](#give-every-copy-of-a-pin-the-same-datasource)
<!-- tocstop -->

## Extend the shared Renovate presets

The rules every iglootools project needs live once, as presets in
[iglootools/common](https://github.com/iglootools/common/tree/main/renovate):

| Preset | Holds |
|---|---|
| `renovate/base` | `helpers:pinGitHubActionDigests`, the 14-day `minimumReleaseAge` with `timestamp-optional` and its exemption for iglootools' own releases, and the custom managers for the mise version pinned in workflows and for versions named in `mise.toml`'s `[env]` |
| `renovate/python` | the custom manager for `[tool.uv] build-constraint-dependencies` |

A project extends them pinned to the release tag, and keeps only what is its
own: its grouping and schedule, its holds, and its own custom managers.

```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": [
    "config:recommended",
    "github>iglootools/common//renovate/base#v<version>",
    "github>iglootools/common//renovate/python#v<version>"
  ],
  "separateMajorMinor": false,
  "packageRules": [
    {
      "groupName": "all dependencies",
      "matchManagers": ["*"],
      "schedule": ["at any time"],
      "automerge": false
    }
  ],
  "dependencyDashboard": { "enabled": true }
}
```

- **Pin the tag**, for the same reason the shared workflows are pinned: an
  unpinned preset changes every project's dependency updates at once, with no
  diff in any of them. Move the pin with the rest of the iglootools pins when a
  release lands.
- **A key the project sets overrides the preset's**, and arrays such as
  `customManagers` and `packageRules` are concatenated. Add a project's own
  manager or hold in its `renovate.json`; never copy a preset's entry, which
  would run it twice.
- `config:recommended` and grouping stay in the project because they differ: one
  project extends a framework's preset with `group:all` instead.

## Committing `renovate.json` does not turn Renovate on

The config is inert until the Renovate GitHub App is granted access to the
repository, and nothing in the repository can tell you whether that happened.
There is no error, no failed check and no log — the pins simply never move,
which looks exactly like having nothing to update.

**The tell is the Dependency Dashboard issue.** With `dependencyDashboard`
enabled, Renovate opens one on its first run, so its absence means it has never
run:

```bash
gh issue list --repo <owner>/<repo> --state all --search "Dependency Dashboard in:title"
gh pr list --repo <owner>/<repo> --state all --author app/renovate --json number -q length
```

Check both after adding the config, not months later. A repository can carry a
fully documented `renovate.json`, a complete set of SHA-pinned actions and a
pile of open Dependabot alerts while Renovate has never looked at it once.

Validate the config, and preview what Renovate would do, with the
[tasks below](#validate-and-preview-the-config-with-renovate-itself), rather
than waiting for its next run to report a mistake.

### Validate and preview the config with Renovate itself

Two tasks run Renovate locally, from the project's own pinned copy:

| Task | Runs | Family |
|---|---|---|
| `lint-renovate` | `renovate-config-validator --strict`, which validates `renovate.json` as repository config | a lint: `lint` runs it, since it takes about a second |
| `renovate-dry-run` | Renovate's local platform in lookup mode, which prints the updates it would propose from this checkout | neither writes nor fails on what it finds |

```toml
[tools]
node = "26.13.0"
jq = "1.8.2"
"npm:renovate" = { version = "44.239.1", trust_policy_excludes = ["@yarnpkg/libzip@3.2.2"], allow_builds = ["re2"] }

[tasks.lint-renovate]
description = "Validate the Renovate config with Renovate's validator, strictly"
run = "renovate-config-validator --strict"
```

`renovate-dry-run` is a file task, `mise-tasks/renovate-dry-run`: copy it from
iglootools/common. It takes a GitHub token from `GITHUB_COM_TOKEN` or else from
`gh auth token`, runs
`renovate --platform=local --dry-run=lookup --report-type=file`, and prints
the report as a table with `jq`, so a project without Python can run it.

- **Pass `--strict`.** Without it, a config that Renovate has renamed or
  restructured an option of passes with only a warning, and Renovate keeps
  migrating it in memory on every run without anyone being told. Strict mode
  fails on it, so the migration lands as a commit rather than going unnoticed.
- **Pin Renovate in mise, not through `npx`.** An unpinned `npx renovate`
  resolves to a very old release, which reports valid modern options as errors
  and invites you to "fix" a working config, and a version named on the
  command line is a pin no updater reads. In `[tools]`, Renovate's mise manager
  keeps it current like any other tool.
- **Commit `.mise/locks/`.** mise locks an npm tool's whole dependency tree in
  a file under it, which `mise.lock` pins by digest: without it, CI's locked
  install fails. Exclude the directory from dprint, which would otherwise
  reformat a file mise writes. The shared `base` preset keeps Renovate's npm
  manager off it, and the
  [shared lock regenerator](shared-workflows.md#call-the-shared-lock-regenerator-too)
  commits the new lock when Renovate moves the tool.
- **The two options are deliberate.** `allow_builds = ["re2"]` lets that one
  dependency run its build script: without its native module Renovate falls
  back to JavaScript's regex engine, and the validator accepts custom-manager
  patterns Renovate itself, which runs RE2, rejects. `trust_policy_excludes`
  exempts one release from mise's no-trust-downgrade check: the Yarn project's
  lead maintainer published `@yarnpkg/libzip@3.2.2` by hand, without the
  provenance its CI-published predecessors carry. It was reviewed (its tarball
  matches Yarn's source, and its compiled code is byte-identical to the
  attested 3.2.1) and the comment in iglootools/common's `mise.toml` records
  the review. Drop the exclusion once Renovate no longer resolves to it; never
  widen it to a bare package name, which would exempt every release.
- **Extend the presets with `github>`.** Renovate's local platform cannot fetch
  a `local>` preset and rejects the whole config, so the dry run needs the
  `github>iglootools/common//renovate/…` form the presets are documented with.

## Turn on the dependency graph, alerts and security updates

These are repository settings, not files, so a repository can carry a perfectly
good `dependabot.yml` and have none of it running. They form a chain, and each
link is a prerequisite for the next:

```text
dependency graph  ->  Dependabot alerts  ->  Dependabot security updates
```

The split below hands Dependabot the security half of the workload. That only
happens if the whole chain is on. Enable it with two calls — the first turns on
the dependency graph *and* alerts together, which is why there is no separate
graph command:

```bash
gh api --method PUT "repos/<owner>/<repo>/vulnerability-alerts"      # graph + alerts
gh api --method PUT "repos/<owner>/<repo>/automated-security-fixes"  # security updates
```

Both answer `204 No Content`, and both are idempotent, so running them against a
repository that already has the setting changes nothing. Do this when the
repository is created, alongside `git config user.email`.

A public repository gets the graph switched on and unremovable, which makes this
look done when it is not: alerts and security updates are still off until the
calls above are made. A private repository starts with none of the three.

Verify rather than assume, because the two endpoints disagree about how they
report state:

```bash
gh api -i "repos/<owner>/<repo>/vulnerability-alerts" | head -1   # 204 = on, 404 = off
gh api "repos/<owner>/<repo>/automated-security-fixes"            # read .enabled
```

`automated-security-fixes` returns **`200` whether the feature is on or off** —
the answer is `{"enabled": false}` in the body. Checking status codes alone
reports every repository as healthy.
`gh api repos/<owner>/<repo> --jq .security_and_analysis` gives the same answer
for security updates, plus the secret-scanning settings, and needs admin.

This is the same silent failure as
[Committing `renovate.json` does not turn Renovate on](#committing-renovatejson-does-not-turn-renovate-on),
and for a uv project it stacks with
[a graph that is empty until something submits it](shared-workflows.md#a-uv-project-must-submit-its-own-dependency-graph):
three independent switches, none of which reports anything when off, all of
which have to be on before a published advisory reaches a pull request.

## Split Renovate and Dependabot by job, not by ecosystem

**iglootools' own releases are exempt.** The `base` preset sets
`minimumReleaseAge` to zero for packages from the `iglootools` organization: the
shared workflows and presets, the `iglootools` command and its version in
`mise.toml`. The hold protects against someone else's broken or malicious
release; these are released and reviewed by the same people who review the
update, so waiting two weeks only delays fixes the projects are waiting for.

The 14-day delay above is a supply-chain measure: it protects you from a release
that turns out to be broken or malicious, and it works by waiting. Waiting is
exactly the wrong response to a published advisory, where the fix is already
known and every day of delay is another day of exposure.

One tool cannot be both slow and immediate, so give the two tools opposite
latencies:

| Tool | Handles | Latency |
|---|---|---|
| Renovate | routine version updates, grouped into one PR | delayed 14 days (`minimumReleaseAge`) |
| Dependabot | security updates only | immediate |

Renovate takes the routine half because it is also the only one of the two with
managers for `mise.toml` and `customManagers` regex entries. Dependabot takes
the security half because its advisory-driven updates are exempt from delay.

Do **not** let both do version updates. That produces duplicate PRs, and
Dependabot's half ignores the 14-day delay — quietly defeating the measure the
delay exists for.

`open-pull-requests-limit: 0` is what implements the split. It is GitHub's
documented way to switch off *version* updates for an ecosystem, and security
PRs are exempt from it (and from `cooldown`), so setting it to zero leaves
exactly the security half running:

```yaml
updates:
  - package-ecosystem: "uv"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 0
```

**`package-ecosystem` must track the build tool.** A stale value fails
*silently*: `pip` reads `poetry.lock` and understands neither `uv.lock` nor
`[dependency-groups]`, so after a migration it keeps running, finds nothing, and
reports green — indistinguishable from working coverage.

## Give every copy of a pin the same datasource

Some versions are pinned in more than one place: the uv in `mise.toml` and in a
test image's Dockerfile, say. Renovate updates each copy through whichever
manager found it, and the 14-day `minimumReleaseAge` holds an update only when
its datasource reports a release date. A Docker image tag has none, and under
`minimumReleaseAgeBehaviour: timestamp-optional` an update without a date is not
held at all. So the Dockerfile's copy can be bumped the day a release appears,
while `mise.toml`'s copy, a dated GitHub release, waits two weeks. The two drift
apart in the very PR meant to update them, and nothing fails to say so.

Track every copy through the same datasource, so all of them become eligible on
the same day and land in the same update:

- Mark each extra copy with a `# renovate:` comment naming the datasource and
  package the primary copy uses — for a tool pinned in `mise.toml`, the one
  Renovate's mise manager uses for it, such as `github-releases` `astral-sh/uv`
  — and read the comments with a regex `customManagers` entry.
- Turn the original manager off for those copies only, so a copy is not updated
  twice: a `packageRules` entry with `matchManagers` (`["dockerfile"]`),
  `matchDepNames` listing the copies as that manager names them
  (`ghcr.io/astral-sh/uv`), and `"enabled": false`.
- Leave a pin that exists once, such as a Debian base image, with its own
  manager.

nbkp found this in
[iglootools/nbkp#259](https://github.com/iglootools/nbkp/pull/259), where a
Renovate PR bumped uv in its test Dockerfile and left `mise.toml` behind. Check
for duplicated pins whenever a version appears in a second file, not only when
the first drift shows up.

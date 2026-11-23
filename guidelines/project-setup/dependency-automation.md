# Dependency Automation Guidelines

How Renovate and Dependabot divide the work, and the repository settings both
depend on: `renovate.json`, `dependabot.yml`, the Renovate tasks and pin, and
the shared presets in `renovate/`. Read it before changing any of them, or when
a dependency update did or did not appear. The workflow that regenerates
`mise.lock` and `uv.lock` on Renovate branches is in
[shared-workflows.md](shared-workflows.md#call-the-shared-lock-regenerator-on-renovate-branches).

<!-- toc -->
**On this page**

- [Extend the shared Renovate presets](#extend-the-shared-renovate-presets)
- [Split Renovate and Dependabot by job, not by ecosystem](#split-renovate-and-dependabot-by-job-not-by-ecosystem)
- [Confirm Renovate has run, from the Dependency Dashboard](#confirm-renovate-has-run-from-the-dependency-dashboard)
- [Validate and preview the config with Renovate itself](#validate-and-preview-the-config-with-renovate-itself)
- [Turn on the dependency graph, alerts and security updates](#turn-on-the-dependency-graph-alerts-and-security-updates)
- [Give every copy of a pin the same datasource](#give-every-copy-of-a-pin-the-same-datasource)
- [Rationale](#rationale)
  - [Give every copy of a pin the same datasource](#give-every-copy-of-a-pin-the-same-datasource-1)
<!-- tocstop -->

## Extend the shared Renovate presets

Extend the presets in
[iglootools/common](https://github.com/iglootools/common/tree/main/renovate),
pinned to the release tag, and keep in `renovate.json` only what is the
project's own: its grouping and schedule, its holds, and its own custom
managers.

- [renovate/base.json](../../renovate/base.json): extend it in every project.
  Each entry carries its reason in its `description`.
- [renovate/python.json](../../renovate/python.json): extend it as well in a
  Python project, one that builds a package. A project without Python, whose
  `pyproject.toml` holds only the `iglootools` command, needs only `base`.
- iglootools' own releases skip the 14-day hold: the `base` preset exempts them,
  since the people who release them also review the update.

nbkp's
[renovate.json](https://github.com/iglootools/nbkp/blob/main/renovate.json) is a
working example.

**Why:** the rules every project needs then live once, and a fix reaches every
project by moving a pin.

- **Pin the tag**: an unpinned preset changes every project's dependency updates
  at once, with no diff in any of them. Move the pin with the other iglootools
  pins when a release lands.
- **A key the project sets overrides the preset's**, and arrays such as
  `customManagers` and `packageRules` are concatenated. Add a project's own
  manager or hold in its `renovate.json`; never copy a preset's entry, which
  would run it twice.
- `config:recommended` and grouping stay in the project because they differ:
  one project extends a framework's preset with `group:all` instead.

## Split Renovate and Dependabot by job, not by ecosystem

Renovate does routine version updates, grouped into one PR and held 14 days
(`minimumReleaseAge`, set by the `base` preset). Dependabot does security
updates only, at once. Never let both do version updates.

**Why:** the hold is a supply-chain measure that works by waiting, which
protects against a broken or malicious release and is exactly wrong for a
published advisory. Version updates from Dependabot would duplicate Renovate's
PRs and ignore the hold.

- Renovate takes the routine half because only it has managers for `mise.toml`
  and regex `customManagers`. Dependabot takes the security half because its
  advisory-driven updates skip delays.
- `open-pull-requests-limit: 0` implements the split: it switches off version
  updates for an ecosystem, while security PRs are exempt from it (and from
  `cooldown`).

  ```yaml
  updates:
    - package-ecosystem: "uv"
      directory: "/"
      schedule:
        interval: "weekly"
      open-pull-requests-limit: 0
  ```

- **`package-ecosystem` tracks the build tool.** A stale value fails silently:
  `pip` reads `poetry.lock` and understands neither `uv.lock` nor
  `[dependency-groups]`, so it finds nothing and reports green.

## Confirm Renovate has run, from the Dependency Dashboard

After adding `renovate.json`, check that Renovate has opened its Dependency
Dashboard issue, or any PR:

```bash
gh issue list --repo <owner>/<repo> --state all --search "Dependency Dashboard in:title"
gh pr list --repo <owner>/<repo> --state all --author app/renovate --json number -q length
```

**Why:** the config is inert until the Renovate GitHub App is granted access to
the repository, and nothing reports that it was not: the pins simply never
move, which looks like having nothing to update.

- With `dependencyDashboard` enabled, Renovate opens the issue on its first run,
  so its absence means it has never run.

## Validate and preview the config with Renovate itself

Pin Renovate in mise and give the project two tasks:

| Task | Runs | Family |
|---|---|---|
| `lint-renovate` | `renovate-config-validator --strict`, which validates `renovate.json` as repository config | a lint: `lint` runs it, since it takes about a second |
| `renovate-dry-run` | Renovate's local platform in lookup mode, printing the updates it would propose from this checkout | a report |

```toml
[tools]
"npm:renovate" = { version = "<version>", allow_builds = ["re2"] }

[tasks.lint-renovate]
description = "Validate the Renovate config with Renovate's validator, strictly"
run = "renovate-config-validator --strict"
```

**Why:** a mistake shows up before a push rather than on Renovate's next run.

- **`renovate-dry-run` is a file task**: copy `mise-tasks/renovate-dry-run`
  from iglootools/common. It needs `node` and `jq` in `[tools]`, and runs in a
  project without Python.
- **Pass `--strict`.** Without it, a config with a renamed or restructured
  option passes with a warning, and Renovate migrates it in memory on every run
  without telling anyone. Strict mode makes the migration land as a commit.
- **Pin Renovate in mise, not through `npx`.** An unpinned `npx renovate`
  resolves to a very old release that reports valid modern options as errors,
  and a version named on the command line is a pin no updater reads.
- **Commit `.mise/locks/`.** mise locks an npm tool's dependency tree in a file
  under it, which `mise.lock` pins by digest: without it, CI's locked install
  fails. The `base` preset keeps Renovate's npm manager off it, the
  [shared lock regenerator](shared-workflows.md#call-the-shared-lock-regenerator-on-renovate-branches)
  commits the new lock when Renovate moves the tool, and
  [formatting.md](formatting.md#exclude-from-dprint-what-a-tool-writes-in-its-own-style)
  keeps dprint off it.
- **Keep `allow_builds = ["re2"]`**: without its native module Renovate falls
  back to JavaScript's regex engine, and the validator accepts custom-manager
  patterns Renovate itself rejects.
- **Exempt a release from mise's trust check by exact version, after review.**
  iglootools/common's [mise.toml](../../mise.toml) records the one exemption
  (`trust_policy_excludes`), its review and the condition that retires it. Never
  widen one to a bare package name, which exempts every release.
- **Extend the presets with `github>`.** Renovate's local platform cannot fetch
  a `local>` preset and rejects the whole config.

## Turn on the dependency graph, alerts and security updates

Enable the chain with two calls, when the repository is created, and verify
both:

```bash
gh api --method PUT "repos/<owner>/<repo>/vulnerability-alerts"      # graph + alerts
gh api --method PUT "repos/<owner>/<repo>/automated-security-fixes"  # security updates

gh api -i "repos/<owner>/<repo>/vulnerability-alerts" | head -1   # 204 = on, 404 = off
gh api "repos/<owner>/<repo>/automated-security-fixes"            # read .enabled
```

**Why:** these are repository settings, not files, so a repository can carry a
good `dependabot.yml` with none of it running, and nothing says so. Each link of
the chain (graph, then alerts, then security updates) is a prerequisite for the
next.

- Both PUTs answer `204 No Content` and are idempotent.
- `automated-security-fixes` returns `200` whether the feature is on or off:
  read `enabled` in the body, not the status code.
  `gh api repos/<owner>/<repo> --jq .security_and_analysis` gives the same
  answer, plus the secret-scanning settings, and needs admin.
- A public repository has the graph on and unremovable, while alerts and
  security updates stay off until the calls. A private one starts with none of
  the three.
- Record the calls with the repository's other settings, as
  [layout.md](../documentation/layout.md#record-repository-settings-as-commands-in-one-place)
  describes.
- A uv project also has to
  [submit its own dependency graph](shared-workflows.md#submit-a-uv-projects-dependency-graph-through-the-shared-workflow).
  With that and
  [Renovate's first run](#confirm-renovate-has-run-from-the-dependency-dashboard),
  three independent switches must be on, none of which reports anything when
  off.

## Give every copy of a pin the same datasource

When a version is pinned in more than one place, such as uv in `mise.toml` and
in a test image's Dockerfile, track every copy through the datasource the
primary copy uses.

**Why:** the hold applies only to an update whose datasource reports a release
date, so copies read through different managers become eligible on different
days and drift apart in the PR meant to update them.
[Rationale](#give-every-copy-of-a-pin-the-same-datasource-1)

- Mark each extra copy with a `# renovate:` comment naming the primary copy's
  datasource and package (for a tool in `mise.toml`, the one Renovate's mise
  manager uses, such as `github-releases` `astral-sh/uv`), and read the comments
  with a regex `customManagers` entry.
- Turn the original manager off for those copies only: a `packageRules` entry
  with `matchManagers` (`["dockerfile"]`), `matchDepNames` listing the copies as
  that manager names them (`ghcr.io/astral-sh/uv`), and `"enabled": false`.
- Leave a pin that exists once, such as a Debian base image, with its own
  manager.
- Check for duplicated pins whenever a version appears in a second file.

## Rationale

### Give every copy of a pin the same datasource

A Docker image tag has no release date, and under
`minimumReleaseAgeBehaviour: timestamp-optional` an update without a date is not
held at all. So the Dockerfile's copy can be bumped the day a release appears,
while `mise.toml`'s copy, a dated GitHub release, waits two weeks. nbkp hit this
in [iglootools/nbkp#259](https://github.com/iglootools/nbkp/pull/259), where a
Renovate PR bumped uv in the test Dockerfile and left `mise.toml` behind.

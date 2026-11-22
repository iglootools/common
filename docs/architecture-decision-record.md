# Architecture Decision Record

The decisions taken on this repository that someone would otherwise argue about
again, newest at the bottom. An entry is never edited to change its decision: a
new entry supersedes it, so the log keeps what was believed at the time. The
format is in
[layout.md › Record architectural decisions](../guidelines/documentation/layout.md#record-architectural-decisions-in-an-append-only-log).

<!-- toc -->
**On this page**

- [ADR-001 — Check the pins on common offline, trusting uv.lock and IGLOOTOOLS_VERSION's name](#adr-001--check-the-pins-on-common-offline-trusting-uvlock-and-iglootools_versions-name)
  - [Context](#context)
  - [Decision](#decision)
  - [Rationale](#rationale)
  - [Consequences](#consequences)
<!-- tocstop -->

<!-- toc -->
<!-- tocstop -->

## ADR-001 — Check the pins on common offline, trusting uv.lock and IGLOOTOOLS_VERSION's name

**Date:** 2026-11-21
**Status:** Accepted

### Context

Every iglootools project pins a release of this repository in several places:

| Pin | Example | Where |
|---|---|---|
| a reusable workflow, by commit SHA with the tag in a comment | `uses: iglootools/common/.github/workflows/reusable-release.yml@8bd88a2… # v1.33.1` | `.github/workflows/` |
| the `iglootools` command, by tag | `iglootools @ git+https://github.com/iglootools/common@v1.33.1` | `pyproject.toml` (Python projects) |
| a Renovate preset, by tag | `github>iglootools/common//renovate/base#v1.33.1` | `renovate.json` |
| the release the uvx alias runs | `IGLOOTOOLS_VERSION = "v1.33.1"` | `mise.toml` (projects without Python) |

`iglootools common adopt` moves them all to a release. Two things can drift
without anything failing. A pin can be added in a file adopt never reads, or
spelled in a way its rewrite does not recognise, so the next adopt leaves it
behind. And a pin can be edited by hand to disagree with the others, most
dangerously a workflow SHA that is not the commit its `# vX.Y.Z` comment names.

The check has to run as a lint, in every project's CI, where there may be no
GitHub token and no network access worth depending on.

### Decision

- **adopt finds pins in every tracked file that mentions common**, lock files
  aside, instead of a list of file names. A file nobody thought to list cannot
  hide a pin.
- **`iglootools common check-pins` runs offline, as each project's
  `lint-common-pins` task.** It finds every pin with patterns deliberately
  broader than adopt's rewrite, and fails when:
  - adopt would not move one, which is the drift between the files and the
    rewrite;
  - two pins name different releases;
  - a SHA pin has no `# vX.Y.Z` comment naming its release;
  - in a project with a `uv.lock`, the pins disagree with the release it locked,
    or a workflow SHA is not the commit it recorded for that release.
- **It trusts two things it does not verify:**
  - **uv.lock's record of which commit the tag named.** `uv lock` asked GitHub
    once, when adopt ran it, and wrote
    `common?rev=v1.33.1#<commit>`. `lint-lock-uv` keeps `rev` in step with
    `pyproject.toml`, and the release-tag ruleset keeps the tag from moving, so
    the recorded commit stays true.
  - **`IGLOOTOOLS_VERSION`'s name.** The variable is a pin on common because the
    `IGLOOTOOLS` alias beside it builds the common URL from it, and the
    `# renovate:` comment above it names `depName=iglootools/common`. The check
    does not read either line.

### Rationale

Running offline keeps the lint usable where it matters: in CI on every pull
request, including Renovate's and those from forks, and on a laptop without a
token. The checks it makes catch the failures seen in practice: a pin left
behind by a fixed file list, and SHAs and tags drifting apart.

Alternatives not pursued:

- **Verify every pin against GitHub inside the lint.** It would check each
  workflow SHA against its tag's real commit in every project. It needs a token
  and network access in CI, so a GitHub outage or a rate limit fails unrelated
  pull requests, and pull requests from forks get no token at all. The local
  `--online` variant below keeps the benefit without putting it on CI's path.
- **Add a `--online` option, for local runs and for adopt.** Worth having, and
  the natural next step if a limitation below ever bites. Not built yet, because
  adopt always writes the SHA GitHub returns, so only a hand edit can get one
  wrong.
- **Record the tag's commit for projects without Python**, for example as a
  comment next to `IGLOOTOOLS_VERSION` or in a lock file of our own. It would
  let the offline check verify their workflow SHAs. But it is one more pin to
  keep in step, written by hand or by adopt, guarding against a hand edit that
  the same hand could make to the record.
- **Give projects without Python a minimal `pyproject.toml`**, so uv locks the
  command and the check gets `uv.lock`'s record everywhere. It brings Python
  scaffolding, a `.venv` and a uv lock check into repositories that have no
  Python, to serve one lint.
- **Pin the uvx alias by commit SHA instead of tag.** It would make the release
  unambiguous without a record. But Renovate's tag tracking and the readable
  `v1.33.1` would go, and the workflow pins would still need their comment.
- **Read the `IGLOOTOOLS` alias, or the Renovate comment, to confirm the
  variable is a pin on common.** Cheap, and it would close the second
  limitation. Left out because both projects that use the variable define the
  alias the same way, from the guideline's example, and a mismatch would break
  every task that calls `$IGLOOTOOLS` at once, which is louder than any lint.
- **Keep a list of files for adopt, and have the lint check the list.** It
  moves the drift to the list instead of removing it.

### Consequences

- **In projects without a `uv.lock`** (alberta-hiking-resources, network-infra),
  a workflow SHA edited by hand to the wrong commit, with its `# vX.Y.Z` comment
  left right, passes the check. adopt and Renovate always write the right one.
- **`IGLOOTOOLS_VERSION` counts as a pin on common by its name.** A variable of
  that name used for something else would be checked and moved as one.
- **A moved tag would make uv.lock's record wrong.** The release-tag ruleset
  forbids moving one; if it were ever lifted, this decision would need
  revisiting.

**Retire this** when a project's CI can rely on a token and network access for
its lints, or when a wrong SHA or a misnamed variable gets through: then add
the `--online` verification and run it from adopt, or from CI.

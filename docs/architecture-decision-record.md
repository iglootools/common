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
- [ADR-002 — Keep pyright as the type checker, rather than switching to ty](#adr-002--keep-pyright-as-the-type-checker-rather-than-switching-to-ty)
  - [Context](#context-1)
  - [Decision](#decision-1)
  - [Rationale](#rationale-1)
  - [Consequences](#consequences-1)
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

## ADR-002 — Keep pyright as the type checker, rather than switching to ty

**Date:** 2026-11-22
**Status:** Accepted

### Context

Every Python project type-checks with pyright, in strict mode, tests included,
as
[python-tooling.md](../guidelines/project-setup/python-tooling.md#type-check-with-pyright-in-strict-mode-tests-included)
asks; common, nbkp and photree reached zero errors on 2026-11-22. Astral's ty
is a faster alternative, still pre-1.0 (0.0.107 at the time), releasing several
times a week. We re-evaluated pyright against ty twice: on the code as it was
before strict mode, and again once it passed strict mode.

Before strict mode, ty reported 12, 28 and 42 findings in common, nbkp and
photree, mostly false positives. Once the projects passed strict mode it
reported 20, none a real bug:

- 9 already suppressed for pyright: ty reads neither `# pyright: ignore[...]`
  nor the mypy-style `# type: ignore[arg-type]`.
- 6 deliberate invalid writes in nbkp's tests, inside
  `pytest.raises(ValidationError)`. ty sees pydantic's frozen fields as
  read-only, which pyright does not; the tests are correct.
- 5 false positives from ty's inference: narrowing across the `case` branches
  of a tuple `match`, a `match` covering every member of an enum, narrowing
  inside a nested function, and generic types between two functions.

ty did not report what strict mode found before the projects were fixed: in
common, the three `match` statements that handled only some cases, the untyped
empty lists, and the private functions used from tests. Its 165 rules have no
equivalent for most of strict mode:

| Strict-mode check | ty |
|---|---|
| a `match` that misses a case | none; only a function that then returns nothing, not code that carries on after the `match` |
| values of unknown type | only calls to functions with unknown signatures |
| missing parameter or return annotations | none |
| a `_private` name used from another module | none |
| a bare `list` or `dict` | `missing-type-argument` |
| a check or cast that cannot fail | `redundant-condition`, `redundant-cast` |
| a suppression no longer needed | `unused-ignore-comment` |

### Decision

- **Keep pyright, in strict mode, as the type checker and `lint-types` gate for
  the foreseeable future.**
- **Do not run ty alongside it in CI.** Anyone may try ty as an editor language
  server; nothing depends on it.

### Rationale

Switching would let the strict baseline erode without anything failing: new
code could bring in values of unknown type, unannotated functions and partial
`match` statements, which ty does not check. ty's advantage is speed, and
pyright already checks each project in about two seconds. On top of that, ty
has no compatibility promise before 1.0 and releases several times a week, its
five false positives on our code would each need a `# ty: ignore`, and every
existing `# pyright: ignore` would need rewriting in its syntax.

Alternatives not pursued:

- **Switch to ty.** Faster, and more precise on pydantic's frozen fields, but
  it gives up most of what strict mode checks.
- **Run both in CI.** It adds nothing pyright misses on our code, and doubles
  the suppressions: every correct line ty misreads needs its own ignore.
- **Run ty in CI as an advisory, non-blocking check.** A check nobody has to
  act on is noise that teaches everyone to ignore it.

### Consequences

- The projects keep pyright's slower check, about two seconds each, which does
  not matter at their size.
- ty's real strengths, such as reading pydantic's frozen fields as read-only,
  go unused.
- Suppressions stay in pyright's syntax only.

**Retire this** when ty reaches a stable 1.0 with equivalents for at least
`match` exhaustiveness and unknown-type reporting: then re-run the comparison
(`uvx ty@<version> check` on each project) and decide again.

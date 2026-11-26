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
- [ADR-003 — Enable every ruff rule, except those our conventions are against](#adr-003--enable-every-ruff-rule-except-those-our-conventions-are-against)
  - [Context](#context-2)
  - [Decision](#decision-2)
  - [Rationale](#rationale-2)
  - [Consequences](#consequences-2)
- [ADR-004 — Install the iglootools command through uv in every project, Python or not](#adr-004--install-the-iglootools-command-through-uv-in-every-project-python-or-not)
  - [Context](#context-3)
  - [Decision](#decision-3)
  - [Rationale](#rationale-3)
  - [Consequences](#consequences-3)
- [ADR-005 — Load only the guideline indexes into every session](#adr-005--load-only-the-guideline-indexes-into-every-session)
  - [Context](#context-4)
  - [Decision](#decision-4)
  - [Rationale](#rationale-4)
  - [Consequences](#consequences-4)
<!-- tocstop -->

## ADR-001 — Check the pins on common offline, trusting uv.lock and IGLOOTOOLS_VERSION's name

**Date:** 2026-11-21 **Status:** Accepted — superseded in part by ADR-004, which
gives every project a `uv.lock`

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

## ADR-003 — Enable every ruff rule, except those our conventions are against

**Date:** 2026-11-22
**Status:** Accepted

### Context

Ruff's default rule set (about 400 rules in 0.17) leaves out most of what it
can check. A first pass selected only the rules that enforce a written
guideline, such as `PERF401` for
[building a collection in one expression](../guidelines/coding/python.md#build-a-collection-in-one-expression-not-by-appending).
That still left off rules that make the code stricter without contradicting
anything we do: unused arguments, boolean positional parameters, magic numbers,
`pathlib` over `os.path`, exception messages built at the `raise`.

### Decision

Every project selects `ALL`, and ignores only a rule that a convention is
against, or that fights a tool we use. Each ignored rule is listed here with
its reason:

| Ignored | Why |
|---|---|
| `D203`, `D212` | Each is the opposite of a rule we keep. `D211`: no blank line before a class docstring, which is also what the formatter writes. `D213`: a multi-line docstring opens with `"""` alone and starts its summary on the next line, so the summary lines up with the detail below it. |
| `CPY001` | The repository's LICENSE covers every file; a header per file repeats it. |
| `TC001`–`TC003` | They move imports into a `TYPE_CHECKING` block, which [python.md](../guidelines/coding/python.md#import-at-module-level-and-defer-with-lazy-import) rules out. |
| `RET505`–`RET508` | They delete the explicit `else` [python.md](../guidelines/coding/python.md#prefer-match-and-explicit-branches-over-chains-and-early-returns) asks for. |
| `C901`, `PLR0911`, `PLR0912` | They count each `case` of a `match`, so they penalise the flat dispatch python.md prefers. `PLR0915` (`max-statements = 30`) still keeps functions short. |
| `PLR0913` | Keyword seams ([python.md](../guidelines/coding/python.md#make-a-seam-a-keyword-parameter-whose-default-is-the-real-function)) add parameters by design. `PLR0917` still caps the positional ones at five. |
| `S603`, `S607` | `S603` flags every `subprocess` call made with an argument list, the form [general.md](../guidelines/coding/general.md#escape-interpolated-text-or-keep-it-apart-from-markup) asks for; `S607` flags a program found on `PATH`, which is how mise provides tools. |
| In `tests/**`: `D1`, `S101`, `PLR2004`, `S105`–`S107` | A test's name says what it checks, so [it needs no docstring](../guidelines/coding/general.md#document-every-public-module-class-and-function); pytest asserts with `assert`; a test's literals are its specification; the "secrets" are fakes or keyring entry names such as `passphrase_id`. `S108` stays on in tests: a test writes under `tmp_path`, and a `/tmp` path used only as data carries a `noqa`. |

The rules ruff's documentation lists as conflicting with the formatter stay
on as well. `E501` catches the strings, comments and docstrings the formatter
leaves long, and since ruff 0.9 the formatter joins implicitly concatenated
strings itself, so `ISC001` no longer fights it. `COM812` still can: the
formatter may leave a call's last arguments on one line without a trailing
comma, which the rule then adds, and the formatter then splits one argument per
line. Running `ruff check --fix` and `ruff format` twice settles it, and
`ruff format` prints a warning about the rule on every run.

Two settings go with it: `ban-relative-imports = "all"`, since every project
imports absolutely, and `PLW1514` selected by name with `preview = true` and
`explicit-preview-rules = true`, because it is still a preview rule and `ALL`
selects stable rules only.

A project's own exception goes in its `pyproject.toml` with its reason, as
narrow as it reaches, such as photree's `DTZ001` for EXIF times that carry no
offset.

### Rationale

- A rule that is on catches the mistake when it is made; a rule nobody enabled
  catches nothing. Listing what is off, with a reason, is shorter than listing
  what is on, and makes each exception an explicit choice.
- Rules that only enforce a taste we do not hold are rare once the conflicts
  above are out: the rest describe code we would accept anyway.
- `D401` (an imperative docstring summary) and `TID252` (absolute imports) set
  conventions the guidelines had not written down; both were adopted rather
  than ignored.

### Consequences

- A ruff upgrade turns on the rules it adds, so a Renovate pull request for ruff
  can fail `lint-ruff`. Fix the new findings in that pull request, or add the
  rule here with its reason.
- Rules for frameworks we do not use (Airflow, Django, FastAPI, NumPy, pandas)
  are selected too. They never fire, and need no entry.
- The first adoption rewrote much of nbkp and photree: absolute imports,
  keyword-only booleans, error types that build their own message.

**Retire this** if ruff's default set grows to cover what `ALL` adds, or if the
ignore list grows long enough that selecting rule families would be shorter.

## ADR-004 — Install the iglootools command through uv in every project, Python or not

**Date:** 2026-11-22 **Status:** Accepted — supersedes ADR-001's rejection of a
minimal `pyproject.toml` for projects without Python

### Context

Python projects install the `iglootools` command as a uv dev dependency;
projects without Python (alberta-hiking-resources, network-infra) ran it
through uvx, with the release named in `IGLOOTOOLS_VERSION` in `mise.toml`.
ADR-001 weighed giving those projects a minimal `pyproject.toml` instead, and
rejected it as Python scaffolding brought in to serve one lint.

Two things have changed since. The reusable workflows need to call the command
for the logic they still copy between projects (the release-tag guard, the link
report, the Test PyPI version), and they run in every project, so they need one
way to call it. And uvx pins the command's release but not its dependencies:
each runner resolves Typer, Rich and the rest again, so a project's checks can
break with no change in the project.

### Decision

- **Every project installs the command as a uv dev dependency**, pinned to the
  release tag, with `uv.lock` committed, and runs it as
  `uv run --no-sync iglootools`.
- **A project without Python has a `pyproject.toml` for the command alone**:
  a virtual project (`package = false`) whose `[project]` table names only
  `name`, `version` and `requires-python`, with a comment saying why the file
  is there. Its `mise.toml` sets up uv as a Python project's does.
- **The uvx form goes**: `IGLOOTOOLS_VERSION`, its Renovate manager, and its
  handling in `check-pins` and `adopt`.

### Rationale

- One way to call the command lets a shared workflow use it in any project,
  so logic now copied into several workflows moves into one tested command.
- `uv.lock` pins the whole dependency tree, with hashes, everywhere.
- `check-pins` gets `uv.lock`'s record in every project, which retires both of
  ADR-001's limitations: it now verifies the workflow SHAs everywhere, and no
  variable counts as a pin by its name.
- `adopt`, `check-pins`, the Renovate presets and the guidelines lose their
  second branch.

Alternatives not pursued:

- **Keep uvx, and give each project a `mise` task that wraps either form.**
  One name for the workflows to call, but the dependencies stay unlocked and
  every tool keeps both branches.
- **Install the command with mise's `pipx:` backend.** mise would pin it in
  `mise.lock`, but only the command, not its dependencies, and a git tag is an
  awkward version for that backend.

### Consequences

- alberta-hiking-resources and network-infra carry a `pyproject.toml`,
  `uv.lock` and `.venv` that do not make them Python projects. The comment in
  `pyproject.toml` says so.
- Renovate opens lock updates for the command's dependencies in those projects
  too, grouped with their other updates.
- A workflow that calls the command sets up mise and syncs the environment
  first, which adds tens of seconds even to a run that ends up doing nothing.

**Retire this** if the command is published to PyPI with its dependencies
pinned, or if the shared workflows stop needing it.

## ADR-005 — Load only the guideline indexes into every session

**Date:** 2026-11-25 **Status:** Accepted

### Context

The plugin reached an agent through three mechanisms. A `SessionStart` hook
emitted `applying-the-guidelines.md`, `coding/general.md` and `coding/git.md` in
full, and `coding/python.md` in a project that tracks a `.py` file. A
`guidelines` skill, scoped to file paths, carried a routing table to the
`project-setup/` and `documentation/` files, the pass to make before calling a
change done, and advice on finding code. And the directory `README.md` files
routed people to the same guidelines as the skill did agents, with triggers that
differed from the skill's.

Each guideline was routed from two places that drifted, which file loaded how
had to be learned from three, and every session paid for the coding rules in
full, a commit-message rule included, whether its task touched code or not.

### Decision

- **The hook emits the indexes and nothing else of the shared guidelines**:
  `guidelines/README.md` and every directory's `README.md`, then the project's
  guidelines entry file and the list of its other guidelines files, as before.
- **The indexes are the only route.** Each lists every file under its
  directory, templates included, with the change that should send a reader
  there, as precisely as the skill's table was.
- **The `guidelines` skill goes.** What it held that no guideline did becomes
  a rule: the check before calling a change done in
  `applying-the-guidelines.md`, and finding code with the language server in
  `claude-code.md`.

### Rationale

- One route per guideline, read by people and agents alike, cannot drift from a
  second one.
- A session pays for a few small tables and the guidelines its work reaches.
- A new directory is loaded by the hook without changing it, and a new file
  needs one line, in the index a test already checks.

Alternatives not pursued:

- **Keep loading the coding guidelines in full.** They apply to most changes,
  but not to all, and the index line that sends an agent to them costs a
  sentence rather than a file.
- **Keep the skill, trimmed to a reminder to use the indexes.** Its path
  trigger re-surfaced the routing in the middle of a long session, but it was a
  second place saying the same thing, which is what this decision removes.

### Consequences

- An agent follows a rule only once it has read the file, so a session that
  skips the index's row writes code without `general.md` in front of it. The
  hook's header asks for every matching file to be read in full before the
  change.
- Nothing re-prompts in the middle of a session, as the skill's path trigger
  did; after a compaction the hook emits the indexes again.

**Retire this** if agents are seen to skip the guidelines the indexes route
them to: restore the path-scoped skill as a reminder, or load the coding
guidelines in full again.

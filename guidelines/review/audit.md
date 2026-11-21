# Auditing a Codebase

What an iglootools audit looks for, how it rates and reports what it finds, and
how the findings are fixed. Read it before running or changing an audit, fixing
a finding from an audit report, or reviewing a pull request by hand, which can
use the categories as a checklist. The plugin's `audit-pr` and `audit-full`
skills and the `auditor` agent they start follow it.

<!-- toc -->
**On this page**

- [Report problems; fix them only when asked](#report-problems-fix-them-only-when-asked)
- [Run `audit-pr` before review](#run-audit-pr-before-review)
- [Categories](#categories)
  - [File each finding under exactly one category](#file-each-finding-under-exactly-one-category)
  - [Run every category in `audit-pr`, and all but `HIST` in `audit-full`](#run-every-category-in-audit-pr-and-all-but-hist-in-audit-full)
  - [Record a broken guideline on the finding, not as `GUIDE`](#record-a-broken-guideline-on-the-finding-not-as-guide)
  - [Check whether each documented exception's retirement condition holds](#check-whether-each-documented-exceptions-retirement-condition-holds)
- [Rating a finding](#rating-a-finding)
  - [Rate severity by the impact if the finding is left alone](#rate-severity-by-the-impact-if-the-finding-is-left-alone)
  - [Mark confidence, and have a second auditor try to disprove `critical` and `high`](#mark-confidence-and-have-a-second-auditor-try-to-disprove-critical-and-high)
  - [Give an `audit-pr` finding its origin](#give-an-audit-pr-finding-its-origin)
- [The report](#the-report)
  - [Write the report to `.iglootools/audits/<timestamp>-<scope>.md`](#write-the-report-to-iglootoolsauditstimestamp-scopemd)
  - [Lay the report out for navigating](#lay-the-report-out-for-navigating)
  - [State coverage, never imply it](#state-coverage-never-imply-it)
  - [Report what an auditor notices beyond its brief](#report-what-an-auditor-notices-beyond-its-brief)
- [Fixing findings](#fixing-findings)
  - [Ask for fixes by ID, category or severity](#ask-for-fixes-by-id-category-or-severity)
  - [Fold a fix with an origin into that commit; give the rest their own](#fold-a-fix-with-an-origin-into-that-commit-give-the-rest-their-own)
  - [Describe the problem in the commit message, not the ID](#describe-the-problem-in-the-commit-message-not-the-id)
  - [Update the finding's status with the fix](#update-the-findings-status-with-the-fix)
  - [Answer a finding you disagree with by `won't fix` or a documented exception](#answer-a-finding-you-disagree-with-by-wont-fix-or-a-documented-exception)
<!-- tocstop -->

## Report problems; fix them only when asked

An audit reports problems and changes nothing. Fixing is a separate step, asked
for finding by finding ([Fixing findings](#fixing-findings)).

**Why:** each fix is then a change someone chose, not a side effect of looking.

## Run `audit-pr` before review

Run it before a pull request is reviewed, and again before it merges if the
branch has changed much. It is a judgment call, not a gate.

**Why:** problems found before review cost a fold; found after merge, a new
pull request.

## Categories

### File each finding under exactly one category

The ID prefix is the category's short name, and the categories appear in this
order in a report, functional first.

**Why:** a finding counted under two categories inflates the report and is
fixed twice.

| ID | Category | Looks for |
|---|---|---|
| `BUG` | Correctness | Logic errors, unhandled edge cases, wrong results, race conditions, off-by-one and boundary mistakes, behaviour that contradicts the docs or the tests |
| `ERR` | Error handling | Silent failures, swallowed or over-broad exceptions, errors that leave the core as prose instead of structured data, missing input or configuration validation, retries without idempotency, failure modes of external calls |
| `DATA` | Data integrity | Operations that are not idempotent, in-place mutation where the design is append-only, state stored that should be derived, destructive operations without an explicit opt-in, crash recovery that leaves partial state |
| `SEC` | Security | Interpolated text not escaped for the language it lands in (shell, terminal markup, HTML, Markdown, SQL), commands built as strings, secrets in code or logs, workflow `permissions` broader than needed, actions or tools not pinned |
| `PERF` | Performance | Needless algorithmic cost, unbounded memory, repeated I/O or subprocess calls in loops, heavy imports on the CLI start-up path |
| `TEST` | Tests | Behaviour with no test, tests that pin the implementation instead of the behaviour, patching where a decider or an injected fake would do, or outside the documented exceptions, tests that cannot fail |
| `ARCH` | Architecture and boundaries | Low cohesion or high coupling, import cycles, edges an import-linter contract forbids or should forbid, a layer-first tree, core code that imports `rich` or `typer`, abstractions with no domain concept behind them |
| `DEPS` | Dependencies and build | Unpinned versions, lock files nothing checks, pins no updater reads, unused or vulnerable dependencies, CI that diverges from local development |
| `MAINT` | Maintainability | Functions that are too long or do several things, procedural style where the guidelines ask for functional, imprecise names, duplication, dead code, comments that say *what* instead of *why*, missing type annotations |
| `OPS` | Operability and CLI experience | Missing logging or inspection tooling, no dry-run or preflight check where one is needed, commands that do not point to each other, error messages that do not say what to do next, absolute paths where relative ones are expected |
| `DOC` | Documentation | Docs that contradict the code, missing reference or contributor docs, documentation that is only in agent configuration, generated references not checked |
| `GUIDE` | Guideline conformance | Only what fits no other category: a deviation from a shared or project rule that is not documented as an exception, and a documented exception whose retirement condition now holds |
| `HIST` | Commit history | `audit-pr` only. Any rule in [git.md](../coding/git.md) the branch breaks: a commit that belongs in its own pull request, refactoring mixed with behaviour, rework or a fix-up never folded in, a message that does not match its diff |

### Run every category in `audit-pr`, and all but `HIST` in `audit-full`

Either skill takes `only:` or `skip:` to narrow the set. `audit-full` refuses
`only:HIST`.

**Why:** commit history can be fixed only on a branch, by rebasing before the
merge. On `main` it is append-only, so a full audit would pay to read every
commit for findings nobody can act on.

### Record a broken guideline on the finding, not as `GUIDE`

An overlong function is `MAINT`, and its rule cites
`coding/general.md › Keep functions short, at one level of abstraction`.
`GUIDE` holds only divergences about the rules themselves.

**Why:** filing it under `GUIDE` as well would count it twice.

### Check whether each documented exception's retirement condition holds

Every exception names the condition that retires it
([general.md](../coding/general.md#name-the-condition-that-retires-it)). The
audit checks whether it now holds: the dependency published wheels, the plan was
upgraded.

**Why:** nothing else checks.

## Rating a finding

### Rate severity by the impact if the finding is left alone

| Severity | Meaning |
|---|---|
| `critical` | Data loss, an exploitable security hole, or a broken release or build |
| `high` | Wrong behaviour a user will hit, or a failure that goes unreported |
| `medium` | A latent bug under conditions that are plausible but not routine, or debt that makes the next change in that area harder |
| `low` | Polish: a better name, a clearer message, a small simplification |

**Why:** the reader fixes in order of impact, not of discovery.

### Mark confidence, and have a second auditor try to disprove `critical` and `high`

`confirmed` when the auditor reproduced the finding or traced it end to end
through the code, `plausible` when the reasoning holds but was not traced all
the way. A `critical` or `high` finding goes to a second auditor that tries to
disprove it before it reaches the report: one that does not survive is dropped,
one that survives unproven stays `plausible`.

**Why:** the most severe findings are the ones acted on first, so a false one
costs the most.

### Give an `audit-pr` finding its origin

The commit on the branch that introduced the problem, or `pre-existing` when it
is already present at the base.

**Why:** it is the ownership test from
[git.md](../coding/git.md#fold-rework-into-the-commit-it-corrects), and it
decides how the finding is fixed.

## The report

### Write the report to `.iglootools/audits/<timestamp>-<scope>.md`

At the project root, for example
`.iglootools/audits/20261114T093012Z-pr-feat-sync-retries.md` or
`.iglootools/audits/20261114T161540Z-full.md`. The timestamp is UTC in ISO 8601
basic format. The conversation shows only the summary and the path.

**Why:** the reports list in the order they were written, and as working
documents rather than project history they stay out of Git: `.iglootools/` is
in the committed `.gitignore`
([repository.md](../project-setup/repository.md#ignore-os-and-editor-cruft-and-generated-iglootools-output-in-the-committed-gitignore)).

### Lay the report out for navigating

In GitHub, in an editor's Markdown preview, or as plain text:

```markdown
# Audit: feat/sync-retries — 2026-11-14

Scope: 7 commits, a1b2c3d..d4e5f6a · Categories: all · Auditors: 3 · Guidelines: iglootools <version>

To address findings, see [Fixing findings](<link to this section>).

## Summary

| Category | critical | high | medium | low |
|---|---|---|---|---|
| [SEC — Security](#sec) | 1 | 1 | | |
| [ERR — Error handling](#err) | | 2 | 1 | |

No findings in: BUG, DATA, PERF, TEST, ARCH, DEPS, MAINT, OPS, DOC, GUIDE, HIST.
Not audited: none.

## Index

| ID | Severity | Finding | Location | Status |
|---|---|---|---|---|
| [SEC-1](#SEC-1) | critical | `rsync` command built from a user path | [sync/rsync.py:88](../../sync/rsync.py#L88) | open |

<a id="sec"></a>
## SEC — Security

<a id="SEC-1"></a>
### SEC-1 — `rsync` command built as a string from a user-supplied path

| | |
|---|---|
| Severity | critical · confirmed |
| Location | [sync/rsync.py:88](../../sync/rsync.py#L88) |
| Origin | introduced in `3f2a1c9` |
| Rule | [coding/general.md › Escape interpolated text, or keep it apart from markup](https://github.com/iglootools/common/blob/iglootools--v<version>/guidelines/coding/general.md#escape-interpolated-text-or-keep-it-apart-from-markup) |
| Status | open |

**Scenario.** A volume named `x; rm -rf ~` runs the `rm`.

**Fix.** Build the command as an argument list.

[↑ Index](#index)
```

**Why:** a reader jumps from the summary to a finding to the line of code and
back, and cites a finding by a link that does not break.

- **IDs** are the category prefix and a number, numbered by severity within the
  category, so `SEC-1` is the most severe security finding. They are assigned
  once and never renumbered: a fixed finding keeps its ID.
- **Anchors** are explicit (`<a id="SEC-1">`), so a link survives a reworded
  title.
- **Locations** are relative to the report file (`../../<path>`) with a
  `#L<line>` anchor, so they open in an editor and at the line on GitHub.
- **Rules** link to the rule's own heading at the plugin version applied, so a
  later change to the guideline does not change what the finding cited.

### State coverage, never imply it

"No findings in" lists the categories audited that came back clean. "Not
audited" lists what was skipped and why: a category left out on request, an
auditor that failed or ran out of turns.

**Why:** a gap must never read as a clean result.

### Report what an auditor notices beyond its brief

- **In another auditor's category**: a finding like any other, `plausible`
  unless confirmed, so it can be fixed by ID.
- **Outside the scope** (another repository, paths not asked for, categories
  not run): a final "Outside the scope" list, a location and one line each, with
  no ID and no severity. Run an audit over it to turn them into findings.

**Why:** a problem dropped because it was off-brief is lost; one given a
severity nobody audited is overstated.

## Fixing findings

### Ask for fixes by ID, category or severity

"Fix SEC-1 and ERR-2", "fix all ARCH", "fix every high". Whoever fixes them
reads the report first and follows [git.md](../coding/git.md).

**Why:** each fix is a change chosen from the report, not a sweep.

### Fold a fix with an origin into that commit; give the rest their own

- **An `audit-pr` finding with an origin commit** is a problem the branch
  introduced: fold its fix into that commit with `git commit --fixup=<sha>` and
  `git rebase --autosquash`.
- **A `pre-existing` finding, or any `audit-full` finding,** gets a commit of
  its own. Mechanical fixes across one category (a rename, a formatting rule)
  can share one.

**Why:** the reviewer never reads a problem a later commit fixes, and a branch's
fixes stay apart from older code.

### Describe the problem in the commit message, not the ID

**Why:** an ID means something only inside one report, and the history outlives
it.

### Update the finding's status with the fix

In the index and in its section: `fixed in <sha>`, or `won't fix: <reason>`.
Never delete a finding from a report.

**Why:** the IDs stay stable, and the report shows what is left.

### Answer a finding you disagree with by `won't fix` or a documented exception

Never edit around the rule. Either the finding is wrong, and gets
`won't fix: <reason>`, or the project records an exception as
[Documented Exceptions](../coding/general.md#documented-exceptions) describes.

**Why:** code edited around a rule hides the disagreement that the rule or the
finding should settle.

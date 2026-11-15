# Auditing a Codebase

What an iglootools audit looks for, how it rates what it finds, and how its report is laid out
and worked through. The plugin's `audit-pr` and `audit-full` skills follow this document, and
so does the `auditor` agent they start. A person reviewing a pull request can use the
categories below as a checklist just as well.

An audit reports problems. It does not fix them. Fixing is a separate step that you ask for
finding by finding, so each fix is a change you chose (see [Fixing findings](#fixing-findings)).

## Categories

Every finding has exactly one category. The ID prefix is the category's short name, and the
categories appear in this order in a report, functional first.

| ID | Category | Looks for |
|---|---|---|
| `BUG` | Correctness | Logic errors, unhandled edge cases, wrong results, race conditions, off-by-one and boundary mistakes, behaviour that contradicts the docs or the tests |
| `ERR` | Error handling | Silent failures, swallowed or over-broad exceptions, errors that leave the core as prose instead of structured data, missing input or configuration validation, retries without idempotency, failure modes of external calls |
| `DATA` | Data integrity | Operations that are not idempotent, in-place mutation where the design is append-only, state stored that should be derived, destructive operations without an explicit opt-in, crash recovery that leaves partial state |
| `SEC` | Security | Interpolated text not escaped for the language it lands in (shell, terminal markup, HTML, Markdown, SQL), commands built as strings, secrets in code or logs, workflow `permissions` broader than needed, actions or tools not pinned |
| `PERF` | Performance | Needless algorithmic cost, unbounded memory, repeated I/O or subprocess calls in loops, heavy imports on the CLI start-up path |
| `TEST` | Tests | Behaviour with no test, tests that pin the implementation instead of the behaviour, patching where passing a value in would do, tests that cannot fail |
| `ARCH` | Architecture and boundaries | Low cohesion or high coupling, import cycles, edges an import-linter contract forbids or should forbid, a layer-first tree, core code that imports `rich` or `typer`, abstractions with no domain concept behind them |
| `DEPS` | Dependencies and build | Unpinned versions, lock files nothing checks, pins no updater reads, unused or vulnerable dependencies, CI that diverges from local development |
| `MAINT` | Maintainability | Functions that are too long or do several things, procedural style where the guidelines ask for functional, imprecise names, duplication, dead code, comments that say *what* instead of *why*, missing type annotations |
| `OPS` | Operability and CLI experience | Missing logging or inspection tooling, no dry-run or preflight check where one is needed, commands that do not point to each other, error messages that do not say what to do next, absolute paths where relative ones are expected |
| `DOC` | Documentation | Docs that contradict the code, missing reference or contributor docs, documentation that is only in agent configuration, generated references not checked |
| `GUIDE` | Guideline conformance | Only what fits no other category: a deviation from a shared or project rule that is not documented as an exception, and a documented exception whose retirement condition now holds |
| `HIST` | Commit history | `audit-pr` only. A commit that mixes refactoring and behaviour, a fix-up never folded in, a message that does not match its diff, a problem a later commit introduces and another fixes — see [git.md](../coding/git.md) |

**Which categories each audit runs.** `audit-pr` runs every category. `audit-full` runs every
category except `HIST`. Commit history is worth auditing only while it can still be changed:
on a branch, a finding is fixed by rebasing before the merge. On `main` the history is
append-only, so a full audit would pay to read every commit and produce findings nobody can act
on. Either skill takes `only:` or `skip:` to narrow the set further. `audit-full` refuses
`only:HIST`.

**A broken guideline is a field on the finding, not a category.** An overlong function is
`MAINT`, and its rule cites `coding/general.md › Function size`. Filing it under `GUIDE` as
well would count it twice. `GUIDE` holds only the divergences that are about the rules
themselves.

**Check documented exceptions too.** Every exception in a project's `docs/guidelines.md` or in
a comment names the condition that would retire it. An audit checks whether that condition now
holds — the dependency published wheels, the plan was upgraded — because nothing else does.

## Rating a finding

**Severity** is the impact if the finding is left alone:

| Severity | Meaning |
|---|---|
| `critical` | Data loss, an exploitable security hole, or a broken release or build |
| `high` | Wrong behaviour a user will hit, or a failure that goes unreported |
| `medium` | A latent bug under conditions that are plausible but not routine, or debt that makes the next change in that area harder |
| `low` | Polish: a better name, a clearer message, a small simplification |

**Confidence** is how well the finding is established: `confirmed` when the auditor reproduced
it, or traced it end to end through the code, and `plausible` when the reasoning holds but was
not traced all the way. `critical` and `high` findings go through a second auditor that tries to
disprove them before they reach the report. A finding that does not survive is dropped. One
that survives but stays unproven keeps `plausible`.

**Origin** applies to `audit-pr` only: the commit on the branch that introduced the problem, or
`pre-existing` when it is already present at the base. It is the ownership test from
[git.md](../coding/git.md#fold-rework-into-the-commit-it-corrects), and it decides how the
finding is fixed.

## The report

An audit writes a Markdown report to `.iglootools/audits/<YYYY-MM-DD>-<scope>.md` at the project
root, for example `.iglootools/audits/2026-11-14-pr-feat-sync-retries.md` or
`.iglootools/audits/2026-11-14-full.md`. Reports are working documents, not project history.
`.iglootools/` holds everything iglootools tools generate and is listed in the committed
`.gitignore` (see
[repository.md](../project-setup/repository.md#ignore-os-and-editor-cruft-and-generated-iglootools-output-in-the-committed-gitignore)). The conversation shows only the summary
and the path.

The report is built for navigating, in GitHub, in an editor's Markdown preview, or as plain
text:

```markdown
# Audit: feat/sync-retries — 2026-11-14

Scope: 7 commits, a1b2c3d..d4e5f6a · Categories: all · Auditors: 3 · Guidelines: iglootools 1.21.0

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
| Rule | [coding/general.md › Command Line](<link>) |
| Status | open |

**Scenario.** A volume named `x; rm -rf ~` runs the `rm`.

**Fix.** Build the command as an argument list.

[↑ Index](#index)
```

- **IDs** are the category prefix and a number, numbered by severity within the category, so
  `SEC-1` is the most severe security finding. They are assigned once, when the report is
  written, and never renumbered: a fixed finding keeps its ID.
- **Anchors** are explicit (`<a id="SEC-1">`) rather than derived from the heading, so a link
  to a finding survives a reworded title.
- **Locations** are relative to the report file (`../../<path>`, two levels up from
  `.iglootools/audits/`) with a `#L<line>` anchor, so they open the file in an editor and at the
  line on GitHub.
- **Rules** link to the guideline at the plugin version that was applied, so a later change to
  the guideline does not change what the finding cited.
- **Coverage is stated, not implied.** "No findings in" lists the categories that were audited
  and came back clean. "Not audited" lists what was skipped and why — a category left out on
  request, an auditor that failed or ran out of turns — so a gap never reads as a clean result.
- **Problems noticed outside the scope** go in a final "Outside the scope" list, with a location
  and one line each, instead of being dropped. They have no ID and no severity, because nobody
  audited that code. Run an audit over it to turn them into findings.

## Fixing findings

Ask for findings by ID, by category or by severity: "fix SEC-1 and ERR-2", "fix all ARCH",
"fix every high". The agent fixing them reads the report first, and follows
[git.md](../coding/git.md):

- **An `audit-pr` finding with an origin commit** is a problem the branch introduced. Its fix is
  folded into that commit with `git commit --fixup=<sha>` and `git rebase --autosquash`.
- **A `pre-existing` finding, or any `audit-full` finding,** gets a commit of its own. Mechanical
  fixes across one category (a rename, a formatting rule) can share one commit.
- **Commit messages describe the problem, not the ID.** IDs mean something only inside one
  report, while the history outlives it.
- **The report is updated with the fix.** The finding's status, in the index and in its
  section, becomes `fixed in <sha>`, or `won't fix: <reason>` when you decide against it.
  Findings are never deleted from a report, so the IDs stay stable.

A finding you disagree with is not fixed by editing around the rule. Either it is wrong, and
gets `won't fix: <reason>`, or the project records a documented exception for it, as
[Applying these guidelines](../../README.md#applying-these-guidelines) describes.

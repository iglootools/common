---
description: Audit the whole codebase, or the paths given, for bugs, error handling, data integrity, security, performance, tests, architecture and module boundaries, dependencies, maintainability, operability, documentation and divergence from the shared and project guidelines — with parallel auditor agents — and write a navigable Markdown report with an ID for every finding.
argument-hint: "[path ...] [only:CAT,CAT | skip:CAT,CAT]"
disable-model-invocation: true
---

Audit the repository as it is committed at `HEAD`. Arguments: $ARGUMENTS

## 1. Establish the scope

1. Record `git rev-parse --short HEAD`. Uncommitted changes are not audited:
   when `git status --porcelain` shows any, record them under "Not audited".
2. The scope is the paths given in the arguments, or every tracked file
   (`git ls-files`).
3. Size it: the number of tracked source files and their total lines. Generated
   files, vendored code and lock files count toward neither, though the `DEPS`
   auditor still reads lock files.

## 2. Choose the categories

All categories in `${CLAUDE_PLUGIN_ROOT}/guidelines/review/audit.md` except
`HIST`, unless the arguments narrow them with `only:` or `skip:`. `HIST` is
never run here, even when asked for: merged history cannot be rewritten, so its
findings could not be acted on. If the arguments ask for it, say so and suggest
`/iglootools:audit-pr` on the branch instead. A category left out on request
goes under "Not audited" as "not requested".

## 3. Split the work

Four auditors, each over the whole scope:

- functional `BUG, ERR, DATA`
- risk `SEC, PERF, DEPS`
- design `TEST, ARCH, MAINT`
- docs and operations `OPS, DOC, GUIDE`

When the scope is large (more than about 150 source files or 20,000 lines),
split the functional and design groups further by top-level package or
directory, the domain slices the code is organised in. Keep the total at ten
auditors or fewer. `ARCH` always sees the whole scope, because boundaries are
about edges between the slices, so with a split it moves to an auditor of its
own over every path.

## 4. Run the auditors and write the report

Follow `${CLAUDE_PLUGIN_ROOT}/audit/assemble-report.md`. The report's scope
name is `full`, or `full-<path>` when the arguments named a single path,
with `/` replaced by `-`.

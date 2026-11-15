---
description: Audit the current branch's changes against its base — bugs, error handling, data integrity, security, performance, tests, architecture, dependencies, maintainability, operability, documentation, guideline conformance and commit history — with parallel auditor agents, and write a navigable Markdown report with an ID for every finding.
argument-hint: "[base-ref] [only:CAT,CAT | skip:CAT,CAT]"
disable-model-invocation: true
---

Audit the commits on this branch that are not on its base. Arguments: $ARGUMENTS

## 1. Establish the scope

1. The base is the ref given in the arguments. Otherwise it is the pull request's base
   (`gh pr view --json baseRefName -q .baseRefName`, as `origin/<name>`), and otherwise the
   default branch (`git symbolic-ref --short refs/remotes/origin/HEAD`). Run `git fetch` first,
   so the base is current.
2. The range starts at `git merge-base <base> HEAD`. List it with
   `git log --reverse --format='%h %s' <merge-base>..HEAD` and `git diff --stat <merge-base>..HEAD`.
3. With no commits in the range, say so and stop. Uncommitted changes are not audited: when
   `git status --porcelain` shows any, record them under "Not audited".

## 2. Choose the categories

All categories in `${CLAUDE_PLUGIN_ROOT}/guidelines/review/audit.md`, `HIST` included, unless
the arguments narrow them with `only:` or `skip:`. A category left out on request goes under
"Not audited" as "not requested".

## 3. Audit the commit history yourself

`HIST` needs only the commit list, so check it here rather than in an auditor, against
`${CLAUDE_PLUGIN_ROOT}/guidelines/coding/git.md`: read `git log --reverse --stat` for the
range and each commit's diff. Look for commits that mix refactoring and behaviour, fix-ups
never folded in (`git log --format=%s <merge-base>..HEAD | grep -E '^(fixup|squash|amend)! '`),
messages that do not match their diff, and changes a later commit in the range undoes. Record
each problem as a `finding` block in the auditor's format, with `origin` set to the commit.

## 4. Split the work

- **Small range** (up to about 15 changed files and 500 changed lines): one auditor with every
  remaining category.
- **Larger range**: three auditors —
  functional `BUG, ERR, DATA`;
  risk `SEC, PERF, DEPS`;
  structure `TEST, ARCH, MAINT, OPS, DOC, GUIDE`.

Each auditor's scope is the whole range: the merge-base and head SHAs, the commit list and the
changed files.

## 5. Run the auditors and write the report

Follow `${CLAUDE_PLUGIN_ROOT}/skills/audit-pr/assemble-report.md`, adding your `HIST` findings
to the auditors' before step 4 there. The report's scope name is `pr-<branch>`, with `/` in the
branch name replaced by `-`.

# Auditing a branch range

Shared by `audit-pr` and `audit-pr-stack`, for each range they audit: the
commits from a base to a head. The skill decides the base, the head, and what
happens to a range with no commits, then follows these steps. Every category
in `${CLAUDE_PLUGIN_ROOT}/guidelines/review/audit.md` runs, `HIST` included.

## 1. List the range

`git log --reverse --format='%h %s' <base>..<head>` and
`git diff --stat <base>..<head>`.

## 2. Audit the commit history yourself

`HIST` needs only the commit list, so check it here rather than in an auditor.
Read `${CLAUDE_PLUGIN_ROOT}/guidelines/coding/git.md` in full and check the
range against every rule in it, using its own commands with `<base>` as the
base: `git log --reverse --stat` for the range, then each commit's diff. Record
each problem as a `finding` block in the auditor's format, with `origin` set to
the commit and `rule` citing the section it breaks
(`coding/git.md` › Write the subject as a Conventional Commit, and the body
as the why).

## 3. Split the work

- **Small range** (up to about 15 changed files and 500 changed lines): one
  auditor with every remaining category.
- **Larger range**: three auditors —
  functional `BUG, ERR, DATA`;
  risk `SEC, PERF, DEPS`;
  structure `TEST, ARCH, MAINT, OPS, DOC, GUIDE`.

Each auditor's scope is the whole range: the base and head SHAs, the commit
list and the changed files, with the directory that has `<head>` checked out
as the repository root.

## 4. Run the auditors and write the report

Follow `${CLAUDE_PLUGIN_ROOT}/audit/assemble-report.md`, adding your `HIST`
findings to the auditors' before its "Merge duplicates" step. The report's
scope name is `pr-<branch>`, the head's branch with `/` replaced by `-`, and
its `Scope:` line gives the range.

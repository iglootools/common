# Usage

How to run the audits and act on their reports, for two readers:

- **Anyone working in an iglootools project** with the plugin installed: the
  `/iglootools:audit-*` skills, in every section but the last.
- **Whoever maintains common**: the last section's `/audit-consistency-*`
  skills, which exist only in common's own checkout.

Installing the plugin is in [installation.md](installation.md), and how the
skills and hooks work in [internals.md](internals.md).

The guidelines themselves need nothing run: once the plugin is installed, they
load into each session and are read as a change reaches the files they govern.

<!-- toc -->
**On this page**

- [Audit a branch before review](#audit-a-branch-before-review)
- [Audit the whole codebase](#audit-the-whole-codebase)
- [Fix the findings of an audit](#fix-the-findings-of-an-audit)
- [Check the projects against common](#check-the-projects-against-common)
<!-- tocstop -->

## Audit a branch before review

On the branch, with its commits made (uncommitted changes are not audited):

```text
/iglootools:audit-pr
/iglootools:audit-pr origin/release-2.x
/iglootools:audit-pr skip:PERF,DEPS
```

The base is the pull request's, or the default branch, unless you name one.
`only:` and `skip:` take the category IDs in
[audit.md](../guidelines/review/audit.md#categories). The reply gives the
summary and the path of the report, such as
`.iglootools/audits/20261114T093012Z-pr-feat-sync-retries.md`.

When Claude opens a pull request, marks it ready or merges it with no report for
the current commit, it says so. It does not stop the command.

## Audit the whole codebase

```text
/iglootools:audit-full
/iglootools:audit-full src/nbkp/sync only:BUG,ERR
```

It audits the committed `HEAD`, or the paths given, for every category but
`HIST`, and writes `.iglootools/audits/<timestamp>-full.md`.

## Fix the findings of an audit

Ask for them by ID, category or severity, in the conversation that ran the audit
or one that reads the report:

```text
fix SEC-1 and ERR-2
fix all ARCH
fix every high
```

How each fix is committed, and how a finding you disagree with is answered, is
in [audit.md › Fixing findings](../guidelines/review/audit.md#fixing-findings).

## Check the projects against common

**Common only.** These skills belong to common's repository, not to the plugin:
they are under its `.claude/`, so they exist in a session opened in common's
checkout and nowhere else, and carry no `iglootools:` prefix. A project that
installs the plugin does not get them.

Run them every so often, so a divergence between the projects and common stays
a decision rather than an accident, and what the projects repeat moves into
common. One skill per area:

```text
/audit-consistency-guidelines
/audit-consistency-build
/audit-consistency-build nbkp photree only:DUP,PROMOTE
```

1. Check out each project beside common (`~/Workspace/iglootools/<project>`),
   on its default branch and pulled. A project on another branch or with
   uncommitted changes is still audited, and flagged in the report.
2. Run the skill. Name projects to narrow it; `only:` and `skip:` take
   `CONFLICT`, `STALE`, `DUP`, `PROMOTE` and `DIVERGE`, defined in the
   [`consistency-auditor` agent](../.claude/agents/consistency-auditor.md#categories).
3. Read the report, `.iglootools/audits/<timestamp>-consistency-<area>.md` in
   common's checkout. Its "By repository" table lists the findings each checkout
   has to fix.
4. Ask for fixes by ID, category or repository: `fix CONFLICT-1`,
   `fix all DUP in nbkp`. Each repository's fixes are a branch and a pull
   request in its own checkout.

A `PROMOTE` lands in three steps: add the rule or setting to common, release it
and adopt the release everywhere, as
[releasing-and-publishing.md](releasing-and-publishing.md#releasing) shows,
and only then remove each project's copy, so no project is ever without it.

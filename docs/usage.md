# Usage

For anyone working in an iglootools project with the plugin installed: how to
run the audits and act on their reports. Installing the plugin is in
[installation.md](installation.md), and how the skills and hooks work in
[internals.md](internals.md).

The guidelines themselves need nothing run: once the plugin is installed, they
load into each session and are read as a change reaches the files they govern.

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

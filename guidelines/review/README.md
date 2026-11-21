# Review Guidelines

How an iglootools codebase is audited against the [coding](../coding/) and
[project-setup](../project-setup/) guidelines. Read by the plugin's `audit-pr`
and `audit-full` skills and the `auditor` agent they start, and usable by hand
as a review checklist.

| File | What is in it |
|---|---|
| [audit.md](audit.md) | The audit categories, functional (`BUG`, `ERR`, `DATA`) then non-functional (`SEC`, `PERF`, `TEST`, `ARCH`, `DEPS`, `MAINT`, `OPS`, `DOC`, `GUIDE`, `HIST`); severity, confidence and origin; checking documented exceptions for their retirement condition; the layout of the Markdown report under `.iglootools/audits/`; and fixing findings by ID, following `git.md` |

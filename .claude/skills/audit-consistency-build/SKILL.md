---
description: Audit every iglootools project's build configuration (pyproject.toml, mise.toml and its tasks, the formatter and Markdown lint configs) against the shared project-setup guidelines and against each other, for undocumented departures, stale exceptions and calls, tasks that redo what the iglootools command or a shared file provides, settings several projects carry that common lacks, and choices the projects make differently, with parallel auditors, and write a report with an ID for every finding.
argument-hint: "[project ...] [only:CAT,CAT | skip:CAT,CAT]"
disable-model-invocation: true
---

Audit the consistency of the build configuration across the iglootools
repositories. Arguments: $ARGUMENTS

Follow `.claude/audit-consistency/procedure.md` with what this file sets out.
The area is `build`. Common is audited as a project too: its own build files
follow the same guidelines as every other project's.

## Files in scope

- **Common's side**: the guidelines that govern the build,
  `guidelines/project-setup/python-tooling.md`, `mise.md`, `formatting.md`,
  `iglootools-cli.md`, the `[tool.pyright]` part of `ide.md`, and the
  `renovate-*` tasks in `dependency-automation.md`; the `iglootools` command
  (`src/iglootools/`, and `uv run --no-sync iglootools --help` with each
  command group's `--help`); and the files the guidelines tell a project to
  copy from common.
- **A project's side**, common included: `pyproject.toml`, `mise.toml`,
  `mise-tasks/**`, `dprint.json`, `.rumdl.toml` and `.git-blame-ignore-revs`.
  For the `cross-project` pass only, also any `.editorconfig`, `package.json`,
  `Makefile` or `justfile`: no guideline governs them, so they matter only when
  several projects carry one.

The workflows, the Renovate configuration and the editor settings are other
areas. A `uv.lock` or `mise.lock` is generated, so it is out of scope.

## Area notes

Pass these to every auditor as the `Area` line:

```text
build. A config-level exception is a comment at the point of departure, as
applying-the-guidelines.md › Write each departure, and its reason, where a
reader will hit it says; an uncommented departure is a CONFLICT. Versions of
tools and dependencies that differ between projects are not a DIVERGE: Renovate
moves them, so a difference is usually an update not yet merged. Report a
version only when it is held back by a constraint whose stated reason no longer
holds (STALE), or pinned where no updater reads it (CONFLICT with
coding/general.md › Pin or lock every dependency, and have CI assert the lock).
Some projects have no Python code and a pyproject.toml only for the iglootools
command (ADR-004 in common's docs/architecture-decision-record.md): compare
like with like, and do not report a Python-only setting missing there. Tasks
only some projects need (demo-*, publishing) are not a DIVERGE when a guideline
ties them to a kind of project. A task that reimplements an iglootools command,
or calls one with an option the command no longer has, is a DUP or a STALE.
Ruff rules, pyright settings, task names and descriptions, and formatter
options are where divergence hides: compare them setting by setting.
```

## Passes

Start these, each with the categories chosen in the procedure's step 2 that it
owns:

| Pass | Categories | Repositories |
|---|---|---|
| `project <name>`, one per project with files in scope, common included | `CONFLICT`, `STALE`, `DUP` | common's side and that project |
| `cross-project` | `PROMOTE`, `DIVERGE` | common's side and every project, common included |

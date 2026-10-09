# Contributing

This repository is the source of the shared iglootools guidelines, not a consumer of them, so its
documentation is shaped differently from a project's: there is no `docs/` directory, and the
guidelines themselves are the reference.

## Getting started

- [CLAUDE.md](CLAUDE.md) — loading the plugin from the working tree, validating it, and running
  the `SessionStart` hook by hand
- [README.md#usage-with-claude-code](README.md#usage-with-claude-code) — how the skill and the hook
  deliver the guidelines, and working on them

## Guidelines

Edits here follow [guidelines/coding/general.md](guidelines/coding/general.md) and
[guidelines/coding/python.md](guidelines/coding/python.md), like any other iglootools project.
[README.md#applying-these-guidelines](README.md#applying-these-guidelines) is the bar a documented
exception has to meet.

## Understanding the repository

- [README.md](README.md) — what is here, and which guideline is triggered by which file
- [philosophy.md](philosophy.md) — the reasoning behind the guidelines
- [guidelines/coding/README.md](guidelines/coding/README.md) and
  [guidelines/project-setup/README.md](guidelines/project-setup/README.md) — the index of each
  half of the guidelines

## Reference

- [guidelines/project-setup/shared-workflows.md](guidelines/project-setup/shared-workflows.md) —
  the reusable workflows this repository hosts, and what a caller must declare. Changing one is
  an interface change: see [CLAUDE.md](CLAUDE.md#working-on-the-shared-workflows).

# Contributing

This repository is the source of the shared iglootools guidelines, the Claude Code plugin that
delivers them, the reusable GitHub workflows and the `iglootools` command. The guidelines
themselves are the reference, so `docs/` holds only how this repository is built and released.

## Getting started

- [docs/setup-development-environment.md](docs/setup-development-environment.md): the toolchain,
  and loading the plugin from the working tree
- [docs/building-and-testing.md](docs/building-and-testing.md): the checks and tests, the tables
  of contents, and the GitHub settings the repository depends on
- [docs/releasing-and-publishing.md](docs/releasing-and-publishing.md): changing the plugin, the
  `iglootools` command or the shared workflows without breaking the repositories that pin them,
  and cutting a release

## Guidelines

Edits here follow [guidelines/coding/general.md](guidelines/coding/general.md),
[guidelines/coding/python.md](guidelines/coding/python.md) and
[guidelines/coding/git.md](guidelines/coding/git.md), like any other iglootools project.
[Documented Exceptions](guidelines/coding/general.md#documented-exceptions) is the bar a documented
exception has to meet.

## Understanding the repository

- [README.md](README.md): what is here, and which guideline is triggered by which file
- [philosophy.md](philosophy.md): the reasoning behind the guidelines
- [docs/internals.md](docs/internals.md): how the plugin delivers the guidelines, and how the
  `iglootools` command is organized
- [guidelines/coding/README.md](guidelines/coding/README.md) and
  [guidelines/project-setup/README.md](guidelines/project-setup/README.md): the index of each
  half of the guidelines

## Reference

- [docs/installation.md](docs/installation.md): how projects install and update the plugin
- [guidelines/project-setup/shared-workflows.md](guidelines/project-setup/shared-workflows.md):
  the reusable workflows this repository hosts, and what a caller must declare
- [guidelines/project-setup/iglootools-cli.md](guidelines/project-setup/iglootools-cli.md): the
  `iglootools` command, as projects install and configure it

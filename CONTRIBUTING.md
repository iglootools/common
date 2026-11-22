# Contributing

This repository is the source of the shared iglootools guidelines, the Claude
Code plugin that delivers them, the reusable GitHub workflows and the
`iglootools` command. The guidelines themselves are the reference, so `docs/`
holds only how this repository is built and released.

## Getting started

- [docs/setup-development-environment.md](docs/setup-development-environment.md):
  follow to set up the toolchain and load the plugin from the working tree
- [docs/building-and-testing.md](docs/building-and-testing.md): follow to run
  the checks and tests and regenerate the tables of contents, and look up the
  GitHub settings the repository depends on
- [docs/releasing-and-publishing.md](docs/releasing-and-publishing.md): follow
  to change the plugin, the `iglootools` command or the shared workflows without
  breaking the repositories that pin them, and to cut a release

## Guidelines

Edits here follow [guidelines/coding/general.md](guidelines/coding/general.md),
[guidelines/coding/python.md](guidelines/coding/python.md) and
[guidelines/coding/git.md](guidelines/coding/git.md), like any other iglootools
project.
[Documented Exceptions](guidelines/applying-the-guidelines.md#documented-exceptions)
is the bar a documented exception has to meet.

## Understanding the repository

- [README.md](README.md): find what is here
- [guidelines/README.md](guidelines/README.md): find which guideline governs
  which change
- [guidelines/philosophy.md](guidelines/philosophy.md): understand the
  reasoning behind the guidelines
- [docs/internals.md](docs/internals.md): understand how the plugin delivers
  the guidelines and how the `iglootools` command is organized, before changing
  `skills/`, `hooks/` or `agents/`
- [docs/architecture-decision-record.md](docs/architecture-decision-record.md):
  find out which decisions were taken on this repository, and why

## Reference

- [docs/installation.md](docs/installation.md): follow to install the plugin
  in a project, or update it
- [guidelines/project-setup/shared-workflows.md](guidelines/project-setup/shared-workflows.md):
  know what a caller of the reusable workflows this repository hosts must
  declare
- [guidelines/project-setup/iglootools-cli.md](guidelines/project-setup/iglootools-cli.md):
  know how projects install, configure and pin the `iglootools` command

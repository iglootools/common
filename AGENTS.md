# AGENTS.md

This repository is the source of the shared iglootools guidelines, the Claude
Code plugin that delivers them, the reusable GitHub workflows every project
calls, and the `iglootools` command.

## Commands

- `mise run check-all`: every check and test CI runs. `mise tasks` lists the
  rest.
- `mise run toc` after adding, renaming or removing a heading in a Markdown
  file.

## Guidelines

Read [guidelines/coding/general.md](guidelines/coding/general.md),
[guidelines/coding/python.md](guidelines/coding/python.md) and
[guidelines/coding/git.md](guidelines/coding/git.md) before any change,
including changes to the guidelines themselves. This repository does not consume
its own plugin, so nothing else loads them.

The project-setup guidelines apply by file; read the whole file before editing
what it governs:

- `.github/workflows/`: [workflows.md](guidelines/project-setup/workflows.md)
  and [shared-workflows.md](guidelines/project-setup/shared-workflows.md).
- `pyproject.toml`, `mise.toml`, `src/`, `tests/`:
  [python-tooling.md](guidelines/project-setup/python-tooling.md) and
  [mise.md](guidelines/project-setup/mise.md).
- `renovate.json`, `renovate/`:
  [dependency-automation.md](guidelines/project-setup/dependency-automation.md).
- Any document: [documentation.md](guidelines/project-setup/documentation.md).

## Where things are

- [CONTRIBUTING.md](CONTRIBUTING.md): the index of the documents below.
- [docs/releasing-and-publishing.md](docs/releasing-and-publishing.md): how to
  change what other repositories pin (the plugin, the `iglootools` command, the
  shared workflows) without breaking them, and cutting a release.
- [docs/internals.md](docs/internals.md): how the plugin's skill and hooks
  deliver the guidelines. Read before changing `skills/`, `hooks/` or `agents/`.
- [README.md](README.md): what is here, and which guideline each kind of file
  triggers.
- [philosophy.md](philosophy.md): the reasoning behind the guidelines.

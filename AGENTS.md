# AGENTS.md

This repository is the source of the shared iglootools guidelines, the Claude
Code plugin that delivers them, the reusable GitHub workflows every project
calls, and the `iglootools` command.

## Commands

- `mise run preflight-quick`: every lint and the fast tests, before each
  commit.
- `mise run preflight`: every lint and test CI runs, every few commits and
  before review.
- `mise tasks` lists the rest.
- `mise run toc` after adding, renaming or removing a heading in a Markdown
  file, and `mise run fmt` after editing any file.

## Guidelines

Read
[guidelines/applying-the-guidelines.md](guidelines/applying-the-guidelines.md),
[guidelines/coding/general.md](guidelines/coding/general.md),
[guidelines/coding/python.md](guidelines/coding/python.md) and
[guidelines/coding/git.md](guidelines/coding/git.md) before any change,
including changes to the guidelines themselves. This repository does not consume
its own plugin, so nothing else loads them.

The other guidelines apply by file, here as in any project: find the one whose
trigger matches what you are changing through
[guidelines/README.md](guidelines/README.md) and the `README.md` of the
directory it points to, and read it in full before editing.

## Where things are

[CONTRIBUTING.md](CONTRIBUTING.md) indexes every document, including which to
read before changing the plugin's skills, hooks or agents.

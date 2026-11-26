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

Read [guidelines/README.md](guidelines/README.md) and the `README.md` of each
directory under [guidelines/](guidelines/) at the start of a session: they are
the indexes the plugin loads into every other project's sessions, and this
repository does not consume its own plugin, so nothing else loads them. Before
any change, including a change to the guidelines themselves, read in full every
file their rows send you to: here that is
[coding/general.md](guidelines/coding/general.md) and
[coding/python.md](guidelines/coding/python.md) for any code change, and
[coding/git.md](guidelines/coding/git.md) before committing.

## Where things are

[CONTRIBUTING.md](CONTRIBUTING.md) indexes every document, including which to
read before changing the plugin's skills, hooks or agents.

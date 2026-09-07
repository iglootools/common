# Common Guidelines

Shared coding guidelines for iglootools projects. This repository is the source: the files here
are what every other iglootools project consumes.

@coding.md
@python.md

These two govern every edit, including edits to the guidelines themselves, so they are imported.
`coding.md` carries the "defaults, not dogma" clause, so the exception rule arrives with it.

`project-setup.md`, `python-tooling.md` and `ide.md` are triggered by files this repository does
not have — it has no workflows, no `pyproject.toml`, no `.vscode/`. Read one when you are editing
it, and read the whole file: these guidelines are mostly about failures that are silent, so the
part you would have skipped is usually the part that names the failure.

## Why this file exists when the plugin says the same thing

[skills/](skills/) and [hooks/](hooks/) package this repository as a Claude Code plugin, and a
consumer project gets all of the above from it without importing or cloning anything.

This repository does not consume its own plugin. `${CLAUDE_PLUGIN_ROOT}` resolves to the
installed plugin directory, so an agent editing `project-setup.md` here would be pointed at
whatever commit was last installed rather than at the file in front of it. The `@` imports above
have no such problem, because the files are in this directory.

## Working on the plugin

Load it from the working tree, which is what makes `${CLAUDE_PLUGIN_ROOT}` resolve here:

```bash
claude --plugin-dir .
claude plugin validate .
```

Keep it in step with the guidelines. Renaming a guideline file, changing which files trigger it,
or adding a new one leaves `skills/guidelines/SKILL.md` or `hooks/load-always-on-guidelines.sh`
pointing at something that is no longer there — and a dispatch table that fails to fire fails
silently, which is the failure mode this repository exists to prevent.

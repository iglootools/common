# Common Guidelines

Shared coding guidelines for iglootools projects. This repository is the source: the files in
[guidelines/](guidelines/) are what every other iglootools project consumes. Everything at the
root supports them — `philosophy.md` for the reasoning, `skills/` and `hooks/` for delivery,
`scripts/` for the guidelines that ship as working code.

@guidelines/coding.md
@guidelines/python.md

These two govern every edit, including edits to the guidelines themselves, so they are imported.
`coding.md` carries the "defaults, not dogma" clause, so the exception rule arrives with it.

`guidelines/project-setup/python-tooling.md`, `guidelines/project-setup/ide.md` and
`guidelines/project-setup/claude-code.md` are triggered by files this repository does not have —
no `pyproject.toml`, no `.vscode/`, no `.claude/settings.json`. Read one when you are editing it, and read the whole file:
these guidelines are mostly about failures that are silent, so the part you would have skipped
is usually the part that names the failure.

`guidelines/project-setup/workflows.md` and `guidelines/project-setup/shared-workflows.md` are
different: this repository *does* have `.github/workflows/`,
so its GitHub Actions rules govern the files here as much as anywhere. Nothing fires that
trigger automatically, because the skill that would is delivered by a plugin this repository
does not consume, so read it yourself before editing anything under `.github/workflows/`.

## Why this file exists when the plugin says the same thing

[skills/](skills/) and [hooks/](hooks/) package this repository as a Claude Code plugin, and a
consumer project gets all of the above from it without importing or cloning anything.

This repository does not consume its own plugin. `${CLAUDE_PLUGIN_ROOT}` resolves to the
installed plugin directory, so an agent editing `guidelines/project-setup/workflows.md` here
would be pointed at
whatever commit was last installed rather than at the file in front of it. The `@` imports above
have no such problem, because the files are in this directory.

## Working on the plugin

Load it from the working tree, which is what makes `${CLAUDE_PLUGIN_ROOT}` resolve here:

```bash
claude --plugin-dir .
claude plugin validate .
```

Keep it in step with the guidelines. Renaming or moving a guideline file, changing which files
trigger it, or adding a new one leaves `skills/guidelines/SKILL.md` or
`hooks/load-always-on-guidelines.sh` pointing at something that is no longer there — and a
dispatch table that fails to fire fails silently, which is the failure mode this repository
exists to prevent. Both spell the paths out from the plugin root
(`${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/ide.md`, `$plugin_root/guidelines/coding.md`),
so no amount
of moving files is picked up for you. The hook is runnable, which is the cheapest check:

```bash
CLAUDE_PLUGIN_ROOT="$PWD" CLAUDE_PROJECT_DIR="$PWD" bash hooks/load-always-on-guidelines.sh
```

It prints a loud `ERROR:` line per file it cannot read rather than falling silent, so an empty
error count means every always-on path still resolves.

## Working on the shared workflows

`.github/workflows/reusable-check-links.yml` is consumed by the other iglootools repositories,
which pin it by commit SHA. It is therefore an interface: changing its inputs, or what a caller
has to declare for it to work, breaks every caller that has not been updated. Document the
consumer side in `guidelines/project-setup/shared-workflows.md` in the same change, and remember
that consumers do not move
until someone repoints their pin.

`check-links.yml` here calls it through a local path ref, so this repository exercises the
workflow as changed rather than as last released. Use that: dispatch it on the branch
(`gh workflow run check-links.yml --ref <branch>`) before merging a change to it.

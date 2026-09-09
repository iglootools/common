# Claude Code Guidelines

See [philosophy.md](../../philosophy.md) for the reasoning behind these guidelines, and
[Applying these guidelines](../../README.md#applying-these-guidelines) for how to deviate from
them — these are defaults, and a documented, justified exception is always allowed.

Claude Code's own configuration: which plugins a project enables, how they resolve symbols, and
what has to be committed for the team to get them. The editor half is in
[ide.md](ide.md), and the two are not interchangeable — VSCode runs Pylance for the
squiggles while the plugin runs its own pyright for Claude.

## Pyright LSP plugin

Install it in every Python project so Claude resolves symbols instead of grepping for them:

```bash
claude plugin install pyright-lsp@claude-plugins-official --scope project
```

It provides go-to-definition, find-references, hover types, document and workspace symbol search,
and call hierarchy, and it pushes diagnostics into Claude's context after each edit. Where the same
name appears in several modules, this is the difference between an answer grounded in the import
graph and one inferred from text matches.

## Multi-project workspaces

Opening several projects in one window — or reaching them as additional
working directories — does not degrade resolution, *provided each project pins its own venv* with
[`venvPath`/`venv`](ide.md#pyright-environment-resolution). This holds even when the session itself is
rooted somewhere unrelated to any of them:

- **One server can cover several projects.** There is no guarantee of one server per project, and the
  binary serving them all is whichever project's `.venv` supplied it first.
- **Imports still resolve per project.** Each file is checked against the venv its own project pins,
  so one project's dependencies never stand in for another's.
- **`goToDefinition` and `findReferences` stay correct**, including for a name defined in more than
  one project — they follow the import graph rather than the name, so a call lands in the definition
  its own project imports.

## Picking up configuration changes

The plugin's pyright server reads `[tool.pyright]` at startup, so edits to it do not reach a running
session. Restart the editor window (or the Claude Code session) and let the plugin spawn the server
itself. Do not kill the server process expecting a respawn: the plugin does not restart it on
demand, and it then reports `server is running` for a process that no longer exists, failing every
LSP request until the session is reloaded. Note that this server is distinct from the editor's
own — VSCode runs Pylance for the squiggles and the plugin runs its own pyright for Claude, so a
stale diagnostic on one side says nothing about the other.

## Sharing the plugin set with the team

`--scope project` is what makes the install shared: it writes `enabledPlugins` into the repository's
`.claude/settings.json` instead of your own `~/.claude/settings.json`, so everyone who clones the
repo gets the same plugins rather than each developer installing them by hand. **Commit that file** —
only `.claude/settings.local.json` is normally ignored, so it is easy to leave the shared half
untracked and never notice, since your own user-scope install keeps the plugin working locally.

Plugins declared this way come from the repository rather than from the developer, so they load only
after the workspace trust dialog is accepted — LSP servers in particular start only once the
workspace is trusted.

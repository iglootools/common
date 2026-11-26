# Claude Code Guidelines

Claude Code's own configuration: `.claude/settings.json` and the plugins a
project enables, and how Claude finds code with them. Read it before changing
either, and before searching a project's code for a symbol. The editor half is
in [ide.md](ide.md): VSCode runs Pylance for its diagnostics, while the plugin
runs its own pyright for Claude, so a stale diagnostic on one side says nothing
about the other.

<!-- toc -->
**On this page**

- [Install pyright-lsp at project scope in every Python project](#install-pyright-lsp-at-project-scope-in-every-python-project)
- [Find a symbol with the language server, and text with grep](#find-a-symbol-with-the-language-server-and-text-with-grep)
- [Commit `.claude/settings.json` so the team gets the plugins](#commit-claudesettingsjson-so-the-team-gets-the-plugins)
- [Restart the session after changing `[tool.pyright]`, and never kill the server](#restart-the-session-after-changing-toolpyright-and-never-kill-the-server)
<!-- tocstop -->

## Install pyright-lsp at project scope in every Python project

```bash
claude plugin install pyright-lsp@claude-plugins-official --scope project
```

**Why:** Claude then resolves symbols through the import graph instead of
grepping for names, which matters wherever the same name appears in several
modules.

- A Python project is one as
  [python-tooling.md](python-tooling.md)'s opening defines it.
- It provides go-to-definition, find-references, hover types, symbol search and
  call hierarchy, and pushes diagnostics into Claude's context after each edit.
- Resolution stays per project in a multi-project session, even one rooted
  outside every project, as long as each project pins its venv as
  [ide.md](ide.md#pin-the-venv-for-pyright-in-toolpyright) describes. One server
  may cover several projects, but each file is checked against its own
  project's venv, and `goToDefinition` follows the import graph rather than the
  name.

## Find a symbol with the language server, and text with grep

Answer symbol questions through the project's language server: where something
is defined, what references or calls it, what type it returns, what a module
contains. Use `grep` or a glob for what is not a resolvable symbol: string
literals, configuration keys, YAML and TOML, comments, filenames, or a name that
may not resolve at all.

**Why:** these projects reuse short names across modules, so only the import
graph tells which one a reference means; a text match finds them all.

- The server does not descend into installed dependencies (`site-packages`,
  `node_modules`), so a third-party definition is read from the file directly.

## Commit `.claude/settings.json` so the team gets the plugins

`--scope project` writes `enabledPlugins` into the repository's
`.claude/settings.json`. Commit it; only `.claude/settings.local.json` is
ignored.

**Why:** everyone who clones then gets the same plugins. The file is easy to
leave untracked without noticing, since a user-scope install keeps the plugin
working locally.

- Project plugins load only after the workspace trust dialog is accepted, and
  LSP servers start only once the workspace is trusted.

## Restart the session after changing `[tool.pyright]`, and never kill the server

Restart the editor window or the Claude Code session, and let the plugin spawn
the server itself.

**Why:** the server reads `[tool.pyright]` at startup. Killed, it is not
respawned: the plugin reports `server is running` for a process that no longer
exists, and every LSP request fails until the session is reloaded.

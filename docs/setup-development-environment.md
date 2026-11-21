# Setup Development Environment

<!-- toc -->
**On this page**

- [Toolchain](#toolchain)
- [Loading the plugin from the working tree](#loading-the-plugin-from-the-working-tree)
<!-- tocstop -->

## Toolchain

Install [mise](https://mise.jdx.dev/), then run `mise install` in the
repository. It installs the pinned tools — Python, uv, shellcheck, and the
formatters dprint and rumdl — and the first `mise run` creates `.venv` with the
dev dependencies. VSCode prompts for the extensions in `.vscode/extensions.json`
on opening the repository; `.vscode/settings.json` formats each file on save
with the tool `mise run fmt` uses. `mise run preflight` runs every lint and
test, which is what the `preflight` workflow runs on each pull request;
`mise tasks` lists the rest.

## Loading the plugin from the working tree

This repository does not consume its own plugin: `${CLAUDE_PLUGIN_ROOT}` would
resolve to the installed copy rather than the file being edited. Its
[AGENTS.md](../AGENTS.md) points every agent at `coding/general.md`,
`coding/python.md` and `coding/git.md` directly instead, which needs no plugin
at all.

To work on the plugin, load it from the working tree without installing it,
which is what makes `${CLAUDE_PLUGIN_ROOT}` resolve here:

```bash
claude --plugin-dir .
```

Edits to a `SKILL.md` take effect immediately; changes to `.claude-plugin/` need
`/reload-plugins`. Validate the manifests with:

```bash
claude plugin validate .
```

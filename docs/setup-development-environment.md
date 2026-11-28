# Setup Development Environment

<!-- toc -->
**On this page**

- [Toolchain](#toolchain)
- [The iglootools workspace](#the-iglootools-workspace)
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

## The iglootools workspace

`iglootools common adopt-all` works on every iglootools project checked out in
one directory, the workspace, such as `~/Workspace/iglootools`, with common's
checkout among them. Mark it with a `.iglootools-workspace` directory:

```bash
mkdir -p ~/Workspace/iglootools/.iglootools-workspace
```

adopt-all finds it from common's checkout, or any directory below the workspace,
by walking up. The directory is what to set up: it works wherever the command
runs, including in an agent's or an editor's shell, which does not read your
shell profile. It also holds the commands' cache, under `cache/`.

Optionally, to point a shell at another workspace, set `IGLOOTOOLS_WORKSPACE`
to an absolute path. It wins over the directory:

```bash
export IGLOOTOOLS_WORKSPACE=~/Workspace/iglootools
```

A variable that names no directory is an error, not a reason to fall back on the
marker directory. With neither, adopt-all stops and prints the commands, with
the directory above common's checkout filled in.

Every workspace command starts from the organization's list of repositories,
which rarely changes. The commands keep that list in
`.iglootools-workspace/cache/` and reuse it for 7 days. `--cache-ttl` changes
how old it may be (`12h`, `30m`; `0` never reuses it), and `--refresh` lists the
repositories again now, for instance just after one is created.

## Loading the plugin from the working tree

This repository does not install its own plugin. Its
[AGENTS.md](../AGENTS.md) points every agent at the guidelines in the working
tree instead; why is in
[internals.md](internals.md#how-common-applies-its-own-guidelines).

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

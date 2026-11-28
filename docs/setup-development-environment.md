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

The `iglootools workspace` commands work on every iglootools project checked out
in one directory, the workspace, such as `~/Workspace/iglootools`, with common's
checkout among them. Mark it with a `.iglootools-workspace` directory:

```bash
mkdir -p ~/Workspace/iglootools/.iglootools-workspace
```

They find it from any directory in the workspace, common's checkout included, by
walking up. The directory is what to set up: it works wherever the command runs,
including in an agent's or an editor's shell, which does not read your shell
profile. It also holds the commands' cache, under `cache/`.

Optionally, to point a shell at another workspace, set `IGLOOTOOLS_WORKSPACE`
to an absolute path. It wins over the directory:

```bash
export IGLOOTOOLS_WORKSPACE=~/Workspace/iglootools
```

A variable that names no directory is an error, not a reason to fall back on the
marker directory. With neither, a workspace command stops and prints the
commands, with the directory above where it ran filled in.

Then run `iglootools workspace sync`, the first time from common's checkout:

```bash
cd ~/Workspace/iglootools/common
uv run --no-sync iglootools workspace sync
```

It clones every repository of the organization into the workspace, and sets
the workspace itself up as a project without Python of its own is: a
`pyproject.toml` pinning the `iglootools` command to common's newest release, a
`mise.toml` with the tools and uv settings common's own `mise.toml` has at that
release, and the `uv.lock` and `.venv` that install it. From
then on the command runs from anywhere in the workspace, as in every project:

```bash
cd ~/Workspace/iglootools
iglootools workspace status
```

Inside a project, `iglootools` is still that project's own: mise sources the
`.venv` of the nearest uv project.

`iglootools workspace sync` maintains these four: each run brings them to the
newest release, rewriting `mise.toml` and `pyproject.toml` whenever it differs,
so they are always on the recommended version. Do not edit them; a change
belongs in common. mise applies the `mise.toml` in every project below it as
well, so it holds only what each project sets the same way.

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

# The `iglootools` Command Line

The build, documentation and check tools every iglootools project shares,
shipped as one command from this repository: `[tool.iglootools]`, the
`iglootools` pin, and the tasks that call it. Read it before adding or changing
either, or when fixing a bug in one of its commands.

<!-- toc -->
**On this page**

- [Use the shared command instead of a copied script](#use-the-shared-command-instead-of-a-copied-script)
- [Install it as a dev dependency, pinned to a release](#install-it-as-a-dev-dependency-pinned-to-a-release)
- [Check that every pin on common agrees](#check-that-every-pin-on-common-agrees)
- [Call it from one-line mise tasks](#call-it-from-one-line-mise-tasks)
- [Configure it in `[tool.iglootools]`, only where the defaults do not fit](#configure-it-in-tooliglootools-only-where-the-defaults-do-not-fit)
- [Try a change from a local checkout before releasing it](#try-a-change-from-a-local-checkout-before-releasing-it)
<!-- tocstop -->

## Use the shared command instead of a copied script

Where `iglootools` has a command for a job, call it rather than keeping a
script in the project.

**Why:** a fix lands once, and a project picks it up by moving one pin.

| Command | For |
|---|---|
| `iglootools docs toc` | the "On this page" lists between `<!-- toc -->` and `<!-- tocstop -->` |
| `iglootools docs cli` | the CLI reference, from the Typer app |
| `iglootools docs depgraph` | the Module Overview in `docs/architecture.md`, from pydeps |
| `iglootools python build` / `clean` | building the sdist and wheel into an emptied `dist/` / deleting build artifacts |
| `iglootools python verify-version` | failing on a wheel that carries the `0.0.0` fallback version |
| `iglootools python dev-version` | the throwaway version a Test PyPI rehearsal publishes |
| `iglootools python reinstall` | rebuilding `.venv` from the lock |
| `iglootools demo record` / `upload` | recording the demo / publishing the newest CI recording |
| `iglootools mise lock-check` | failing when the staged `mise.lock` is stale |
| `iglootools shell lint` | running shellcheck on every tracked shell script |
| `iglootools github lint` | running actionlint, with shellcheck on each `run:` script, on every tracked workflow |
| `iglootools github merge-when-green <pr>` | merging a pull request once every check has passed, then deleting its branch, on GitHub and locally |
| `iglootools github prune-branches` | deleting every branch whose latest pull request merged, on GitHub and locally; `-n` shows what it would delete |
| `iglootools github checkout-release` | checking out the release a workflow run builds, or skipping a run that has none (shared workflows, publish) |
| `iglootools github link-report` | keeping one issue open for a lychee report's broken links (the shared link checker) |
| `iglootools common adopt <version>` | moving every pin on iglootools/common to a release (`--latest` for the newest), through a pull request merged once green, in a temporary worktree that leaves the checkout as it is (`--in-place` to work in the checkout) |
| `iglootools common adopt-all <version>` | adopting a release (`--latest` for the newest) in every iglootools project of the workspace, in parallel, each in a temporary worktree, after checking all of them (from common) |
| `iglootools common release <version>` | cutting a release of common: the version bump merged once green, then both tags (in common only) |
| `iglootools common check-indexes` | failing when a shared guideline is missing from its directory's index (in common only) |
| `iglootools common check-pins` | failing when the pins on common disagree, or `adopt` would miss one |
| `iglootools workspace clone` | cloning every repository of the organization the workspace lacks, and fetching the rest |
| `iglootools workspace sync` | `clone`, then each checkout on an up-to-date default branch, merged branches deleted, the Claude Code plugins its project enables installed and current; reports what is left |
| `iglootools workspace status` | a table of every repository: its branch, uncommitted changes, standing against origin, branches, worktrees and open pull requests |
| `iglootools workspace run <task>` | running one mise task in every project at once, each logged, with a pass/fail summary |
| `iglootools workspace renovate` | the open Renovate pull requests across the organization, with what merge-when-green would do; `--merge` merges the ones it would not refuse |
| `iglootools build [<task>]` | running one of the project's mise tasks (`preflight`, `lint-*`, `test*`, `fmt`, `ci-*`, …) through `mise run`; with no task, listing them by family; `--fix` runs `fmt` before the task (`iglootools build --fix preflight`) |
| `iglootools preflight` | checking every program and credential the other commands use, with how to fix what is missing; each subsystem checks its own before its first change |

- `iglootools --help` and `iglootools <group> --help` list the options.
- Each command works on the current directory, or on `--root <dir>`. The
  `docs` commands take `--check`, which fails instead of writing.

## Install it as a dev dependency, pinned to a release

In every project, with Python or without, add it to the dev dependency group,
pinned to the release tag:

```toml
[dependency-groups]
dev = [
  "iglootools @ git+https://github.com/iglootools/common@v<version>",
]
```

**Why:** `uv.lock` then pins the command and everything it depends on, and
every project runs it the same way, as `uv run --no-sync iglootools`, so a
shared workflow can call it in any project. `docs cli` and `docs depgraph`
need it there too: they import the project's own package. Why projects without
Python have one as well is in
[ADR-004](../../docs/architecture-decision-record.md#adr-004--install-the-iglootools-command-through-uv-in-every-project-python-or-not).

- A project without Python has a `pyproject.toml` for the command alone: a
  `[project]` table with only `name`, `version = "0"` and `requires-python`,
  the dependency group, `package = false` under `[tool.uv]`, and a comment
  saying why the file is there. Its `mise.toml` sets uv up as
  [python-tooling.md › Mise and uv](python-tooling.md#mise-and-uv) describes.
  Commit `uv.lock`, and ignore `.venv/`. alberta-hiking-resources'
  [pyproject.toml](https://github.com/iglootools/alberta-hiking-resources/blob/main/pyproject.toml)
  is a working example.
- `uv.lock` records the commit the tag resolved to. Move the pin, then
  `uv lock`, as for any dependency. The version is the plugin's: the tag that
  releases the plugin releases the tools.
- Renovate moves the pin along with the workflows and presets, through a custom
  manager in the shared `base` preset, since no built-in one moves a git
  reference; the shared lock regenerator then updates `uv.lock` on its branch.
  `iglootools common adopt-all` does the same at once.
- Never run it through uvx. uvx pins the release but resolves its dependencies
  again on each machine, so a project's checks can break with no change in the
  project.

## Check that every pin on common agrees

In every project that pins a release of common, run
`iglootools common check-pins` as a `lint-common-pins` task, part of `lint`.
It finds every pin on common in the tracked files, spelled any way, and fails
when two name different releases, a SHA pin lacks its `# vX.Y.Z` comment, they
disagree with what `uv.lock` resolved, or `iglootools common adopt` would not
move one.

**Why:** the reusable workflows, the command and the Renovate presets pin the
same release in several files, and a pin written a new way would be left behind
by `adopt` without anything failing. Why the check runs offline, and the
alternatives not pursued, are in
[ADR-001](../../docs/architecture-decision-record.md#adr-001--check-the-pins-on-common-offline-trusting-uvlock-and-iglootools_versions-name).

## Call it from one-line mise tasks

Make each task a single call, named as
[mise.md](mise.md#name-tasks-by-family) describes and run through
`uv run --no-sync`
([python-tooling.md](python-tooling.md#invoke-tools-through-uv-run---no-sync-tool-in-mise-tasks-not-bare)):

```toml
[tasks.lint-depgraph]
description = "Check that the Module Overview in docs/architecture.md is up to date"
run = "uv run --no-sync iglootools docs depgraph --check"
```

**Why:** a task that calls one command needs no file under `mise-tasks/`.

- Arguments after the task name reach the command:
  `mise run toc --add docs/new.md`, with `--add` repeated for each file.

## Configure it in `[tool.iglootools]`, only where the defaults do not fit

Write a setting only where its default does not fit the project:

```toml
[tool.iglootools]
package = "nbkp"                       # default: [project] name, as an import name

[tool.iglootools.docs]
cli-module = "nbkp.cli"                # default: <package>.cli
cli-name = "nbkp"                      # default: [project] name
cli-reference = "docs/cli-reference.md"
architecture = "docs/architecture.md"
depgraph-exclude = ["nbkp.templates"]  # default: none

[tool.iglootools.demo]
script = "demo/demo.sh"
recording = "demo/demo.cast"
window-size = "160x45"
workflow = "demo.yml"
artifact = "demo-recording"
cast = "demo.cast"
readme = "README.md"
```

**Why:** every default fits nbkp and photree, so most projects write nothing,
and a setting that restates a default hides the ones that matter.

- A setting of the wrong type fails the command and names the key, rather than
  falling back to the default.

## Try a change from a local checkout before releasing it

Fix a tool in a checkout of this repository next to the project, and run the
project's command against it:

```bash
uv run --no-sync --with-editable ../common iglootools docs depgraph --check
```

Never point the dependency at a path or a branch in `pyproject.toml` to try a
change.

**Why:** a path or branch dependency edits the lock, and a commit that forgets
to undo it ships a dependency on a developer's directory.

- `--with-editable` layers the checkout over the project's environment for that
  one command, ahead of the pinned version. `pyproject.toml`, `uv.lock` and
  `.venv` stay on the pin, and the next plain `mise run` is back on it.
- Once the fix is released, move the project's pin.

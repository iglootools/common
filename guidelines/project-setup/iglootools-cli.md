# The `iglootools` Command Line

The build, documentation and check tools every iglootools project shares,
shipped as one command from this repository: `[tool.iglootools]`, the
`iglootools` pin, and the tasks that call it. Read it before adding or changing
either, or when fixing a bug in one of its commands.

<!-- toc -->
**On this page**

- [Use the shared command instead of a copied script](#use-the-shared-command-instead-of-a-copied-script)
- [Install it as a dev dependency, pinned to a release](#install-it-as-a-dev-dependency-pinned-to-a-release)
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
| `iglootools python reinstall` | rebuilding `.venv` from the lock |
| `iglootools demo record` / `upload` | recording the demo / publishing the newest CI recording |
| `iglootools mise lock-check` | failing when the staged `mise.lock` is stale |
| `iglootools shell lint` | running shellcheck on every tracked shell script |
| `iglootools github merge-when-green <pr>` | merging a pull request once every check has passed, then deleting its branch, on GitHub and locally |
| `iglootools github prune-branches` | deleting every branch whose latest pull request merged, on GitHub and locally; `-n` shows what it would delete |

- `iglootools --help` and `iglootools <group> --help` list the options.
- Each command works on the current directory, or on `--root <dir>`. The
  `docs` commands take `--check`, which fails instead of writing.

## Install it as a dev dependency, pinned to a release

In a Python project, add it to the dev dependency group, pinned to the release
tag:

```toml
[dependency-groups]
dev = [
  "iglootools @ git+https://github.com/iglootools/common@v<version>",
]
```

**Why:** `docs cli` imports the project's Typer app, and `docs depgraph`
imports the package and reads the distributions it declares, so neither works
from an isolated tool environment.

- `uv.lock` records the commit the tag resolved to. Move the pin, then
  `uv lock`, as for any dependency. The version is the plugin's: the tag that
  releases the plugin releases the tools.
- A project without Python runs the commands that do not need its environment
  (`shell lint`, `mise lock-check`) through uvx, with uv in `[tools]` and the
  release named once, in `[env]`, under a `# renovate:` comment, which the
  shared `base` preset reads. Without the comment, nothing updates the version.

  alberta-hiking-resources'
  [mise.toml](https://github.com/iglootools/alberta-hiking-resources/blob/main/mise.toml)
  is a working example: `IGLOOTOOLS` in `[env]`, and its `lint-shell` task.

  uv caches the build, so only the first run after the version moves builds
  anything.

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

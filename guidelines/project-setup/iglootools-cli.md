# The `iglootools` Command Line

The build, documentation and check tools every iglootools project shares, shipped as one
command from this repository instead of scripts each project copies. A fix lands once, and a
project picks it up by moving one pin.

<!-- toc -->
**On this page**

- [What it does](#what-it-does)
- [Install it as a dev dependency, pinned to a release](#install-it-as-a-dev-dependency-pinned-to-a-release)
- [Call it from one-line mise tasks](#call-it-from-one-line-mise-tasks)
- [Configure it in `[tool.iglootools]`, only where the defaults do not fit](#configure-it-in-tooliglootools-only-where-the-defaults-do-not-fit)
- [Try a change from a local checkout before releasing it](#try-a-change-from-a-local-checkout-before-releasing-it)
<!-- tocstop -->

## What it does

| Command | Does | Replaces |
|---|---|---|
| `iglootools docs toc [--check] [--add FILE]` | the "On this page" lists between `<!-- toc -->` and `<!-- tocstop -->`, from each file's `##` and `###` headings | — |
| `iglootools docs cli [--check]` | `docs/cli-reference.md`, from the Typer app | `build-scripts/clidocs.py` |
| `iglootools docs depgraph [--check] [-f mermaid\|ascii]` | the Module Overview in `docs/architecture.md`, from pydeps | `build-scripts/depgraph.py` |
| `iglootools python build` | `uv build --sdist --wheel` into an emptied `dist/` | `mise-tasks/build` |
| `iglootools python verify-version` | fails on a wheel carrying the `0.0.0` fallback version | `build-scripts/verifyversion.py` |
| `iglootools python clean` / `reinstall` | deletes build artifacts / rebuilds `.venv` from the lock | `mise-tasks/clean`, `mise-tasks/reinstall` |
| `iglootools demo record` / `upload` | records `demo/demo.sh` / publishes the newest CI recording | `demo/record-demo.sh`, `build-scripts/demoupload.py` |
| `iglootools mise lock-check` | fails when the staged `mise.lock` is stale | `scripts/lock-check.sh` |
| `iglootools shell lint` | shellcheck on every tracked shell script | `scripts/lint-shell.sh` |

`iglootools --help` and `iglootools <group> --help` list the options. Each command works on the
current directory, or on `--root <dir>`.

## Install it as a dev dependency, pinned to a release

In a Python project, add it to the dev dependency group, pinned to the release tag:

```toml
[dependency-groups]
dev = [
  "iglootools @ git+https://github.com/iglootools/common@v1.24.0",
]
```

`uv.lock` records the commit the tag resolved to. The version is the plugin's, so the tag that
releases the plugin releases the tools too. Move the pin, then `uv lock`, the way any dependency
moves.

It installs into the project's own environment on purpose: `docs cli` imports the project's
Typer app, and `docs depgraph` imports the package and reads which distributions it declares.
Neither works from an isolated tool environment.

A project without Python, such as a site or an infrastructure repository, runs the commands that
do not need its environment (`shell lint`, `mise lock-check`) through uvx, with uv pinned in
`[tools]` and the release named once, in `[env]`:

```toml
[tools]
uv = "0.13.7"

[env]
# renovate: datasource=github-tags depName=iglootools/common
IGLOOTOOLS_VERSION = "v1.24.0"
IGLOOTOOLS = "uvx --from git+https://github.com/iglootools/common@{{ env.IGLOOTOOLS_VERSION }} iglootools"

[tasks.lint-shell]
description = "Lint the tracked shell scripts with shellcheck"
run = "$IGLOOTOOLS shell lint"
```

The `# renovate:` comment is what keeps the version current: the shared `base` preset reads it,
since no built-in manager reads `[env]`. Without it the version is a pin nothing updates. uv
caches the build, so only the first run after the version moves builds anything.

## Call it from one-line mise tasks

Keep the project's task names and make each one a single call, run through `uv run --no-sync`
like every other tool ([python-tooling.md](python-tooling.md#invoke-tools-through-uv-run---no-sync-tool-in-mise-tasks-not-bare)):

```toml
[tasks.depgraph-check]
description = "Check that the Module Overview in docs/architecture.md is up to date"
run = "uv run --no-sync iglootools docs depgraph --check"
```

A task that only calls one command needs no file under `mise-tasks/`. Arguments after the task
name reach the command: `mise run toc --add docs/new.md`.

## Configure it in `[tool.iglootools]`, only where the defaults do not fit

Every setting has a default that fits nbkp and photree, so most projects write nothing:

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

A setting of the wrong type fails the command and names the key, rather than falling back to
the default.

## Try a change from a local checkout before releasing it

When a bug in a tool shows up while working on a project, fix it in a checkout of this
repository next to the project, and run the project's command against that checkout:

```bash
uv run --no-sync --with-editable ../common iglootools docs depgraph --check
```

`--with-editable` layers the checkout over the project's environment for that one command, and
it wins over the pinned version. Nothing in the project changes: its `pyproject.toml`, `uv.lock`
and `.venv` stay on the pin, and the next plain `mise run` is back on it. Once the fix is
merged and released, move the project's pin.

Do not point the dependency at a path or a branch in `pyproject.toml` to try a change. That
edits the lock, and a commit that forgets to undo it ships a dependency on a developer's
directory.

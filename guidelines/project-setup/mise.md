# Mise Guidelines

How an iglootools project uses [mise](https://mise.jdx.dev/) for its tasks,
whatever its language: `mise.toml`'s tasks, `mise-tasks/`, `mise.lock` and the
shell scripts it runs. Read it before adding or renaming a task, writing a file
task or a shell script, or changing how `mise.lock` is checked. Python projects
add uv and `[deps.uv]` as
[python-tooling.md](python-tooling.md#mise-and-uv) describes, and how CI
installs mise is in [workflows.md](workflows.md).

<!-- toc -->
**On this page**

- [Name tasks by family](#name-tasks-by-family)
- [Give each workflow job one `ci-*` task](#give-each-workflow-job-one-ci--task)
- [Put a multi-line task body in a file task under `mise-tasks/`](#put-a-multi-line-task-body-in-a-file-task-under-mise-tasks)
- [Lint every shell script with shellcheck](#lint-every-shell-script-with-shellcheck)
- [Check `mise.lock` in a scratch copy](#check-miselock-in-a-scratch-copy)
- [Rationale](#rationale)
  - [Put a multi-line task body in a file task under `mise-tasks/`](#put-a-multi-line-task-body-in-a-file-task-under-mise-tasks-1)
  - [Check `mise.lock` in a scratch copy](#check-miselock-in-a-scratch-copy-1)
<!-- tocstop -->

## Name tasks by family

Name every task by its family, so the name says whether it writes:

| Family | What it does | Examples |
|---|---|---|
| a writer, named for what it writes | rewrites files | `fmt`, `toc`, `clidocs`, `depgraph`, `configdocs` |
| `lint-*` | fails without writing anything | `lint-ruff`, `lint-types`, `lint-fmt`, `lint-toc`, `lint-lock-uv` |
| `test`, `test-*` | runs tests | `test`, `test-unit`, `test-integration` |
| `preflight`, `preflight-quick` | everything to run before a push | — |
| `ci-*` | one per workflow job | `ci-preflight`, `ci-build` |
| a report, named for what it shows | prints, and neither writes nor fails on what it finds | `renovate-dry-run`, `depgraph-mermaid` |

**Why:** the same command then does the same thing in every project, and one
family name can run the whole family.

- **Anything that fails without writing is a lint**: a linter (`lint-ruff`,
  `lint-shell`, `lint-markdown`), the type checker (`lint-types`), import
  contracts (`lint-boundaries`), unused code (`lint-dead-code`), a formatter run
  as a check (`lint-fmt-ruff`, `lint-fmt-dprint`), and a check that a generated
  or locked file is up to date (`lint-toc`, `lint-clidocs`, `lint-lock-mise`,
  `lint-lock-uv`). No task ends in `-check`.
- **A check of build output belongs to the build**, not to `lint`, which runs
  without one: `build-verify`, which reads the wheel `build` wrote, runs in
  `ci-build` after `build`.
- **A family name runs the family**: `fmt` runs every `fmt-*`, `lint` every
  `lint-*`, and `lint-fmt` every `lint-fmt-*`. The per-tool tasks let one check
  be run and fixed alone: `lint-fmt-dprint` fails, `fmt-dprint` fixes it.
- **A lint's description names its fix** when a writer has one:
  ``"… (fix with `mise run toc`)"``.
- **`test` runs every test suite**, and each `test-*` runs one suite or a group
  of them (`test-integration`). There is no `test-all`.
- **`preflight` runs every lint and every test**, and is what CI runs.
  `preflight-quick` runs every lint and only the fast tests, leaving out suites
  that need Docker, a real filesystem or the network. Where every test is fast,
  the two run the same thing, and `preflight-quick` still exists, so the command
  works in every project.
- **Both run `lint` and the tests in parallel**,
  `run = [{ tasks = ["lint", "test"] }]`: the tests do not depend on the lints,
  so their time hides behind the lints' instead of adding to it. mise prefixes
  each line with its task, so the interleaved output stays attributable.
- **There is no `check`, `check-all` or `format` task**: a task under an old
  name is one nobody finds by the convention.

## Give each workflow job one `ci-*` task

Each workflow job runs one `ci-*` task, which chains the project's ordinary
tasks and adds no logic of its own: `ci-preflight` (`install`, `preflight`),
`ci-build` (`install`, `build`, `build-verify`), or several jobs that split
`preflight` when its parts are slow enough to run side by side.

**Why:** a workflow job is then a single `mise run`, and CI runs exactly what a
developer can run.

- **`ci-preflight` does not build**: the build and `build-verify`, which reads
  what it wrote, are `ci-build`'s. A project that builds a package also runs
  `ci-build` on every pull request, as a `build` job in `preflight.yml`
  ([workflows.md](workflows.md#name-each-job-after-the-task-it-runs-without-ci-)),
  so each one proves the package builds and passes `build-verify`.
- **A project whose build is itself a check**, such as a static site that fails
  to build on a broken page, runs the build in `preflight`, and says so in a
  comment.
- The workflow side is in [workflows.md](workflows.md).

## Put a multi-line task body in a file task under `mise-tasks/`

A `run =` value in `mise.toml` is one command. When a task body needs a second
line (another command, a variable, a conditional, a loop), move it into an
executable file under `mise-tasks/`, which mise turns into a task named after
the file. `mise-tasks/lint-links`:

```bash
#!/usr/bin/env bash
#MISE description="Build the site and check its links offline"
#MISE depends=["install"]
set -euo pipefail

pnpm build
lychee --offline 'dist/**/*.html'
```

**Why:** a script inside a TOML string is opaque to shellcheck and the editor,
and runs under POSIX `sh`, where a syntax error does not reliably fail the
task. [Rationale](#put-a-multi-line-task-body-in-a-file-task-under-mise-tasks-1)

- **Name the file after the task.** A subdirectory namespaces it:
  `mise-tasks/ci/preflight` is the task `ci:preflight`. It runs from the project
  root, as an inline task does.
- **Put the metadata in comments**, with the fields of a `[tasks.*]` table:
  `#MISE description="..."`, `#MISE depends=["build"]`, and `sources`,
  `outputs`, `dir`, `env` and `alias` likewise. Arguments go in `#USAGE`
  comments (`#USAGE arg "<name>"`) and arrive as `$usage_name`. mise reads any
  comment line starting with `MISE` or `USAGE`, with or without a space after
  the `#`, so a comment that wraps onto a line beginning with a variable such as
  `MISE_TRUSTED_CONFIG_PATHS` makes every run warn `invalid usage spec`. Rewrap
  it.
- **Commit the file as executable** (mode `100755`). mise silently ignores one
  that is not: the task vanishes from `mise tasks ls`, and `mise run` reports it
  does not exist, with no hint why. `git ls-files -s mise-tasks` shows each
  file's mode.
- **Start with `#!/usr/bin/env bash` and `set -euo pipefail`.** Without
  `pipefail` a failure early in a pipeline is ignored, and without `-u` a
  misspelled variable expands to nothing.
- **Write for bash 3.2.** On macOS `/usr/bin/env bash` finds the system bash,
  3.2, unless something else is earlier on `PATH`, so `mapfile`, associative
  arrays or `${var,,}` work in CI and fail on a developer's machine. Under
  `set -u`, bash before 4.4 also rejects `"${array[@]}"` on an empty array.
  shellcheck does not catch these.
- **A task that only calls a script is the script.** Move `./scripts/<name>.sh`
  to `mise-tasks/<name>` rather than keeping a one-line task that runs it. Keep
  `scripts/` for programs that are not tasks.
- **Composition stays in `mise.toml`.** A task that only chains others, through
  `depends` or `run = [{ task = "..." }]`, is not a script: the `ci-*` tasks
  stay inline.

## Lint every shell script with shellcheck

Pin [shellcheck](https://www.shellcheck.net/) in `[tools]` and add a
`lint-shell` task to `lint` that runs
[`iglootools shell lint`](iglootools-cli.md):

```toml
[tools]
shellcheck = "<version>"

[tasks.lint-shell]
description = "Lint the tracked shell scripts with shellcheck"
run = "uv run --no-sync iglootools shell lint"
```

**Why:** a shell script fails at runtime on what shellcheck reports in a
second, and moving a task body into a file is only worth it if the file is
linted.

- It lints every tracked `.sh` or `.bash` file, and every file whose shebang
  runs `sh` or `bash`, which is how it finds the file tasks.
- **Run shellcheck at its default severity**, style findings included. Fix a
  finding, or disable it on the line it concerns with the reason beside it:

  ```bash
  # shellcheck disable=SC2034  # kept for the GIF conversion below, commented out for now
  GIF="$SCRIPT_DIR/demo.gif"
  ```

  A directive placed before a script's first command covers the whole file, so
  keep it next to the line it concerns. Do not disable a check project-wide in a
  `.shellcheckrc`: a broad disable hides the next instance along with this one.
- **Point shellcheck at what a script sources.** The command passes
  `--external-sources`, so a variable set for a sourced file, such as
  demo-magic's `TYPE_SPEED`, counts as used. A source path built from the
  script's directory needs a directive:

  ```bash
  # shellcheck source-path=SCRIPTDIR source=demo-magic.sh
  source "$SCRIPT_DIR/demo-magic.sh"
  ```

- **Mark vendored and generated scripts in `.gitattributes`**, with
  `linguist-vendored` or `linguist-generated`, and the command skips them. A
  copied third-party script is not the project's to restyle, and a generated one
  is fixed in its generator. GitHub reads the same attributes to leave them out
  of diffs and language statistics:

  ```gitattributes
  demo/demo-magic.sh linguist-vendored
  ```

## Check `mise.lock` in a scratch copy

Give the project a `lint-lock-mise` task that runs
[`iglootools mise lock-check`](iglootools-cli.md), and never hand-roll the
check:

```toml
[tasks.lint-lock-mise]
description = "Check that mise.lock is up to date with mise.toml"
run = "uv run --no-sync iglootools mise lock-check"
```

**Why:** mise has no read-only check, so the command regenerates the lockfile
and compares, in a scratch copy, never in place. Each of its guards was earned
by a failure, and none is guessable.
[Rationale](#check-miselock-in-a-scratch-copy-1)

- **Set `lockfile = true` in `[settings]`** in every project that commits
  `mise.lock`, so mise records per-platform checksums and URLs for every tool,
  and a fresh clone or runner installs the exact artifacts the project was
  verified against rather than whatever the version resolves to that day.
- It compares the staged files: stage `mise.toml` and `mise.lock` before
  running it.

## Rationale

### Put a multi-line task body in a file task under `mise-tasks/`

A shell script inside a TOML string is one opaque string to every tool.
shellcheck cannot lint it, the editor cannot highlight it, and it runs under
POSIX `sh`, with no `pipefail` and no `<(...)`. A file gets a shebang and
`set -euo pipefail`, can be linted and run directly, shows up in review as
code, and has room for the comments that explain it.

### Check `mise.lock` in a scratch copy

| Guard | Why |
|---|---|
| regenerates in a scratch directory | `mise lock` always writes. Undoing it with `git checkout mise.lock` discards the regenerated file the error message just said to commit |
| reads both files from the index (`git show :<file>`) | with `lockfile = true`, any tool-resolving command rewrites `mise.lock`, updating the version stanza and dropping the per-platform checksums it can no longer vouch for, which is exactly what makes `mise install --locked` fail on a fresh runner. The working copy is not a stable reference |
| removes `MISE_PYTHON_VERSION` | `mise lock` honours it, so an interpreter selected through the environment would be locked in place of the committed pin |
| treats a failing `mise lock` as an error | treated as "no difference", the check would pass in the very situation it exists to catch |

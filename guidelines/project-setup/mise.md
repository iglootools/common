# Mise Guidelines

How an iglootools project uses [mise](https://mise.jdx.dev/) for its tools and
tasks, whatever its language. Python projects add uv and `[deps.uv]` on top —
see [python-tooling.md](python-tooling.md#mise-and-uv) — and how CI installs
mise is in
[workflows.md](workflows.md).

<!-- toc -->
**On this page**

- [Tasks](#tasks)
  - [One `ci-*` task per workflow job](#one-ci--task-per-workflow-job)
  - [Put a multi-line task body in a file task under `mise-tasks/`](#put-a-multi-line-task-body-in-a-file-task-under-mise-tasks)
- [Lint every shell script with shellcheck](#lint-every-shell-script-with-shellcheck)
- [Check `mise.lock` in a scratch copy](#check-miselock-in-a-scratch-copy)
<!-- tocstop -->

## Tasks

### One `ci-*` task per workflow job

Each workflow job runs one `ci-*` task, which chains the project's ordinary
tasks and adds no logic of its own: `ci-test` (`install`, `build`, `check-all`),
`ci-build` (`install`, `build`, `build-verify`), or several jobs that split
`check-all` when its parts are slow enough to be worth running side by side. A
workflow job is then a single `mise run`, and CI runs exactly what a developer
can run. See [Keep workflows thin](workflows.md).

### Put a multi-line task body in a file task under `mise-tasks/`

A `run =` value in `mise.toml` is one command. When a task body needs a second
line — another command, a variable, a conditional, a loop — it moves into an
executable file under `mise-tasks/`, which mise turns into a task named after
the file. `mise-tasks/site-check`:

```bash
#!/usr/bin/env bash
#MISE description="Build the site and check its links"
#MISE depends=["install"]
set -euo pipefail

pnpm build
lychee --offline 'dist/**/*.html'
```

A shell script inside a TOML string is one opaque string to every tool.
shellcheck cannot lint it, the editor cannot highlight it, and it runs under
POSIX `sh`, with no `pipefail` and no `<(...)` — a syntax error there that does
*not* reliably fail the task. A file gets a shebang and `set -euo pipefail`, can
be linted with shellcheck and run directly, shows up in review as code, and has
room for the comments that explain it.

- **Name the file after the task.** A subdirectory namespaces it:
  `mise-tasks/ci/test` is the task `ci:test`. The task runs from the project
  root, as an inline one does.
- **Put the metadata in comments**, with the same fields as a `[tasks.*]` table:
  `#MISE description="..."`, `#MISE depends=["build"]`, and `sources`,
  `outputs`, `dir`, `env` and `alias` likewise. Arguments go in `#USAGE`
  comments (`#USAGE arg "<name>"`) and arrive in the script as `$usage_name`.
  mise reads a comment line that starts with `MISE` or `USAGE` as one of these,
  with or without a space after the `#`, so a comment that happens to wrap onto
  a line beginning with a variable such as `MISE_TRUSTED_CONFIG_PATHS` makes
  every run warn `invalid usage spec`. Rewrap it.
- **Commit the file as executable** (mode `100755`). mise silently ignores a
  file under `mise-tasks/` that is not: the task vanishes from `mise tasks ls`,
  and `mise run` reports it does not exist, with no hint why.
  `git ls-files -s mise-tasks` shows each file's mode.
- **Start with `#!/usr/bin/env bash` and `set -euo pipefail`.** Without
  `pipefail` a failure early in a pipeline is ignored, and without `-u` a
  misspelled variable expands to nothing.
- **Write for bash 3.2.** On macOS `/usr/bin/env bash` finds the system bash,
  3.2, unless something else is earlier on `PATH`, so a script that uses
  `mapfile`, associative arrays or `${var,,}` works in CI and fails on a
  developer's machine. Under `set -u`, bash before 4.4 also rejects
  `"${array[@]}"` on an empty array. shellcheck does not catch these.
- **A task that only calls a script is the script.** A one-line task that runs
  `./scripts/<name>.sh` is a file task with an extra hop and a second place to
  document it: move the script to `mise-tasks/<name>`. Keep `scripts/` for
  programs that are not tasks.
- **Composition stays in `mise.toml`.** A task that only chains others, through
  `depends` or `run = [{ task = "..." }]`, is not a script: the `ci-*` tasks
  stay inline.

## Lint every shell script with shellcheck

Pin [shellcheck](https://www.shellcheck.net/) in `[tools]` and add a
`lint-shell` task that runs [`iglootools shell lint`](iglootools-cli.md). Make
`check` depend on it, so CI runs it wherever it runs `check`:

```toml
[tools]
shellcheck = "0.11.0"

[tasks.lint-shell]
description = "Lint the tracked shell scripts with shellcheck"
run = "uv run --no-sync iglootools shell lint"
```

It lints every tracked shell script: each `.sh` or `.bash` file, and each file
whose shebang runs `sh` or `bash`, which is how it finds the file tasks under
`mise-tasks/`. Moving a task body into a file is what makes it lintable, and
this is the step that lints it.

- **Run shellcheck at its default severity**, which includes style findings. Fix
  a finding, or disable it on the line it concerns with the reason beside it, as
  for any other documented exception:

  ```bash
  # shellcheck disable=SC2034  # kept for the GIF conversion below, commented out for now
  GIF="$SCRIPT_DIR/demo.gif"
  ```

  A directive covers the command after it, with one exception: placed before a
  script's first command, it covers the whole file. Keep it next to the line it
  concerns. For the same reason, do not disable a check for the whole project in
  a `.shellcheckrc`: a broad disable hides the next instance along with this
  one.
- **Point shellcheck at what a script sources.** The command runs shellcheck
  with `--external-sources`, so a variable a script sets for a file it sources,
  such as demo-magic's `TYPE_SPEED`, is seen as used. A source path built from
  the script's directory needs a directive to resolve:

  ```bash
  # shellcheck source-path=SCRIPTDIR source=demo-magic.sh
  source "$SCRIPT_DIR/demo-magic.sh"
  ```

- **Mark vendored and generated scripts in `.gitattributes`**, with
  `linguist-vendored` or `linguist-generated`, and the command skips them. A
  copied third-party script, such as the demo's `demo-magic.sh`, is not the
  project's to restyle, and a generated one is fixed in its generator. GitHub
  reads the same attributes to leave those files out of diffs and language
  statistics, so one marker serves both:

  ```gitattributes
  demo/demo-magic.sh linguist-vendored
  ```

## Check `mise.lock` in a scratch copy

A `lock-check` task asserts that the committed `mise.lock` matches `mise.toml`.
mise has no read-only check for that, so the check regenerates the lockfile and
compares, and it must do so **in a scratch copy, never in place**. Run
[`iglootools mise lock-check`](iglootools-cli.md), which does:

```toml
[tasks.lock-check]
description = "Check that mise.lock is up to date with mise.toml"
run = "uv run --no-sync iglootools mise lock-check"
```

Each of its guards was earned by a failure, and none is guessable, so know them
before replacing it with something simpler:

| Guard | Why |
|---|---|
| regenerates in a scratch directory | `mise lock` always writes. Letting it write the real lockfile means undoing it afterwards, and a `git checkout mise.lock` to do so **discards the regenerated file the error message just told you to commit** |
| reads both files from the index (`git show :<file>`) | mise rewrites `mise.lock` on its own: with `lockfile = true`, any tool-resolving command updates the version stanza and drops the per-platform checksums it can no longer vouch for — which is exactly the state that makes `mise install --locked` fail on a fresh runner. The working copy is therefore not a stable reference, so "up to date" can only mean "matches what is staged". Stage `mise.toml` and `mise.lock` before running it |
| removes `MISE_PYTHON_VERSION` | `mise lock` honours it, so an interpreter selected through the environment would otherwise be locked in place of the committed pin |
| a failing `mise lock` is an error | treated as "no difference", the check would **pass** in the very situation it exists to catch |

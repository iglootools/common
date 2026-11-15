# Mise Guidelines

How an iglootools project uses [mise](https://mise.jdx.dev/) for its tools and tasks, whatever
its language. Python projects add uv and `[deps.uv]` on top — see
[python-tooling.md](python-tooling.md#mise-and-uv) — and how CI installs mise is in
[workflows.md](workflows.md).

## Tasks

### One `ci-*` task per workflow job

Each workflow job runs one `ci-*` task, which chains the project's ordinary tasks and adds no
logic of its own: `ci-test` (`install`, `build`, `check-all`), `ci-build` (`install`, `build`,
`build-verify`), or several jobs that split `check-all` when its parts are slow enough to be
worth running side by side. A workflow job is then a single `mise run`, and CI runs exactly what
a developer can run. See [Keep workflows thin](workflows.md).

### Put a multi-line task body in a file task under `mise-tasks/`

A `run =` value in `mise.toml` is one command. When a task body needs a second line — another
command, a variable, a conditional, a loop — it moves into an executable file under
`mise-tasks/`, which mise turns into a task named after the file. `mise-tasks/site-check`:

```bash
#!/usr/bin/env bash
#MISE description="Build the site and check its links"
#MISE depends=["install"]
set -euo pipefail

pnpm build
lychee --offline 'dist/**/*.html'
```

A shell script inside a TOML string is one opaque string to every tool. shellcheck cannot lint
it, the editor cannot highlight it, and it runs under POSIX `sh`, with no `pipefail` and no
`<(...)` — a syntax error there that does *not* reliably fail the task. A file gets a shebang
and `set -euo pipefail`, can be linted with shellcheck and run directly, shows up in review as
code, and has room for the comments that explain it.

- **Name the file after the task.** A subdirectory namespaces it: `mise-tasks/ci/test` is the
  task `ci:test`. The task runs from the project root, as an inline one does.
- **Put the metadata in comments**, with the same fields as a `[tasks.*]` table:
  `#MISE description="..."`, `#MISE depends=["build"]`, and `sources`, `outputs`, `dir`, `env`
  and `alias` likewise. Arguments go in `#USAGE` comments (`#USAGE arg "<name>"`) and arrive in
  the script as `$usage_name`.
- **Commit the file as executable** (mode `100755`). mise silently ignores a file under
  `mise-tasks/` that is not: the task vanishes from `mise tasks ls`, and `mise run` reports it
  does not exist, with no hint why. `git ls-files -s mise-tasks` shows each file's mode.
- **Start with `#!/usr/bin/env bash` and `set -euo pipefail`.** Without `pipefail` a failure
  early in a pipeline is ignored, and without `-u` a misspelled variable expands to nothing.
- **A task that only calls a script is the script.** A one-line task that runs
  `./scripts/<name>.sh` is a file task with an extra hop and a second place to document it:
  move the script to `mise-tasks/<name>`. Keep `scripts/` for programs that are not tasks.
- **Composition stays in `mise.toml`.** A task that only chains others, through `depends` or
  `run = [{ task = "..." }]`, is not a script: the `ci-*` tasks stay inline.

## Check `mise.lock` in a scratch copy

A `lock-check` task asserts that the committed `mise.lock` matches `mise.toml`. mise has no
read-only check for that, so the task has to regenerate the lockfile and compare, and it must
do so **in a scratch copy, never in place**. Copy
[`scripts/lock-check.sh`](../../scripts/lock-check.sh) into the project as the file task
`mise-tasks/lock-check`, executable, with no `[tasks.lock-check]` entry in `mise.toml`. Its
`#MISE description` line is part of the copy.

Every line of that script is load-bearing, and the reasons are not guessable:

| Detail | Why |
|---|---|
| regenerate in `$tmp` | `mise lock` always writes. Letting it write the real lockfile means undoing it afterwards, and a `git checkout mise.lock` to do so **discards the regenerated file the error message just told you to commit** |
| inputs from the index (`git show :<file>`) | mise rewrites `mise.lock` on its own: with `lockfile = true`, any tool-resolving command updates the version stanza and drops the per-platform checksums it can no longer vouch for — which is exactly the state that makes `mise install --locked` fail on a fresh runner. The working copy is therefore not a stable reference, so "up to date" can only mean "matches what is staged". It also makes the check immune to anything that rewrites the working `mise.toml`, such as a `mise use` in CI |
| `env -u MISE_PYTHON_VERSION` | `mise lock` honours it, so an interpreter selected through the environment would otherwise be locked in place of the committed pin |
| `set -euo pipefail` | without it a failing `mise lock` leaves the copied lockfile untouched, the `diff` finds no difference, and the check **passes** — the guard defeated by the situation it exists to catch |

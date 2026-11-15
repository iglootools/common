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

## Check `mise.lock` in a scratch copy

A `lock-check` task asserts that the committed `mise.lock` matches `mise.toml`. mise has no
read-only check for that, so the task has to regenerate the lockfile and compare, and it must
do so **in a scratch copy, never in place**. Copy
[`scripts/lock-check.sh`](../../scripts/lock-check.sh) into the project and reduce the task to
`run = "./scripts/lock-check.sh"`.

Keep it as a script rather than inlining it as a TOML string. Anything that needs
`set -euo pipefail`, a `trap` and a subshell has outgrown a `run =` value: a file gets a
shebang and therefore `pipefail` (mise tasks otherwise run under POSIX `sh`, where
`<(...)` is a syntax error that does *not* reliably fail the task), it can be invoked and
tested directly, and there is room for the reasoning below next to the code it explains.

Every line of that script is load-bearing, and the reasons are not guessable:

| Detail | Why |
|---|---|
| regenerate in `$tmp` | `mise lock` always writes. Letting it write the real lockfile means undoing it afterwards, and a `git checkout mise.lock` to do so **discards the regenerated file the error message just told you to commit** |
| inputs from the index (`git show :<file>`) | mise rewrites `mise.lock` on its own: with `lockfile = true`, any tool-resolving command updates the version stanza and drops the per-platform checksums it can no longer vouch for — which is exactly the state that makes `mise install --locked` fail on a fresh runner. The working copy is therefore not a stable reference, so "up to date" can only mean "matches what is staged". It also makes the check immune to anything that rewrites the working `mise.toml`, such as a `mise use` in CI |
| `env -u MISE_PYTHON_VERSION` | `mise lock` honours it, so an interpreter selected through the environment would otherwise be locked in place of the committed pin |
| `set -euo pipefail` | without it a failing `mise lock` leaves the copied lockfile untouched, the `diff` finds no difference, and the check **passes** — the guard defeated by the situation it exists to catch |

The threshold cuts both ways: a task body that is two or three straight-line commands with
nothing to clean up and no failure to interpret — like `reinstall` in
[python-tooling.md](python-tooling.md#reinstalling-the-environment) — stays inline,
where a reader sees what it does without opening a second file.

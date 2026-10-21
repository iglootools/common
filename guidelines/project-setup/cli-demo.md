# CLI Demo Guidelines

How an iglootools CLI ships its demo: an [asciinema](https://asciinema.org) recording of a
scripted session against seeded data, recorded by a mise task, run by CI on every release, and
embedded at the top of the README. Sibling files: [repository.md](repository.md#cli-projects)
for the rest of what a CLI project carries, [workflows.md](workflows.md) for the rules every
workflow follows, and [python-tooling.md](python-tooling.md#mise-tasks) for the task set the
demo tasks join.

The pieces, as `nbkp` and `photree` lay them out:

| Path | What it is |
|---|---|
| `demo/demo.sh` | the scripted session: the commands the viewer watches, in order |
| `demo/demo-magic.sh` | vendored [demo-magic](https://github.com/paxtonhare/demo-magic), which types each command out before running it |
| `demo/record-demo.sh` | runs `demo.sh` under `asciinema rec` and writes `demo/demo.cast` |
| `<tool> demo seed` | a command the tool itself ships, which creates the data the demo runs against |
| `mise.toml` | the `demo-*` tasks and the `asciinema`/`agg` pins |
| `.github/workflows/demo.yml` | records the demo on every release and keeps the cast as an artifact |
| `build-scripts/demoupload.py` | publishes the newest CI recording and repoints the README at it |

### Record a cast, not a GIF or a screen video

A cast is the terminal's output stream with timings, not pictures of it. The README embed plays it
back as text, so a reader can pause it and copy a command out of it; it stays small (tens to
hundreds of KB where the equivalent GIF is close to a megabyte); and it is the real output of the
real commands, colors and all, so it cannot show a screen the tool does not produce. It is also
reviewable: `demo/demo.cast` is JSON lines, and a failed run's cast can be read to see exactly
what the session printed before it died.

`agg` converts a cast to a GIF, for places that cannot embed a player. It is pinned, and
`record-demo.sh` carries the conversion, but the conversion is commented out in both projects and
nothing consumes a GIF today. Re-enable it in the script and add the GIF to the workflow's
artifact together, not one without the other.

### Script the session; do not record it by hand

A hand-recorded demo is recorded once, on one machine, with whatever typos and stale state that
session had, and nobody can re-record it the same way after the next release. `demo/demo.sh` is
the session written down: a `p` line narrates, a `pe` line types a command and runs it, and a
`pause` gives the viewer time to read the output.

```bash
# Auto-advance (no ENTER required) for scripted recording
NO_WAIT=true
TYPE_SPEED=40

p "# Show parsed configuration"
pe "nbkp config show --config $CFG"
pause 3
```

Make the session deterministic, because anything that varies between runs shows up as noise in
the recording and as a failure that only reproduces sometimes:

- Work in a fixed directory (`DEMO_DIR="/tmp/<tool>-demo"`) and `rm -rf` it first, so the paths
  on screen are the same on every recording and no earlier run leaves state behind.
- Fix the terminal size in `record-demo.sh` (`--window-size 160x45`), so the output wraps the
  same way on a developer's terminal and on a runner that has none.
- Make the script run on CI's Linux runner as well as a developer's Mac. A command the platform
  lacks gets a shim inside the script rather than a skipped step: photree's demo writes a fake
  `sips` when the real one is absent, which answers the same queries the tool makes.

Grow the script with the tool. On a major release, add scenarios for what the release
introduced, so the demo keeps showing what the tool is for rather than what it was for at 0.1.

### Seed the data with a command the tool ships

The demo runs against data created by `<tool> demo seed --base-dir "$DEMO_DIR"`, a subcommand of
the CLI itself, not by fixtures kept in `demo/` or by setup steps someone performs first. That
puts "demo commands with fake data, no manual setup" from
[Shorten every feedback loop](../../philosophy.md#shorten-every-feedback-loop) to work three
times over: the recording needs nothing prepared, a user can run the seed to try the tool without
risking their own files, and a developer gets a realistic environment in one command for manual
testing. Because it is part of the CLI, it is in `docs/cli-reference.md` like any other command.

Build the seed from the same testkit fixtures the tests use, so the demo data stays valid when
the model changes. Its sibling, `<tool> demo output`, renders every output function with fake
data, which is how a change to formatting is reviewed without reproducing each state.

`nbkp` also exposes the demo app as a separate `nbkp-demo` entry point in `[project.scripts]`;
`photree` does not. The `<tool> demo` subcommand is the convention, and a second entry point is
optional.

### Make a failing command fail the recording

A demo whose third command errors still produces a cast, and a cast that shows a stack trace
looks like a successful recording to every check that does not watch it. Two settings close
that, and both are needed:

- `demo.sh` starts with `set -euo pipefail`, so the session stops at the first failing command.
- `record-demo.sh` passes `--return` to `asciinema rec`. Without it asciinema exits 0 whatever
  the recorded command did, which is how a demo that died on its first command once recorded and
  "succeeded" on CI.

### Record through mise tasks, with the tools pinned

The demo is recorded by a mise task, so a developer and CI record it with the same command — see
"Keep workflows thin" in [workflows.md](workflows.md).

```toml
[tools]
"aqua:asciinema/asciinema" = "3.2.1"
"aqua:asciinema/agg" = "1.9.0"

[tasks.demo-record]
run = "./demo/record-demo.sh \"$(uv run --no-sync python -c 'import <pkg>; print(<pkg>.__version__)')\""

[tasks.ci-demo-record]
run = [{ task = "install" }, { task = "demo-record" }]
```

| Task | Does |
|---|---|
| `demo-record` | records `demo/demo.cast`, titled with the installed version |
| `demo-upload` | `asciinema upload demo/demo.cast` — publishes a local recording |
| `demo` | `demo-record` then `demo-upload` |
| `demo-upload-latest` | publishes the newest CI recording and repoints the README (see below) |
| `ci-demo-record` | `install` then `demo-record`; what the workflow runs |
| `ci-demo` | `install`, `demo-record`, `demo-upload`; for when CI can publish again |

The version passed to `record-demo.sh` becomes the cast title, which is what names the recording
on asciinema.org. It is read from the installed package rather than the build tool because a
VCS-derived version only exists once installed. `record-demo.sh` also puts the project's
`.venv/bin` on `PATH` explicitly: on a fresh clone mise resolves the environment before the venv
exists, so the demo would otherwise run with no CLI on the `PATH` at all.

`asciinema` and `agg` come from `mise.toml` like every other tool. What the demo itself calls
beyond the CLI — `pv` for demo-magic's simulated typing, `tree` for directory listings — is a
system package: `brew install` locally, an `apt-get install` step in the workflow.

### Keep the cast out of git

`demo/demo.cast` and `demo/demo.gif` are in `.gitignore`. A recording is a build output, one per
release, and committing it would add a few hundred KB to the history every time it is refreshed
for no reader: the README embeds the copy on asciinema.org, and CI keeps the one it recorded.

### Record the demo in CI on every release

`.github/workflows/demo.yml` runs `mise run ci-demo-record` and uploads the cast as the
`demo-recording` artifact, retained 90 days.

- **Triggers:** `push` of a `v*` tag, `workflow_run` on the `release` workflow completing,
  `workflow_dispatch` and `repository_dispatch`. The `workflow_run` trigger is not redundant with
  the tag: a tag pushed by the release workflow's `GITHUB_TOKEN` does not trigger other workflows,
  so without it a release would never record its demo.
- **Upload the artifact `if: ${{ !cancelled() }}`**, not only on success. When the demo fails, the
  cast is the only record of what the recorded session printed, since the job log shows the
  recording but not the terminal inside it. Set `if-no-files-found: error`, so a recording that
  never happened fails the job instead of uploading nothing.
- **Concurrency** uses the shared group expression from [workflows.md](workflows.md), including
  the `github.event.workflow_run.head_sha` term that this workflow's `workflow_run` trigger needs.

### Publish from a machine that can reach asciinema.org

Publishing is manual, from a developer machine:

```bash
mise run demo-upload-latest                  # newest successful run: upload, repoint README, commit
mise run demo-upload-latest -- --dry-run     # fetch and report only
mise run demo-upload-latest -- --no-commit   # update README, leave it uncommitted
mise run demo-upload-latest -- --no-readme   # upload only
```

GitHub-hosted runners have no route to asciinema.org: IPv6 has no route and the A record times
out at the TCP level, while the same address answers from outside CI. Each attempt burned about
two minutes of SYN retries and then failed the workflow after an otherwise successful release.
The upload steps are therefore commented out in `demo.yml`, with the reason above them, and
`demoupload.py` does the publishing half instead: it downloads the `demo-recording` artifact from
the newest successful run (preferring `main`, falling back to tag-triggered runs), uploads it
unchanged so the title CI recorded is kept, and commits the README change on its own.

The CI path is kept wired up so it can be re-enabled by uncommenting two steps:
`HAS_ASCIINEMA_INSTALL_ID` in the workflow's `env`, and the `ASCIINEMA_INSTALL_ID` repository
secret, which ties uploads to the maintainer's asciinema.org account. Set the secret up as part
of the repository's GitHub configuration in `docs/building-and-testing.md`:

1. Run `asciinema auth` and follow the link it prints.
2. Store the content of `~/.local/state/asciinema/install-id` in the `ASCIINEMA_INSTALL_ID` secret.

Re-enable CI publishing only once a run shows the host is reachable from a runner again.

### Embed the cast at the top of the README

The README carries the player directly under the one-paragraph description, before the first
section, so the first screen shows what the tool does:

```markdown
[![asciicast](https://asciinema.org/a/<id>.svg)](https://asciinema.org/a/<id>)
```

Keep it on one line in exactly this shape. `demoupload.py` finds the embed with a regular
expression and rewrites it in place, and it fails loudly when it cannot find one rather than
appending a second.

Refresh it on every major release, after adding the release's scenarios to `demo.sh`: run
`mise run demo-upload-latest` once the release's demo workflow has succeeded. List both steps in
the Release Process of `docs/building-and-testing.md`, because nothing else prompts them. Between major
releases, refresh when a release visibly changes what the demo shows.

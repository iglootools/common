# CLI Demo Guidelines

How an iglootools CLI ships its demo: an [asciinema](https://asciinema.org)
recording of a scripted session against seeded data, recorded by a mise task,
run by CI on every release, and embedded at the top of the README. Read it
before adding a demo to a CLI or changing `demo/`, the `demo-*` tasks or
`demo.yml`. The workflow is the shared one in
[shared-workflows.md](shared-workflows.md#call-the-shared-demo-recorder), and
the `iglootools demo` commands are in [iglootools-cli.md](iglootools-cli.md).

The pieces, as `nbkp` and `photree` lay them out:

| Path | What it is |
|---|---|
| `demo/demo.sh` | the scripted session: the commands the viewer watches, in order |
| `demo/demo-magic.sh` | vendored [demo-magic](https://github.com/paxtonhare/demo-magic), which types each command out before running it. Marked `linguist-vendored` in `.gitattributes`, so the shellcheck task skips it ([mise.md](mise.md#lint-every-shell-script-with-shellcheck)) |
| `<tool> demo seed` | a command the tool itself ships, which creates the data the demo runs against |
| `mise.toml` | the `demo-*` tasks and the `asciinema`/`agg` pins |
| `.github/workflows/demo.yml` | a stub calling the shared `reusable-demo.yml`, which records the demo on every release and keeps the cast as an artifact |
| [`iglootools demo record`](iglootools-cli.md) | runs `demo.sh` under `asciinema rec` and writes `demo/demo.cast` |
| [`iglootools demo upload`](iglootools-cli.md) | publishes the newest CI recording and repoints the README at it |

<!-- toc -->
**On this page**

- [Record a cast, not a GIF or a screen video](#record-a-cast-not-a-gif-or-a-screen-video)
- [Script the session; do not record it by hand](#script-the-session-do-not-record-it-by-hand)
- [Seed the data with a command the tool ships](#seed-the-data-with-a-command-the-tool-ships)
- [Make a failing command fail the recording](#make-a-failing-command-fail-the-recording)
- [Record through mise tasks, with the tools pinned](#record-through-mise-tasks-with-the-tools-pinned)
- [Keep the cast out of git](#keep-the-cast-out-of-git)
- [Record the demo in CI on every release](#record-the-demo-in-ci-on-every-release)
- [Publish from a machine that can reach asciinema.org](#publish-from-a-machine-that-can-reach-asciinemaorg)
- [Embed the cast at the top of the README](#embed-the-cast-at-the-top-of-the-readme)
<!-- tocstop -->

## Record a cast, not a GIF or a screen video

A cast is the terminal's output stream with timings, not pictures of it.

**Why:** the README embed plays it back as text, so a reader can pause it and
copy a command out of it. It stays small, and it is the real output of the real
commands, so it cannot show a screen the tool does not produce.

- A cast is tens to hundreds of KB, where the equivalent GIF is close to a
  megabyte.
- `demo/demo.cast` is JSON lines, so a failed run's cast shows exactly what the
  session printed before it died.
- `agg` converts a cast to a GIF, for a place that cannot embed a player. Add
  the conversion and the GIF in the workflow's artifact in the same change, not
  one without the other.

## Script the session; do not record it by hand

`demo/demo.sh` is the session written down: a `p` line narrates, a `pe` line
types a command and runs it, and a `pause` gives the viewer time to read the
output.

```bash
# Auto-advance (no ENTER required) for scripted recording
NO_WAIT=true
TYPE_SPEED=40

p "# Show parsed configuration"
pe "nbkp config show --config $CFG"
pause 3
```

**Why:** a hand-recorded demo is recorded once, with whatever typos and stale
state that session had, and nobody can re-record it the same way after the next
release.

Make the session deterministic, since anything that varies between runs shows up
as noise in the recording and as a failure that only reproduces sometimes:

- Work in a fixed directory (`DEMO_DIR="/tmp/<tool>-demo"`) and `rm -rf` it
  first, so the paths on screen are the same on every recording and no earlier
  run leaves state behind.
- Fix the terminal size (`iglootools demo record` passes
  `--window-size 160x45`), so the output wraps the same way on a developer's
  terminal and on a runner that has none.
- Make the script run on CI's Linux runner as well as a developer's Mac. A
  command the platform lacks gets a shim inside the script rather than a skipped
  step: photree's demo writes a fake `sips` when the real one is absent.
- Grow the script with the tool. On a major release, add scenarios for what the
  release introduced, so the demo keeps showing what the tool is for.

## Seed the data with a command the tool ships

The demo runs against data created by `<tool> demo seed --base-dir "$DEMO_DIR"`,
a subcommand of the CLI, not by fixtures kept in `demo/` or by setup steps
someone performs first.

**Why:** the recording needs nothing prepared, a user can try the tool without
risking their own files, and a developer gets a realistic environment in one
command, as
[Shorten every feedback loop](../philosophy.md#shorten-every-feedback-loop)
asks.

- Being part of the CLI, it is in `docs/cli-reference.md` like any other
  command.
- Build the seed from the same testkit fixtures the tests use, so the demo data
  stays valid when the model changes.
- Its sibling, `<tool> demo output`, renders every output function with fake
  data, so a change to formatting is reviewed without reproducing each state.

## Make a failing command fail the recording

`demo.sh` starts with `set -euo pipefail`, and `iglootools demo record` passes
`--return` to `asciinema rec`. Both are needed.

**Why:** a demo whose third command errors still produces a cast, and without
`--return` asciinema exits 0 whatever the recorded command did, so a cast of a
stack trace passes every check that does not watch it.

## Record through mise tasks, with the tools pinned

The demo is recorded by a mise task, named as
[mise.md › Name tasks by family](mise.md#name-tasks-by-family) describes.

**Why:** a developer and CI then record it with the same command, as
[workflows.md](workflows.md#keep-workflows-thin-set-up-the-toolchain-then-run-one-ci--task)
asks.

| Task | Does |
|---|---|
| `demo-record` | `iglootools demo record`: records `demo/demo.cast`, titled with the installed version |
| `demo-upload` | `asciinema upload demo/demo.cast`: publishes a local recording |
| `demo` | `demo-record` then `demo-upload` |
| `demo-upload-latest` | `iglootools demo upload`: publishes the newest CI recording and repoints the README |
| `ci-demo-record` | `install` then `demo-record`; what the shared workflow runs |

- `asciinema` and `agg` are pinned in `mise.toml` (`aqua:asciinema/asciinema`,
  `aqua:asciinema/agg`) like every other tool.
- What the session calls beyond the CLI, such as `pv` for demo-magic's typing
  and `tree` for directory listings, comes from mise where a lockable backend
  has it (nbkp pins `conda:pv`), and otherwise is a system package:
  `brew install` locally and the `apt-packages` input of the shared workflow in
  CI.
- A `demo-preflight` task that `demo-record` depends on, checking those tools
  are installed, turns a missing tool into a clear error instead of a failure
  visible only inside the cast (nbkp has one).

## Keep the cast out of git

`demo/demo.cast` and `demo/demo.gif` are in `.gitignore`.

**Why:** a recording is a build output, one per release, and committing it adds
a few hundred KB to the history at every refresh for no reader: the README
embeds the copy on asciinema.org, and CI keeps the one it recorded.

## Record the demo in CI on every release

`demo.yml` calls the shared demo recorder, as
[shared-workflows.md](shared-workflows.md#call-the-shared-demo-recorder) shows.
Its triggers, guards and artifact are in
[reusable-demo.yml](../../.github/workflows/reusable-demo.yml).

**Why:** every release then has a recording made from its own tagged commit,
ready to publish, without anyone remembering to make one.

- It listens for the `release` run as well as `v*` tags, for the reason
  [pypi-publishing.md](pypi-publishing.md#chain-publish-to-release-with-workflow_run-and-also-listen-for-v-tags)
  gives.

## Publish from a machine that can reach asciinema.org

Publishing is manual, from a developer machine:

```bash
mise run demo-upload-latest                  # newest successful run: upload, repoint README, commit
mise run demo-upload-latest -- --dry-run     # fetch and report only
mise run demo-upload-latest -- --no-commit   # update README, leave it uncommitted
mise run demo-upload-latest -- --no-readme   # upload only
```

**Why:** GitHub-hosted runners cannot reach asciinema.org, and each attempt
failed an otherwise successful release after minutes of retries;
`reusable-demo.yml`'s header has the details.

- `iglootools demo upload` downloads the `demo-recording` artifact from the
  newest successful run (preferring `main`, falling back to tag-triggered
  runs), uploads it unchanged so the title CI recorded is kept, and commits the
  README change on its own.
- Run `asciinema auth` once on the publishing machine and follow the link it
  prints, so uploads belong to the maintainer's asciinema.org account.
- Publish from CI again only once a run shows the host is reachable from a
  runner.

## Embed the cast at the top of the README

The README carries the player directly under the one-paragraph description,
before the first section, on one line in exactly this shape:

```markdown
[![asciicast](https://asciinema.org/a/<id>.svg)](https://asciinema.org/a/<id>)
```

**Why:** the first screen shows what the tool does. `iglootools demo upload`
finds the embed with a regular expression and rewrites it in place, failing
loudly rather than appending a second when it cannot find one.

- Refresh it on every major release, after adding the release's scenarios to
  `demo.sh`: run `mise run demo-upload-latest` once the release's demo workflow
  has succeeded.
- List both steps in the release process in `docs/releasing-and-publishing.md`,
  because nothing else prompts them.
- Between major releases, refresh when a release visibly changes what the demo
  shows.

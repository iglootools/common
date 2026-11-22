# Internals

How the plugin delivers the guidelines to Claude Code: the `guidelines` skill,
the audit skills, and the hook that loads the always-on guidelines. Installing
it is in
[installation.md](installation.md).

<!-- toc -->
**On this page**

- [Two delivery mechanisms](#two-delivery-mechanisms)
- [The `guidelines` skill](#the-guidelines-skill)
- [Auditing](#auditing)
- [The ones that load in every session](#the-ones-that-load-in-every-session)
- [The `iglootools` command](#the-iglootools-command)
- [Checking the pins on common](#checking-the-pins-on-common)
- [Adopting a release everywhere](#adopting-a-release-everywhere)
<!-- tocstop -->

## Two delivery mechanisms

The guidelines split into two kinds, and the plugin delivers each by the
mechanism that fits. `coding/general.md`, `coding/python.md` and `coding/git.md`
govern every edit, so a `SessionStart` hook puts them in context from the start
(`coding/python.md` only in a project with a `pyproject.toml`).
The rest are triggered by a specific file, so a skill reads them only when a
change reaches the files they govern.

## The `guidelines` skill

This repository is also a Claude Code plugin. Its main skill, `guidelines`,
restates no guideline: its body says which file to read and when, so the
guidelines stay in one place, readable by humans and agents alike. It does three
things — dispatches to the guideline file a change reaches, carries the pass to
make before calling the change done, and walks the procedure for recording a
documented exception where a rule does not fit.

Guideline files are read on demand where possible: the skill reads only the one
a change actually reaches, and an ordinary code change reads none of them.

It also enforces the philosophy the guidelines rest on: check the work against
them before calling it done, and document a deviation rather than drift from a
rule silently. See
[Documented Exceptions](../guidelines/applying-the-guidelines.md#documented-exceptions).

## Auditing

`/iglootools:audit-pr` audits the current branch against its base, and
`/iglootools:audit-full` audits the whole codebase or the paths given. Both run
only when you type them, because an audit starts several agents and costs
accordingly. Each splits the categories in
[guidelines/review/audit.md](../guidelines/review/audit.md) across parallel
`auditor` agents, sends the `critical` and `high` findings to a second auditor
that tries to disprove them, and writes a Markdown report to
`.iglootools/audits/`. Every finding gets an ID such as `SEC-1`, so you can ask
for exactly the fixes you want: "fix SEC-1 and ERR-2", "fix all ARCH".

The skills run in the main conversation rather than in a subagent of their own,
for two reasons. The findings have to be in the conversation that will fix them.
And the fan-out needs no nested delegation when the main conversation starts the
auditors itself.

The auditors do not see what the `SessionStart` hook emits, because a subagent
does not receive it, so the `auditor` agent reads the guidelines itself.

When Claude is about to open a pull request, mark it ready or merge it,
[hooks/remind-audit-pr.sh](../hooks/remind-audit-pr.sh) reminds the user if no
report under `.iglootools/audits/` covers the current commit. It does not block
the command, since an audit is a judgment call rather than a gate, and pull
requests opened outside Claude get no reminder.

## The ones that load in every session

Some guidelines govern every edit rather than one kind of file —
`coding/general.md`, `coding/python.md` and `coding/git.md` today.
`coding/git.md` has no file to trigger it at all: it applies at the moment of
committing, which is exactly when an agent fixing a lint failure would not stop
to look for a skill. Those are not skills: a skill is model-invoked, which is
right for a guideline triggered by a file and wrong for one that applies to
everything. They are delivered instead by
[hooks/load-always-on-guidelines.sh](../hooks/load-always-on-guidelines.sh),
which runs on `SessionStart` and whose stdout becomes context the agent sees.
Another such guideline is added to that script.

The hook fires on `startup`, `clear` and `compact`, and deliberately not on
`resume` or `fork`: a resumed or forked session still carries the earlier
injection in its transcript, while a compacted one may have had it summarized
away.

Emission can be conditional: `coding/python.md` goes out only when the project
has a `pyproject.toml`, so a project with no Python does not pay for it. The
project's guidelines entry file goes out last, when it exists
(`docs/guidelines.md`, or `docs/guidelines/README.md` when the guidelines are
split), under a heading that says it overrides the shared rules above it: an
override the agent only reads on demand is one it does not have in front of it
while writing the code it overrides. Every other `guidelines.md` and
`guidelines/**/*.md` the project tracks is listed after it by path, with what it
governs, and read when a change reaches that: loading them all would make every
session pay for every area's conventions. If a file cannot be read, the hook
says so in the injected text rather than emitting nothing, because a guideline
that failed to load must not be indistinguishable from one that does not apply.

## The `iglootools` command

The shared command lives in `src/iglootools/`, one package per domain (`docs`,
`python`, `demo`, `mise`, `shell`), each with a `cli` module that is the only
place it prints. Its tests are under `tests/`. How projects install, configure
and pin it, and how to try a change against one of them before releasing, is in
[guidelines/project-setup/iglootools-cli.md](../guidelines/project-setup/iglootools-cli.md).

## Checking the pins on common

A project pins a release of common in several files, and how depends on whether
it is a Python project. `iglootools common adopt` moves every pin to a release,
looking in every tracked file that mentions common rather than in a list of
files, and `iglootools common check-pins`, run offline as each project's
`lint-common-pins` task, keeps them in agreement between adopts.

| | Python projects (nbkp, photree) | Projects without Python (alberta-hiking-resources, network-infra) |
|---|---|---|
| The `iglootools` command | a dev dependency in `pyproject.toml`, `iglootools @ git+https://github.com/iglootools/common@v<version>`, run as `uv run --no-sync iglootools …` | run through uvx, as `$IGLOOTOOLS …`: `mise.toml` names the release once in `IGLOOTOOLS_VERSION`, and builds `IGLOOTOOLS = "uvx --from git+https://github.com/iglootools/common@{{ env.IGLOOTOOLS_VERSION }} iglootools"` from it |
| Where the tag's commit is recorded | `uv.lock`: `common?rev=v<version>#<commit>`, written when `uv lock` resolved the tag | nowhere: uvx resolves the tag when it first builds the command, and caches the build, but no committed file keeps the commit |
| Other pins | the reusable workflows (by SHA, with `# v<version>`), the `base` and `python` Renovate presets | the reusable workflows they call, the `base` Renovate preset |
| What keeps the release current | Renovate, through its own manager for the dependency and the presets; adopt | Renovate, through the shared `base` preset's manager, which reads the `# renovate:` comment above `IGLOOTOOLS_VERSION`; adopt |
| What `adopt` does | moves the pins, then regenerates `uv.lock`, which records the new commit | moves the pins, `IGLOOTOOLS_VERSION` among them; there is no lock to regenerate |
| What `check-pins` verifies | every pin names one release, adopt would move each, every SHA pin has its tag comment, and the release and every workflow SHA match `uv.lock`'s record | the same, except the workflow SHAs: with no record of the tag's commit, it cannot check them offline |

Two limitations follow from the second column, both accepted in
[ADR-001](architecture-decision-record.md#adr-001--check-the-pins-on-common-offline-trusting-uvlock-and-iglootools_versions-name),
which records the alternatives too:

- In a project without Python, a workflow SHA edited by hand to the wrong
  commit passes, as long as its `# vX.Y.Z` comment is right. adopt and Renovate
  always write the right one.
- `IGLOOTOOLS_VERSION` counts as a pin on common by its name; the check does not
  read the `IGLOOTOOLS` alias or the Renovate comment beside it.

## Adopting a release everywhere

`iglootools common adopt-all` runs from common's checkout and treats the
directory it sits in as the workspace. It takes every git checkout there whose
`origin` is a repository of the iglootools organization and that pins common,
narrowed by `--only` and `--exclude`, and passes over the rest with the reason.
A repository of the organization whose `renovate.json` mentions common, found
through GitHub's code search, but which has no checkout in the workspace, fails
the run: a project nobody cloned would otherwise be silently left on the old
release.

Before changing any project it checks all of them: no changes or untracked
files, `origin` reachable with git and ssh unable to prompt, and a local default
branch GitHub already has every commit of. One problem anywhere stops the run
while nothing has happened.

Then each project runs `common adopt` in a thread of its own. The work is almost
all waiting, on CI and on GitHub's API, so threads cost nothing and keep the
tested, synchronous adopt as it is. Each project's waits go through a sleep that
an interrupt cancels, so Ctrl-C stops every project at its next poll; pushes
take turns behind one lock, so two credential helpers never run at once; and a
failure in one project leaves the others running. adopt is safe to run again,
picking up from the pull request or branch an earlier run left, so rerunning
adopt-all after an interruption or a failure resumes each project where it
stopped. Progress is a live table in a terminal and lines prefixed with the
project's name elsewhere, from the same events.

**No project depends on another**, so the projects run in any order and at once.
If one ever did, for instance a project consuming another's package, adopt-all
would need an order: adopt and release the dependency first, then the projects
that depend on it, which turns the single parallel step into stages.

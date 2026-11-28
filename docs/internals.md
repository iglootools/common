# Internals

How the plugin delivers the guidelines to Claude Code: the hook that loads the
guideline indexes, and the audit skills. Installing
it is in [installation.md](installation.md), and running the audits in
[usage.md](usage.md).

<!-- toc -->
**On this page**

- [Indexes always, guidelines on demand](#indexes-always-guidelines-on-demand)
- [Auditing](#auditing)
- [Auditing consistency across the projects](#auditing-consistency-across-the-projects)
- [The hook that loads the indexes](#the-hook-that-loads-the-indexes)
- [How common applies its own guidelines](#how-common-applies-its-own-guidelines)
  - [Why common does not install its own plugin](#why-common-does-not-install-its-own-plugin)
- [The `iglootools` command](#the-iglootools-command)
- [Checking the pins on common](#checking-the-pins-on-common)
- [Adopting a release everywhere](#adopting-a-release-everywhere)
<!-- tocstop -->

## Indexes always, guidelines on demand

Every session starts with the guidelines' indexes in context, and none of the
guidelines themselves: `guidelines/README.md` and each directory's `README.md`,
each a table of which file to read for which change. The agent reads a
guideline when a change matches its row, `coding/general.md` for any code
change and `coding/git.md` before committing among them, and it reads the whole
file. A session pays for the map and for the files its work reaches, not for
every rule.

The indexes are the only route, for people and agents alike: no skill or table
in the plugin repeats them, so a trigger is written once, in the row that
carries it. That is why a row names the files or the change precisely enough to
recognize it, and why `mise run lint-guideline-indexes` fails on a file missing
from its directory's index. Why the plugin went this way, rather than loading
the coding guidelines in full or routing through a skill, is
[ADR-005](architecture-decision-record.md#adr-005--load-only-the-guideline-indexes-into-every-session).

Guidance that is not a rule, such as when to read which file, goes in the
hook's own header rather than in a guideline, since a guideline is written for
a person.

## Auditing

`audit-pr` and `audit-full`, run as [usage.md](usage.md) shows, each split the
categories in [guidelines/review/audit.md](../guidelines/review/audit.md)
across parallel `auditor` agents, send the `critical` and `high` findings to a
second auditor that tries to disprove them, and write a Markdown report to
`.iglootools/audits/`. Both set `disable-model-invocation`, so they run only
when typed, because an audit starts several agents and costs accordingly. The
report-writing steps they share are in
[skills/audit-pr/assemble-report.md](../skills/audit-pr/assemble-report.md).

The skills run in the main conversation rather than in a subagent of their own,
for two reasons. The findings have to be in the conversation that will fix them.
And the fan-out needs no nested delegation when the main conversation starts the
auditors itself.

The auditors do not see what the `SessionStart` hook emits, because a subagent
does not receive it, so the `auditor` agent reads the guidelines itself.

When Claude is about to open a pull request, mark it ready or merge it,
[hooks/remind-audit-pr.sh](../hooks/remind-audit-pr.sh) reminds the user if no
report under `.iglootools/audits/` covers the current commit: it takes the SHA
after `..` in each report's `Scope:` line, the head an `audit-pr` report
audited. It does not block the command, since an audit is a judgment call rather
than a gate, and pull requests opened outside Claude get no reminder.

When Claude is about to push a branch other than the default one,
[hooks/remind-clean-branch.sh](../hooks/remind-clean-branch.sh) asks it to read
the branch as its reviewer will and fold any rework first, as
[git.md](../guidelines/coding/git.md#rebase-and-clean-up-before-asking-for-review)
says. That pass is easiest to skip when adding commits to a pull request
already open, since nothing else marks the moment. Common wires the same script
in its own `.claude/settings.json`, as it does not load its own plugin; that
file holds this hook and nothing else.

## Auditing consistency across the projects

The `audit-consistency-*` skills, run as
[usage.md](usage.md#check-the-projects-against-common) shows, compare one area
of common with the same area in every iglootools project checked out beside it,
and the projects with each other.

They are skills of this repository, under `.claude/`, not of the plugin: they
run from common's checkout, read its siblings, and their fixes start in common,
so they would mean nothing in a project that installs the plugin.

Each skill names its area's files, the notes its auditors need, and how the
work splits into passes: common against itself, each project against common,
and the projects against each other. Everything else is shared: the
[procedure](../.claude/audit-consistency/procedure.md) for finding the
checkouts, running and verifying the auditors and writing the report, and the
[`consistency-auditor` agent](../.claude/agents/consistency-auditor.md) with
the categories and the format it returns. Another area, such as the workflows,
is one more `audit-consistency-<area>` skill.

Their reports go to `.iglootools/audits/` beside the plugin's, with no `Scope:`
line, which the reminder hook above would read as an `audit-pr` of that commit.

## The hook that loads the indexes

[hooks/load-guideline-indexes.sh](../hooks/load-guideline-indexes.sh) runs on
`SessionStart`, and its stdout becomes context the agent sees. It prints a short
header saying how to use the indexes, then `guidelines/README.md` and every
directory's `README.md`, each under its absolute path so that the relative links
inside it resolve. A new directory under `guidelines/` is picked up without
touching the hook.

The hook fires on `startup`, `clear` and `compact`, and deliberately not on
`resume` or `fork`: a resumed or forked session still carries the earlier
injection in its transcript, while a compacted one may have had it summarized
away.

The project's guidelines entry file goes out last, when it exists
(`docs/guidelines.md`, or `docs/guidelines/README.md` when the guidelines are
split), under a heading that says it overrides the shared rules: an override the
agent only reads on demand is one it does not have in front of it while writing
the code it overrides. Every other `guidelines.md` and `guidelines/**/*.md` the
project tracks is listed after it by path, with what it governs, and read when a
change reaches that. If a file cannot be read, the hook says so in the injected
text rather than emitting nothing, because an index that failed to load must not
be indistinguishable from guidelines that do not apply.

## How common applies its own guidelines

Every other iglootools project gets the guidelines from the plugin, which it
enables in its committed `.claude/settings.json` (see
[installation.md](installation.md)). Common does not enable the plugin.
[AGENTS.md](../AGENTS.md) does the same job by hand instead:

| | Another project | Common |
|---|---|---|
| The indexes | the `SessionStart` hook injects them from the installed plugin | `AGENTS.md` names them, and the agent reads them from the working tree |
| The guidelines a change reaches | the agent reads them from the installed plugin, as the indexes route it | the same, from the working tree |
| Audit skills and the reminder before a pull request | from the installed plugin | from the working tree, with `claude --plugin-dir .`, as [setup-development-environment.md](setup-development-environment.md#loading-the-plugin-from-the-working-tree) shows |

### Why common does not install its own plugin

An installed plugin is a released copy, cached outside the repository, and
`${CLAUDE_PLUGIN_ROOT}` points at that copy. In another project that is what you
want. In common, the copy is behind the files being edited, because a branch
here is the next release:

- **The agent would follow the old rule while editing the new one.** The hook
  would inject the released `general.md` while the branch changes it. With two
  versions of a rule in context, the agent cannot tell which one applies.
- **It would read and edit the wrong files.** The hook prints the absolute paths
  of the guidelines under the plugin root, so links followed from the injected
  text lead into the cache, not the checkout.
- **Audits would check a branch against the guidelines it replaces.**
- **Changes to the plugin could not be tested cleanly.** Loading the working
  tree with `--plugin-dir` next to an installed copy loads two plugins with the
  same name. At best the guidelines are injected twice. At worst you cannot tell
  which copy's hooks and skills ran.

Reading the files directly avoids all four. The price is that `AGENTS.md`
repeats what the hook emits: the indexes, named by where they are rather than
one by one, so a new directory needs no change to either.

## The `iglootools` command

The shared command lives in `src/iglootools/`, one package per domain (`docs`,
`python`, `demo`, `mise`, `shell`), each with a `cli` module that is the only
place it prints. Its tests are under `tests/`. How projects install, configure
and pin it, and how to try a change against one of them before releasing, is in
[guidelines/project-setup/iglootools-cli.md](../guidelines/project-setup/iglootools-cli.md).

## Checking the pins on common

A project pins a release of common in several files. `iglootools common adopt`
moves every pin to a release, looking in every tracked file that mentions common
rather than in a list of files, and `iglootools common check-pins`, run offline
as each project's `lint-common-pins` task, keeps them in agreement between
adopts.

| | Every project |
|---|---|
| The `iglootools` command | a dev dependency in `pyproject.toml`, `iglootools @ git+https://github.com/iglootools/common@v<version>`, run as `uv run --no-sync iglootools …`; a project without Python has a `pyproject.toml` for this alone ([ADR-004](architecture-decision-record.md#adr-004--install-the-iglootools-command-through-uv-in-every-project-python-or-not)) |
| Where the tag's commit is recorded | `uv.lock`: `common?rev=v<version>#<commit>`, written when `uv lock` resolved the tag |
| Other pins | the reusable workflows (by SHA, with `# v<version>`), the `base` Renovate preset, and the `python` one in a Python project |
| What keeps the release current | Renovate, through the `base` preset's manager for the dependency, and its own for the workflows and presets; adopt |
| What `adopt` does | moves the pins, then regenerates `uv.lock`, which records the new commit; once merged, updates the Claude Code plugin installed for the project |
| What `check-pins` verifies | every pin names one release, adopt would move each, every SHA pin has its tag comment, and the release and every workflow SHA match `uv.lock`'s record |

Why the check runs offline, trusting `uv.lock`'s record, is in
[ADR-001](architecture-decision-record.md#adr-001--check-the-pins-on-common-offline-trusting-uvlock-and-iglootools_versions-name).

## Adopting a release everywhere

`iglootools common adopt-all` runs from common's checkout, on the projects
checked out in the workspace: the directory `IGLOOTOOLS_WORKSPACE` names, or
else the nearest one, from the checkout up, holding a `.iglootools-workspace`
directory ([setup](setup-development-environment.md#the-iglootools-workspace)).
Nothing is guessed, not even common's parent directory: a run that picked the
wrong directory would adopt in the wrong checkouts, or report every project
missing. It takes every git checkout there whose `origin` is a repository of the
iglootools organization and that pins common, narrowed by `--only` and
`--exclude`, and passes over the rest with the reason. It then lists every
repository of the organization and reads the `renovate.json` on the default
branch of each one with no checkout in the workspace. One that extends a preset
from common, as every project that adopts common does, fails the run: a project
nobody cloned would otherwise be silently left on the old release. One that does
not, or has no `renovate.json`, is skipped with a warning, so a project meant to
pin common but missing the preset is seen; an archived one is skipped unread,
since it cannot take a pull request.

Before changing any project it checks that each one's `origin` is reachable
with git and ssh unable to prompt. One problem anywhere stops the run while
nothing has happened. A checkout's branch and changes are not checked: adopt
works in a temporary worktree started from GitHub's default branch, so a session
working in the checkout is never switched or blocked
([ADR-006](architecture-decision-record.md#adr-006--adopt-a-release-in-a-temporary-worktree-not-in-the-projects-checkout)).

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

Once every project has finished, each one on the release has its Claude Code
plugins brought up to date, as `iglootools workspace sync` does: each
marketplace the projects use is refreshed once, then every plugin a project's
`.claude/settings.json` enables is updated where it is installed for that
project and installed where it is not, with `--scope project`, one project
after the other, since Claude Code keeps a single list of installs for every
project. Which version a project loads is recorded only on the machine, so
without this step a merged adopt left every session on the old guidelines.
Whether a plugin is installed for a project, and at which version, is read from
`claude plugin list --json` rather than trusted from the commands, for two
reasons: `claude plugin update` reports success in a project that has no
install of its own, and the marketplace serves the newest release on common's
default branch, which is not the adopted one when a later release exists. The
first is why a missing install is installed rather than updated; the second is
a warning.

**No project depends on another**, so the projects run in any order and at once.
If one ever did, for instance a project consuming another's package, adopt-all
would need an order: adopt and release the dependency first, then the projects
that depend on it, which turns the single parallel step into stages.

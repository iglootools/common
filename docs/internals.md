# Internals

How the plugin delivers the guidelines to Claude Code: the `guidelines` skill, the audit skills,
and the hook that loads the always-on guidelines. Installing it is in
[installation.md](installation.md).

<!-- toc -->
**On this page**

- [Two delivery mechanisms](#two-delivery-mechanisms)
- [The `guidelines` skill](#the-guidelines-skill)
- [Auditing](#auditing)
- [The ones that load in every session](#the-ones-that-load-in-every-session)
- [The `iglootools` command](#the-iglootools-command)
<!-- tocstop -->

## Two delivery mechanisms

The guidelines split into two kinds, and the plugin delivers each by the mechanism that fits.
`coding/general.md`, `coding/python.md` and `coding/git.md` govern every edit, so a `SessionStart`
hook puts them in context from the start. The rest are triggered by a specific file, so a skill
reads them only when a change reaches the files they govern.


## The `guidelines` skill

This repository is also a Claude Code plugin. Its main skill, `guidelines`, restates
no guideline: its body says which file to read and when, so the guidelines stay in one place,
readable by humans and agents alike. It does three things — dispatches to the guideline file a
change reaches, carries the pass to make before calling the change done, and walks the procedure
for recording a documented exception where a rule does not fit.

Guideline files are read on demand where possible: the skill reads only the one a change
actually reaches, and an ordinary code change reads none of them.

It also enforces the philosophy the guidelines rest on: check the work against them before
calling it done, and document a deviation rather than drift from a rule silently. See
[Documented Exceptions](../guidelines/coding/general.md#documented-exceptions).

## Auditing

`/iglootools:audit-pr` audits the current branch against its base, and `/iglootools:audit-full`
audits the whole codebase or the paths given. Both run only when you type them, because an
audit starts several agents and costs accordingly. Each splits the categories in
[guidelines/review/audit.md](../guidelines/review/audit.md) across parallel `auditor` agents,
sends the `critical` and `high` findings to a second auditor that tries to disprove them, and
writes a Markdown report to `.iglootools/audits/`. Every finding gets an ID such as `SEC-1`, so
you can ask for exactly the fixes you want: "fix SEC-1 and ERR-2", "fix all ARCH".

The skills run in the main conversation rather than in a subagent of their own, for two
reasons. The findings have to be in the conversation that will fix them. And the fan-out
needs no nested delegation when the main conversation starts the auditors itself.

The auditors do not see what the `SessionStart` hook emits, because a subagent does not
receive it, so the `auditor` agent reads the guidelines itself.

## The ones that load in every session

Some guidelines govern every edit rather than one kind of file — `coding/general.md`,
`coding/python.md` and `coding/git.md` today. `coding/git.md` has no file to trigger it at all:
it applies at the moment of committing, which is exactly when an agent fixing a lint failure
would not stop to look for a skill. Those are not skills: a skill is model-invoked, which is right for a guideline triggered
by a file and wrong for one that applies to everything. They are delivered instead by
[hooks/load-always-on-guidelines.sh](../hooks/load-always-on-guidelines.sh), which runs on
`SessionStart` and whose stdout becomes context the agent sees. Another such guideline is added
to that script.

The hook fires on `startup`, `clear` and `compact`, and deliberately not on `resume` or `fork`: a
resumed or forked session still carries the earlier injection in its transcript, while a compacted
one may have had it summarized away.

Emission can be conditional: `coding/python.md` goes out only when the project has a `pyproject.toml`,
so a project with no Python does not pay for it. The project's own `docs/guidelines.md` goes out
last, when it exists, under a heading that says it overrides the shared rules above it: an
override the agent only reads on demand is one it does not have in front of it while writing
the code it overrides. If a file cannot be read, the hook says so in
the injected text rather than emitting nothing, because a guideline that failed to load must not
be indistinguishable from one that does not apply.

## The `iglootools` command

The shared command lives in `src/iglootools/`, one package per domain (`docs`, `python`,
`demo`, `mise`, `shell`), each with a `cli` module that is the only place it prints. Its tests
are under `tests/`. How projects install, configure and pin it, and how to try a change against
one of them before releasing, is in
[guidelines/project-setup/iglootools-cli.md](../guidelines/project-setup/iglootools-cli.md).

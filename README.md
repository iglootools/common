# common

What [iglootools](https://github.com/iglootools) projects share: the coding and
project-setup guidelines, the reusable GitHub workflows every repository calls,
the scripts a guideline is easier to ship as than to describe, and the Claude
Code plugin that delivers all of it.

Renamed from `common-guidelines`, which described only the first of those.

<!-- toc -->
**On this page**

- [Contents](#contents)
- [Usage with Claude Code](#usage-with-claude-code)
<!-- tocstop -->

## Contents

The rules themselves live in [**`guidelines/`**](guidelines/), whose
[index](guidelines/README.md) says which file governs which change. Three files
govern every edit and are in context from the start of a session; the rest are
read only when a change reaches the files they govern.

[Usage with Claude Code](#usage-with-claude-code) covers how that split is
delivered. The rest of the repository supports the guidelines rather than
stating any:

- [skills/](skills/) — the Claude Code skills: `guidelines`, which routes an
  agent to whichever guideline governs the edit it is about to make, and
  `audit-pr` and `audit-full`, which audit a branch or the whole codebase. None
  restates guidance of its own.
- [agents/](agents/) — the `auditor` agent the audit skills start, several at a
  time.
- [hooks/](hooks/) — the `SessionStart` hook that loads the always-on guidelines
  into every session, and the `PreToolUse` hook that reminds the user to run
  `audit-pr` before a pull request is opened, marked ready or merged.
- [src/iglootools/](src/iglootools/) — the `iglootools` command, for the
  guidelines that are easier to ship as working code than to describe: generated
  docs, build checks, the demo, the mise and shell checks. Projects install it
  pinned to a release tag; see
  [iglootools-cli.md](guidelines/project-setup/iglootools-cli.md).

To change any of it, start from [CONTRIBUTING.md](CONTRIBUTING.md).

## Usage with Claude Code

A single Claude Code plugin delivers everything here, installed per project; no
clone of this repository is needed. A `SessionStart` hook puts
`coding/general.md`, `coding/python.md` and `coding/git.md` in context from the
start, and the `guidelines` skill reads any other file only when a change
reaches the files it governs. `/iglootools:audit-pr` and
`/iglootools:audit-full` audit a branch or the whole codebase against them.

- [docs/installation.md](docs/installation.md): installing the plugin in a
  project, and moving one project or all of them to a new release.
- [docs/internals.md](docs/internals.md): how the skill, the audits and the hook
  work.

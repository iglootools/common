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

The rules themselves live in [**`guidelines/`**](guidelines/), split into
[`coding/`](guidelines/coding/) for how code is written and
[`project-setup/`](guidelines/project-setup/) for how a repository is
configured, and [`review/`](guidelines/review/) for auditing a codebase against
both. Each has its own index. They divide by how they are delivered rather than
by subject: three govern every edit and are in context from the start of a
session, the rest are read only when a change reaches the files they govern:

| Always on | |
|---|---|
| [`coding/general.md`](guidelines/coding/general.md) | language-agnostic coding principles |
| [`coding/python.md`](guidelines/coding/python.md) | the Python layer, wherever the project has a `pyproject.toml` |
| [`coding/git.md`](guidelines/coding/git.md) | commits shaped for review: what is a commit and what is its own pull request, refactoring apart from behaviour, rework and feedback folded into the commit they correct, merge commits rather than squashes, rebasing and cleaning up before review, commit messages |

| Read when a change reaches it | Triggered by |
|---|---|
| [`project-setup/python-tooling.md`](guidelines/project-setup/python-tooling.md) | `pyproject.toml` (including the import-linter and dead-code checks), the Python settings in `mise.toml`, `uv.lock`, the Python version policy |
| [`project-setup/mise.md`](guidelines/project-setup/mise.md) | `mise.toml`, `mise-tasks/**`, `mise.lock`, a shell script, adding, renaming or naming a mise task |
| [`project-setup/workflows.md`](guidelines/project-setup/workflows.md) | `.github/workflows/**` |
| [`project-setup/shared-workflows.md`](guidelines/project-setup/shared-workflows.md) | adding or changing a caller of a workflow this repository hosts |
| [`project-setup/dependency-automation.md`](guidelines/project-setup/dependency-automation.md) | `renovate.json`, `dependabot.yml`, the repository settings both depend on, `lint-renovate` and `renovate-dry-run` |
| [`project-setup/repository.md`](guidelines/project-setup/repository.md) | `.gitignore`, setting up a new repository, repository rulesets and merge settings, the code of conduct and security policy |
| [`project-setup/documentation.md`](guidelines/project-setup/documentation.md) | `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, `CLAUDE.md`, `docs/**` |
| [`project-setup/pypi-publishing.md`](guidelines/project-setup/pypi-publishing.md) | the release and publish workflows, cutting a release |
| [`project-setup/iglootools-cli.md`](guidelines/project-setup/iglootools-cli.md) | `[tool.iglootools]`, the `iglootools` pin, a task that calls `iglootools` |
| [`project-setup/cli-demo.md`](guidelines/project-setup/cli-demo.md) | `demo/**`, the demo workflow and tasks |
| [`project-setup/formatting.md`](guidelines/project-setup/formatting.md) | `dprint.json`, `.rumdl.toml`, `.git-blame-ignore-revs`, the `fmt*`, `lint-fmt*` and `lint-markdown` tasks |
| [`project-setup/ide.md`](guidelines/project-setup/ide.md) | `.vscode/**`, `*.code-workspace`, `[tool.pyright]` |
| [`project-setup/claude-code.md`](guidelines/project-setup/claude-code.md) | `.claude/settings.json` |

| Read by the audit skills | |
|---|---|
| [`review/audit.md`](guidelines/review/audit.md) | what an audit looks for, by category; severity, confidence and origin; the report's layout; and how findings are fixed |

`project-setup/` is one file per trigger deliberately: it was a single 501-line
file, so a change to a workflow pulled the Renovate rules and the editor
settings into context along with it.

**Two things hold for every file above, which is why none of them repeats
them.** The reasoning behind the rules is in [philosophy.md](philosophy.md). And
every rule is a default: deviating is allowed wherever the deviation and its
reasoning are documented, on the terms in
[general.md › Documented Exceptions](guidelines/coding/general.md#documented-exceptions):
where an exception goes, the bar its rationale has to meet, and naming the
condition that would retire it.

[Usage with Claude Code](#usage-with-claude-code) covers how that split is
delivered. The rest of the repository supports the guidelines rather than
stating any:

- [philosophy.md](philosophy.md) — the reasoning behind the guidelines
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

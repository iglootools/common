---
description: The iglootools shared guidelines — how these projects write and review code, package Python, configure CI and dependency automation, format and lint files, set up the editor, and record a documented exception where a rule does not fit. Use before changing any source file, GitHub workflow, dependency or build configuration, or editor and Claude Code settings; before calling a change done; and before departing from a rule.
when_to_use: Writing or reviewing code; editing .github/workflows, renovate.json, dependabot.yml or .gitignore; editing dprint.json or .rumdl.toml, or fixing a formatting or Markdown lint failure; adding or restructuring project documentation (CONTRIBUTING.md, AGENTS.md, CLAUDE.md, docs/); editing pyproject.toml, mise.toml, a file under mise-tasks/, a shell script or a lock file; adding a dependency or a mise task; editing .vscode/, .claude/settings.json or a *.code-workspace; setting up a new repository; departing from a shared rule; adding a ruff ignore, a noqa, or a pyright suppression.
paths:
  - "**/*.py"
  - "**/*.pyi"
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.vue"
  - "**/*.js"
  - "**/*.mjs"
  - "pyproject.toml"
  - "mise.toml"
  - "mise-tasks/**"
  - "**/*.sh"
  - "mise.lock"
  - "uv.lock"
  - ".github/workflows/**"
  - "renovate.json"
  - ".github/renovate.json"
  - "dependabot.yml"
  - ".github/dependabot.yml"
  - ".gitignore"
  - "dprint.json"
  - ".rumdl.toml"
  - ".git-blame-ignore-revs"
  - "CONTRIBUTING.md"
  - "AGENTS.md"
  - "CLAUDE.md"
  - "docs/*.md"
  - "README.md"
  - "demo/**"
  - ".vscode/**"
  - ".claude/settings.json"
  - "*.code-workspace"
---

## Writing code

`coding/general.md` and `coding/git.md` are already in this session — the
plugin's `SessionStart` hook emits them at startup and again after a compaction,
along with `coding/python.md` when the project has a `pyproject.toml`, and the
project's own `docs/guidelines.md` after both when the project has one. Apply
them at write time, not as a post-hoc review, and where the project's file
contradicts a shared rule, follow the project's file.

If a file you need is not in context, because the project has no
`pyproject.toml`, a compaction dropped it, or the hook reported that it could
not read it, read `${CLAUDE_PLUGIN_ROOT}/guidelines/coding/general.md`,
`${CLAUDE_PLUGIN_ROOT}/guidelines/coding/git.md`,
`${CLAUDE_PLUGIN_ROOT}/guidelines/coding/python.md` or the project's
`docs/guidelines.md` before continuing.

## Finding code

Answer symbol questions with the project's language server rather than with text
search: where something is defined, what references or calls it, what type it
returns, what a module contains. These projects reuse short names across
modules, so a symbol answer has to come from the import graph and not from text
matches. A project declares its server in `.claude/settings.json` — for a Python
project that is the `pyright-lsp` plugin, which `ide.md` requires at project
scope.

Reach for `grep`/`Glob` when the target is not a resolvable symbol: string
literals, config keys, YAML/TOML, comments, filenames, or a name that may not
resolve at all. The server does not descend into installed dependencies either —
`site-packages`, `node_modules` — so a third-party definition still needs the
file read directly.

## What the project documents, and where

Every iglootools project keeps two documents at the same paths. That is a
convention rather than something each project announces, so do not wait to be
pointed at them:

| Path | Holds | Read it |
|---|---|---|
| `CONTRIBUTING.md` | the index of the project's documentation — setup, build and test, guidelines, domain, architecture, internals, CLI and config references | when you need any of those, to find which file has it |
| `docs/guidelines.md` | the project's deviations from the shared set, which shared sections are out of scope, rules of its own, its implementation checklists (inline, or linked by task), and the conventions its owners set for particular areas of the code (linked by the paths they govern) | it is already in context — the hook emits it; reread it if a compaction dropped it |

A missing file means the project has documented nothing of that kind, and the
shared guidelines stand as written. It does not mean the content sits elsewhere
under another name.

**Area conventions.** The people who own a part of the code — storage, the CLI,
the event schema, the CI pipeline — may have written conventions for it, and
`docs/guidelines.md` links each such document next to the paths it governs. When
a change reaches one of those paths, read the linked document in full before
editing, the same way the table below works for the shared files. A project may
also deliver an area's conventions through a skill of its own scoped to those
paths; if one fires, follow it.

## Read the file the change reaches

Read none of these for an ordinary code change. Each is long and stays in
context for the rest of the session once read, so read only the one the change
actually reaches — and then read it in full, not the section that looks
relevant. They are largely about failures that are silent, so the part that
looks skippable is usually the part that names the failure.

| Read | When the change touches |
|---|---|
| `${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/python-tooling.md` | Python building, packaging and dependencies, `uv.lock`, the import-linter setup, the dead-code check, the patching checks (ruff `TID251`, the failing `monkeypatch` fixture), the Python settings in `mise.toml` (`[deps.uv]`, the `python` and `uv` pins), or the Python task set. Adding a dependency counts wherever the edit lands. |
| `${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/mise.md` | `mise.toml`, anything under `mise-tasks/`, `mise.lock`, or a shell script, in any project. Adding, renaming or changing a mise task — including choosing its name — counts wherever the edit lands. Read it *with* `python-tooling.md` when the edit is to a Python project's mise settings. |
| `${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/workflows.md` | Anything under `.github/workflows/`. |
| `${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/shared-workflows.md` | Adding or changing a workflow that calls one this plugin's repository hosts — the link checker, the `mise.lock` regenerator, or the uv dependency-graph submission. Read it *with* `workflows.md`, not instead of it. |
| `${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/dependency-automation.md` | `renovate.json`, `dependabot.yml`, or a question about why a dependency update did or did not appear. |
| `${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/repository.md` | The committed `.gitignore`, setting up a new repository, its rulesets (branch or tag protection), how pull requests are merged, or the code of conduct and security policy. |
| `${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/documentation.md` | Adding, renaming or restructuring project documentation: `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, `CLAUDE.md`, or a file under `docs/` — including `docs/guidelines.md` and a new area-conventions document. |
| `${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/pypi-publishing.md` | `release.yml`, `publish.yml` or `publish-test.yml`, the version scheme, or cutting a release by hand. Read it *with* `workflows.md` when the edit is to a workflow. |
| `${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/iglootools-cli.md` | `[tool.iglootools]` in `pyproject.toml`, the `iglootools` dependency or its pin, a mise task that calls `iglootools`, or a bug found in one of its commands (which is fixed in iglootools/common, not worked around in the project). |
| `${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/cli-demo.md` | `demo/`, `.github/workflows/demo.yml`, the `demo-*` mise tasks, or the README's asciinema embed. |
| `${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/formatting.md` | `dprint.json`, `.rumdl.toml` or `.git-blame-ignore-revs`; the `fmt*` or `lint-fmt*` tasks, or `lint-markdown`; or a formatting or Markdown lint failure to fix. Read it *with* `mise.md` when the edit is to those tasks. |
| `${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/ide.md` | `.vscode/`, a `*.code-workspace`, or the `[tool.pyright]` section of `pyproject.toml`. |
| `${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/claude-code.md` | `.claude/settings.json`, or which Claude Code plugins the project enables. |

Some files are split between two guidelines, so check you have the right half.
`pyproject.toml` appears twice: `[tool.pyright]` belongs to
`project-setup/ide.md`, everything about building, packaging and dependencies to
`project-setup/python-tooling.md`. `mise.toml` does too: its tasks and the
`mise.lock` check belong to `project-setup/mise.md` in every project, and a
Python project's uv settings to `project-setup/python-tooling.md`. And editor
configuration is `project-setup/ide.md` while Claude Code's own configuration is
`project-setup/claude-code.md` — VSCode runs Pylance for the squiggles, the
plugin runs its own pyright for Claude, so a question about one says nothing
about the other.

## Before calling the change done

Walk the diff against the guidelines rather than trusting that you applied them
while writing:

1. The checklists in the project's `docs/guidelines.md` that cover this kind of
   change, including any it links to. Those items are project-specific and are
   not repeated anywhere in this plugin.
2. `coding/general.md`, then `coding/python.md` for a Python change, rule by
   rule against what the diff actually does.
3. Whichever file from the table above you read for this change.
4. `coding/git.md` against the branch's commits, not only its diff: one concern
   per commit, refactoring apart from behaviour, and any fix made while checking
   folded into the commit that introduced the problem. A problem the branch only
   carried along, through a move or a rename, gets a cleanup commit of its own.

Say what you changed as a result.

## When a rule does not fit

These are defaults, not dogma. An explicit, justified exception is fine; silent
drift is not. Never edit around a rule silently — take one of the two paths
below.

### The project may already have decided

Check the project's `docs/guidelines.md` (already in context) and any area
conventions it links for a rule or a documented exception that overrides the
shared default, and read any comment at the point of deviation in the file you
are editing. A documented project rule wins. If the project records none, the
shared guideline stands as written.

Undocumented divergence is drift, not an override. Do not carry it into the
change: follow the shared guideline and say what you found.

### Otherwise, record the exception

Follow `coding/general.md` › Documented Exceptions, already in context: check
that it is an exception and not debt, put it where a reader will hit it, meet
the bar, and name the condition that would retire it.

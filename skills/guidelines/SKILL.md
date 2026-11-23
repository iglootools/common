---
description: The iglootools shared guidelines — how these projects write and review code, package Python, configure CI and dependency automation, format and lint files, set up the editor, and record a documented exception where a rule does not fit. Use before changing any source file, GitHub workflow, dependency or build configuration, or editor and Claude Code settings; before calling a change done; and before departing from a rule.
when_to_use: Writing or reviewing code; editing .github/workflows, renovate.json, dependabot.yml or .gitignore; editing dprint.json or .rumdl.toml, or fixing a formatting or Markdown lint failure; adding or restructuring project documentation (CONTRIBUTING.md, AGENTS.md, docs/); editing pyproject.toml, mise.toml, a file under mise-tasks/, a shell script or a lock file; adding a dependency or a mise task; editing .vscode/, .claude/settings.json or a *.code-workspace; setting up a new repository; departing from a shared rule; adding a ruff ignore, a noqa, or a pyright suppression.
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
  - "docs/*.md"
  - "**/guidelines.md"
  - "**/guidelines/**/*.md"
  - "README.md"
  - "demo/**"
  - ".vscode/**"
  - ".claude/settings.json"
  - "*.code-workspace"
---

## Writing code

`coding/general.md` and `coding/git.md` are already in this session — the
plugin's `SessionStart` hook emits them at startup and again after a compaction,
along with `coding/python.md` when the project has Python code, and the
project's guidelines entry file after both when the project has one. Apply
them at write time, not as a post-hoc review, and where the project's file
contradicts a shared rule, follow the project's file.

If a file you need is not in context, because the project has no
Python code, a compaction dropped it, or the hook reported that it could
not read it, read `${CLAUDE_PLUGIN_ROOT}/guidelines/coding/general.md`,
`${CLAUDE_PLUGIN_ROOT}/guidelines/coding/git.md`,
`${CLAUDE_PLUGIN_ROOT}/guidelines/coding/python.md` or the project's
guidelines entry file before continuing.

## Finding code

Answer symbol questions with the project's language server rather than with text
search: where something is defined, what references or calls it, what type it
returns, what a module contains. These projects reuse short names across
modules, so a symbol answer has to come from the import graph and not from text
matches. A project declares its server in `.claude/settings.json`: for a Python
project, the `pyright-lsp` plugin, as `claude-code.md` sets up.

Reach for `grep`/`Glob` when the target is not a resolvable symbol: string
literals, config keys, YAML/TOML, comments, filenames, or a name that may not
resolve at all. The server does not descend into installed dependencies either —
`site-packages`, `node_modules` — so a third-party definition still needs the
file read directly.

## What the project documents, and where

Every iglootools project keeps its documentation index and its guidelines at the
paths `${CLAUDE_PLUGIN_ROOT}/guidelines/documentation/layout.md` sets out. Do
not wait to be pointed at them:

| Path | Read it |
|---|---|
| `CONTRIBUTING.md` | to find which file documents setup, build and test, the domain, the architecture, internals or a reference |
| `docs/guidelines.md`, or `docs/guidelines/README.md` | already in context, emitted by the hook; reread it if a compaction dropped it |
| any other `guidelines.md` or `guidelines/**/*.md` | in full, before changing a file it governs; the hook lists each one with what it governs |

A missing file means the project has documented nothing of that kind, and the
shared guidelines stand as written. A project may also deliver an area's
conventions through a skill of its own scoped to those paths; if one fires,
follow it.

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
| `${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/shared-workflows.md` | Adding or changing a workflow that calls one this plugin's repository hosts — the link checker, the `mise.lock` regenerator, the uv dependency-graph submission, or the `release.yml` and `demo.yml` stubs. Read it *with* `workflows.md`, not instead of it. |
| `${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/dependency-automation.md` | `renovate.json`, `dependabot.yml`, the `lint-renovate` or `renovate-dry-run` tasks, the `npm:renovate` pin and `.mise/locks/`, or a question about why a dependency update did or did not appear. |
| `${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/repository.md` | The committed `.gitignore`, setting up a new repository, its rulesets (branch or tag protection), how pull requests are merged, or the code of conduct and security policy. |
| `${CLAUDE_PLUGIN_ROOT}/guidelines/documentation/layout.md` | Adding, renaming or restructuring project documentation: `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, or a file under `docs/` — including `docs/guidelines.md` and a new area-conventions document. |
| `${CLAUDE_PLUGIN_ROOT}/guidelines/documentation/types.md` | Writing a new document, or reworking what one says, anywhere in the project. Read it *with* `layout.md` when the document is new or moves. |
| `${CLAUDE_PLUGIN_ROOT}/guidelines/documentation/writing-guidelines.md` | Adding or reworking a rule in any of the project's guidelines files. |
| `${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/pypi-publishing.md` | `release.yml`, `publish.yml` or `publish-test.yml`, the version scheme, or cutting a release by hand. Read it *with* `workflows.md` when the edit is to a workflow. |
| `${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/iglootools-cli.md` | `[tool.iglootools]` in `pyproject.toml`, the `iglootools` dependency or its pin, a mise task that calls `iglootools`, or a bug found in one of its commands (which is fixed in iglootools/common, not worked around in the project). |
| `${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/cli-demo.md` | `demo/`, `.github/workflows/demo.yml`, the `demo-*` mise tasks, or the README's asciinema embed. |
| `${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/formatting.md` | `dprint.json`, `.rumdl.toml` or `.git-blame-ignore-revs`; the `fmt*` or `lint-fmt*` tasks, or `lint-markdown`; or a formatting or Markdown lint failure to fix. Read it *with* `mise.md` when the edit is to those tasks. |
| `${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/ide.md` | `.vscode/`, a `*.code-workspace`, or the `[tool.pyright]` section of `pyproject.toml`. |
| `${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/claude-code.md` | `.claude/settings.json`, or which Claude Code plugins the project enables. |

Two files are split between guidelines. In `pyproject.toml`, `[tool.pyright]` is
`ide.md`'s and building, packaging and dependencies are `python-tooling.md`'s.
In `mise.toml`, tasks and the `mise.lock` check are `mise.md`'s, and a Python
project's uv settings are `python-tooling.md`'s.

## Before calling the change done

Walk the diff against the guidelines rather than trusting that you applied them
while writing:

1. The checklists in the project's guidelines that cover this kind of change,
   including any the entry file links to. Those items are project-specific and
   are not repeated anywhere in this plugin.
2. `coding/general.md`, then `coding/python.md` for a Python change, rule by
   rule against what the diff actually does.
3. Whichever file from the table above you read for this change.
4. `coding/git.md` against the branch's commits, not only its diff: one concern
   per commit, refactoring apart from behaviour, and any fix made while checking
   folded into the commit that introduced the problem. A problem the branch only
   carried along, through a move or a rename, gets a cleanup commit of its own.

Say what you changed as a result.

## When a rule does not fit

Never edit around a rule silently. First check whether the project has already
decided, as `applying-the-guidelines.md` › Precedence (already in context)
describes. Otherwise, record the exception as its Documented Exceptions section
describes.

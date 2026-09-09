---
description: The iglootools shared guidelines — how these projects write and review code, package Python, configure CI and dependency automation, set up the editor, and record a documented exception where a rule does not fit. Use before changing any source file, GitHub workflow, dependency or build configuration, or editor and Claude Code settings; before calling a change done; and before departing from a rule.
when_to_use: Writing or reviewing code; editing .github/workflows, renovate.json, dependabot.yml or .gitignore; editing pyproject.toml, mise.toml or a lock file; adding a dependency or a mise task; editing .vscode/, .claude/settings.json or a *.code-workspace; setting up a new repository; departing from a shared rule; adding a ruff ignore, a noqa, or a pyright suppression.
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
  - "mise.lock"
  - "uv.lock"
  - ".github/workflows/**"
  - "renovate.json"
  - ".github/renovate.json"
  - "dependabot.yml"
  - ".github/dependabot.yml"
  - ".gitignore"
  - ".vscode/**"
  - ".claude/settings.json"
  - "*.code-workspace"
---

## Writing code

`coding.md` is already in this session — the plugin's `SessionStart` hook emits it at startup
and again after a compaction, along with `python.md` when the project has a `pyproject.toml`.
Apply them at write time, not as a post-hoc review.

If a file you need is not in context, because the project has no `pyproject.toml`, a compaction
dropped it, or the hook reported that it could not read it, read
`${CLAUDE_PLUGIN_ROOT}/guidelines/coding.md` or `${CLAUDE_PLUGIN_ROOT}/guidelines/python.md` before continuing.

## Finding code

Answer symbol questions with the project's language server rather than with text search: where
something is defined, what references or calls it, what type it returns, what a module contains.
These projects reuse short names across modules, so a symbol answer has to come from the import
graph and not from text matches. A project declares its server in `.claude/settings.json` — for
a Python project that is the `pyright-lsp` plugin, which `ide.md` requires at project scope.

Reach for `grep`/`Glob` when the target is not a resolvable symbol: string literals, config keys,
YAML/TOML, comments, filenames, or a name that may not resolve at all. The server does not
descend into installed dependencies either — `site-packages`, `node_modules` — so a third-party
definition still needs the file read directly.

## What the project documents, and where

Every iglootools project keeps its own documentation at the same three paths. That is a
convention rather than something each project announces, so do not wait to be pointed at them:

| Path | Holds | Read it |
|---|---|---|
| `docs/guidelines.md` | the project's deviations from the shared set, which shared sections are out of scope, and rules of its own | before departing from a shared rule, and whenever a shared rule looks wrong here |
| `docs/implementation-checklists.md` | project-specific checks with no counterpart in this plugin | before calling a change done |
| `docs/setup-development-environment.md` | how to get the project running, including installing this plugin | when the task is setup, tooling or editor configuration |

A missing file means the project has documented nothing of that kind, and the shared guidelines
stand as written. It does not mean the content sits elsewhere under another name.

## Read the file the change reaches

Read none of these for an ordinary code change. Each is long and stays in context for the rest
of the session once read, so read only the one the change actually reaches — and then read it
in full, not the section that looks relevant. All three are largely about failures that are
silent, so the part that looks skippable is usually the part that names the failure.

| Read | When the change touches |
|---|---|
| `${CLAUDE_PLUGIN_ROOT}/guidelines/python-tooling.md` | Building, packaging, dependencies, lock files, or the mise task set. Adding a dependency and adding a mise task count wherever the edit lands. |
| `${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/workflows.md` | Anything under `.github/workflows/`. |
| `${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/shared-workflows.md` | Adding or changing a workflow that calls one this plugin's repository hosts — the link checker, the `mise.lock` regenerator, or the uv dependency-graph submission. Read it *with* `workflows.md`, not instead of it. |
| `${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/dependency-automation.md` | `renovate.json`, `dependabot.yml`, or a question about why a dependency update did or did not appear. |
| `${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/repository.md` | The committed `.gitignore`, or setting up a new repository. |
| `${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/ide.md` | `.vscode/`, a `*.code-workspace`, or the `[tool.pyright]` section of `pyproject.toml`. |
| `${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/claude-code.md` | `.claude/settings.json`, or which Claude Code plugins the project enables. |

Two files split what used to be one row each, so check you have the right half.
`pyproject.toml` appears twice: `[tool.pyright]` belongs to `project-setup/ide.md`, everything
about building, packaging and dependencies to `python-tooling.md`. And editor configuration is
`project-setup/ide.md` while Claude Code's own configuration is `project-setup/claude-code.md` —
VSCode runs Pylance for the squiggles, the plugin runs its own pyright for Claude, so a question
about one says nothing about the other.

## Before calling the change done

Walk the diff against the guidelines rather than trusting that you applied them while writing:

1. The project's `docs/implementation-checklists.md`, if it has one. Those items are
   project-specific and are not repeated anywhere in this plugin.
2. `coding.md`, then `python.md` for a Python change, rule by rule against what the diff
   actually does.
3. Whichever file from the table above you read for this change.

Say what you changed as a result.

## When a rule does not fit

These are defaults, not dogma. An explicit, justified exception is fine; silent drift is not.
Never edit around a rule silently — take one of the two paths below.

### The project may already have decided

Check the project's `docs/guidelines.md` for a rule or a documented exception that overrides the
shared default, and read any comment at the point of deviation in the file you are editing. A
documented project rule wins. If the project records none, the shared guideline stands as
written.

Undocumented divergence is drift, not an override. Do not carry it into the change: follow the
shared guideline and say what you found.

### Otherwise, record the exception

**1. Check it is an exception, not debt.** If the reason is "we have not gotten around to it",
that is debt to track, not an exception to document — either do the work, or record it wherever
the project tracks debt. Legitimate reasons look like a performance constraint, an ecosystem
convention, a third-party library limitation, or a platform or version still supported.

**2. Put it where a reader will hit it**, not in a separate log.

- *Project-wide* — the project's `docs/guidelines.md`, stated against the rule it overrides. If
  that file already documents an exception in the same area, extend that entry rather than
  adding a second one beside it; two entries on one subject drift apart.
- *Local or config-level* — a comment at the point of deviation: the `[tool.ruff.lint]` `ignore`
  entry paired with the decision that motivates it, a `# noqa` with its reason beside it, a
  comment above the constraint in `pyproject.toml`.

**3. Meet the bar** — a rationale a reviewer would accept, not merely a note that the deviation
exists. "We ignore this rule" is drift; "we ignore this rule because X, and here is what we do
instead" is an exception. Name the rule being overridden, so the exception is traceable back
to it.

**4. Name what would retire it.** Almost every exception answers a condition that is true at the
time, and those conditions expire. Where the exception depends on one, name the condition that
would make it unnecessary — "revisit when X supports Y", "drop this once we no longer support
Z" — not just the reason it exists today. An undocumented exception silently becomes permanent,
because nobody is left who remembers what it was working around. The shape to copy is the
Python version policy in `${CLAUDE_PLUGIN_ROOT}/guidelines/python.md`: it records the constraint, what it
costs, and the specific event that would retire it.

Full reasoning: `${CLAUDE_PLUGIN_ROOT}/README.md#applying-these-guidelines`

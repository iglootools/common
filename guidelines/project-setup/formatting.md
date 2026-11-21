# Formatting Guidelines

Which tool formats and lints each kind of file in an iglootools project,
whatever its language, and how they are set up. ruff's configuration for Python
is in [python-tooling.md](python-tooling.md#code-quality-tools).

<!-- toc -->
**On this page**

- [One tool per file type](#one-tool-per-file-type)
- [Pin both in mise](#pin-both-in-mise)
- [Configure dprint](#configure-dprint)
- [Configure rumdl](#configure-rumdl)
- [Leave generated documents to their generator](#leave-generated-documents-to-their-generator)
- [Tasks](#tasks)
- [Reformat once, in its own commit](#reformat-once-in-its-own-commit)
- [Format Renovate branches in CI](#format-renovate-branches-in-ci)
- [Editor](#editor)
<!-- tocstop -->

## One tool per file type

| Files | Tool | Formats | Lints |
|---|---|---|---|
| Python | [ruff](https://docs.astral.sh/ruff/) | yes | yes |
| JSON, TOML, YAML, Dockerfiles | [dprint](https://dprint.dev/) | yes | no |
| Markdown | [rumdl](https://rumdl.dev/) | yes | yes |

- **dprint for everything with no formatter of its own.** One binary, with one
  plugin per format, so `mise.toml`, `pyproject.toml`, `renovate.json`, the
  workflows and the editor settings all go through one command. Prettier covers
  the same files, but brings a Node toolchain into projects that otherwise have
  none.
- **rumdl for Markdown, not dprint's Markdown plugin.** Both format; only rumdl
  also lints: heading levels, broken relative links, bare URLs, fenced code
  blocks without a language. Leave dprint's Markdown plugin out, so that one
  tool owns each file.
- **Defaults, unless they cannot work.** Neither tool's style is argued over:
  each runs on its defaults, and a setting changes only where the default
  fails, with its reason beside it. That is why prose wraps at rumdl's 80
  columns rather than at the 100 the docs used to be wrapped at by hand.

## Pin both in mise

```toml
[tools]
dprint = "0.64.3"
rumdl = "0.3.4"
```

`mise use --pin dprint@<version> rumdl@<version>` adds both, through `aqua:`
backends, which `mise.lock` can lock
([workflows.md](workflows.md), on lockable backends). In
`[tools]` rather than the dev dependency group, so a project without Python gets
them the same way, and Renovate's mise manager keeps them current.

## Configure dprint

`dprint.json`, at the project root:

```json
{
  "plugins": [
    "npm:@dprint/json@0.26.0",
    "npm:@dprint/toml@0.10.0",
    "npm:dprint-plugin-yaml@0.6.0",
    "npm:@dprint/dockerfile@0.8.0"
  ]
}
```

- **Add plugins with `dprint config add`** (`json toml g-plane/pretty_yaml
  dockerfile`), which writes the current version of each. Add no Markdown or
  Python plugin: rumdl and ruff own those files.
- **The plugins are pins of their own**, apart from the dprint binary. The
  shared `base` Renovate preset reads their `npm:` specifiers
  ([dependency-automation.md](dependency-automation.md#extend-the-shared-renovate-presets)),
  so extend it rather than adding a manager.
- **No `excludes` are needed.** dprint skips what `.gitignore` ignores, and the
  lock files are not `.toml` files, so `uv.lock` and `mise.lock` are never
  formatted.
- **Give each array item its own line when a comment trails it.** dprint puts
  one item per line, so a comment after two items on one line ends up attached
  to the second only, and reads as being about it.

## Configure rumdl

`.rumdl.toml`, at the project root:

```toml
[MD013]
reflow = true
code-blocks = false
headings = false
```

| Setting | Default | Why it changes |
|---|---|---|
| `reflow = true` | `false` | without it, `rumdl fmt` leaves every long line alone, and each one is a warning only a hand edit can fix. With it, prose is rewrapped to 80 columns |
| `code-blocks = false` | `true` | a code block cannot be rewrapped without changing what it shows: a command, a config file, a log line |
| `headings = false` | `true` | a heading cannot be wrapped either, and its text is its anchor: shortening one to fit breaks every link to it |

- **A Claude Code plugin's skills and agents have no title**: they open with
  YAML front matter, which Claude Code shows instead. A repository that has
  them adds `[per-file-ignores]` entries for MD041 (first line is a heading),
  `"skills/**/SKILL.md" = ["MD041"]` and `"agents/*.md" = ["MD041"]`.
- **Fix a skipped heading level by hand.** rumdl's MD001 fix promotes only the
  first heading under the skipped level, leaving its siblings one level below
  it. Promote them all, then run `mise run toc`.

## Leave generated documents to their generator

A generated document belongs to its generator, which decides its format. Let
rumdl reflow it, or strip the `$` prompts from its `console` blocks (MD014),
and the next regeneration produces something else: its `-check` task fails,
and fixing the formatting by hand only lasts until the next run. Keep rumdl out
of everything a generator writes:

- **A whole generated file**, such as the CLI reference `iglootools docs cli`
  writes, is excluded in `.rumdl.toml`. A comment inside it would not survive:
  the generator rewrites the whole file.

  ```toml
  [global]
  exclude = ["docs/cli-reference.md"]
  ```

- **A generated section** inside a hand-written document, such as the Module
  Overview `iglootools docs depgraph` writes or a project's configuration
  tables, is fenced with rumdl's inline comments, *outside* its markers, where
  the generator leaves the text alone. `rumdl fmt` honours them as well as
  `rumdl check`.

  ```markdown
  <!-- rumdl-disable -->
  <!-- BEGIN MODULE OVERVIEW (auto-generated by: mise run depgraph — do not edit manually) -->
  …
  <!-- END MODULE OVERVIEW -->
  <!-- rumdl-enable -->
  ```

The table of contents is the exception: `iglootools docs toc` writes a list of
links that rumdl leaves as it is, so it needs no fence. Regenerate every
generated document after adding the fences, and check that the fences are
still there: a generator that rewrote them would need fixing.

## Tasks

```toml
[tasks.format]
description = "Format every file with ruff, dprint and rumdl (rewrites files; see format-check to verify only)"
run = [
  "uv run --no-sync ruff format .",
  "dprint fmt",
  "rumdl fmt .",
]

[tasks.format-check]
description = "Check that every file is formatted (fails instead of reformatting; fix with `mise run format`)"
run = [
  "uv run --no-sync ruff format --check .",
  "dprint check",
]

[tasks.lint-markdown]
description = "Lint the Markdown with rumdl (configured in .rumdl.toml; fix what it can with `mise run format`)"
run = "rumdl check ."
```

- **`check` runs `format-check` and `lint-markdown`**, so CI runs both. A
  project without Python drops the ruff lines.
- **rumdl has no separate format check.** `rumdl check` reports what `rumdl fmt`
  would change along with what it cannot fix, so `lint-markdown` is the gate
  for both, beside `lint` and `lint-shell`.
- **dprint and rumdl are run bare**, not through `uv run`: mise puts its own
  tools on `PATH`, and the foreign-venv problem that
  [python-tooling.md](python-tooling.md#invoke-tools-through-uv-run---no-sync-tool-in-mise-tasks-not-bare)
  describes concerns only what a virtualenv installs.

## Reformat once, in its own commit

Adopting the formatters rewrites most files once. Keep that rewrite reviewable,
and out of `git blame`:

1. Fix what a formatter would get wrong first, each in its own commit: a
   comment shared by two array items, a skipped heading level, and
   [generated documents](#leave-generated-documents-to-their-generator) left
   unfenced.
2. Run `dprint fmt` and `rumdl fmt .` and commit the result alone, with both
   commands in the message
   ([git.md](../coding/git.md#keep-refactoring-apart-from-behaviour-changes)).
   Check that every generator's `-check` task still passes: `toc-check`, and
   `clidocs-check`, `configdocs-check` and `depgraph-check` where the project
   has them.
3. Fix what `rumdl check` still reports in a commit of its own: findings it has
   no fix for, such as bold text used as a heading (MD036), or an inline code
   span too long to wrap, which moves into a code block (MD013).
4. Record the reformat commit's hash in `.git-blame-ignore-revs`, in a commit of
   its own. GitHub reads the file without configuration; locally, run
   `git config blame.ignoreRevsFile .git-blame-ignore-revs` once per clone. Do
   not rebase the branch below the reformat commit after recording its hash: the
   rebase changes the hash and the entry stops matching.

## Format Renovate branches in CI

Renovate rewrites `mise.toml`, `dprint.json`, `renovate.json` and the workflows
in its own style. The
[shared lock regenerator](shared-workflows.md#call-the-shared-lock-regenerator-too)
runs `dprint fmt` on Renovate branches whenever the project has a
`dprint.json`, and commits the result with the lock files, so its pull requests
pass `format-check` without anyone running `mise run format` on them.

`uv add` and `uv remove` rewrite `pyproject.toml` in uv's style too. Run
`mise run format` after them, before committing.

## Editor

Recommend `dprint.dprint` and `rvben.rumdl` in `.vscode/extensions.json`, so
format-on-save uses the same tools and configuration as the tasks
([ide.md](ide.md#commit-the-extension-set-to-vscodeextensionsjson)).

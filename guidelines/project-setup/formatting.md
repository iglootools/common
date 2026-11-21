# Formatting Guidelines

Which tool formats and lints each kind of file in an iglootools project,
whatever its language: `dprint.json`, `.rumdl.toml`, `.git-blame-ignore-revs`
and the `fmt*`, `lint-fmt*` and `lint-markdown` tasks. Read it before changing
any of them, adopting the formatters, or fixing a formatting or Markdown lint
failure. ruff's configuration is in
[python-tooling.md](python-tooling.md#lint-and-format-with-ruff).

<!-- toc -->
**On this page**

- [Use one tool per file type](#use-one-tool-per-file-type)
- [Pin dprint and rumdl in mise](#pin-dprint-and-rumdl-in-mise)
- [Add dprint's plugins with `dprint config add`](#add-dprints-plugins-with-dprint-config-add)
- [Exclude from dprint what a tool writes in its own style](#exclude-from-dprint-what-a-tool-writes-in-its-own-style)
- [Give each array item its own line when a comment trails it](#give-each-array-item-its-own-line-when-a-comment-trails-it)
- [Change rumdl's defaults only where they fail](#change-rumdls-defaults-only-where-they-fail)
- [Exclude Markdown with a syntax of its own from rumdl](#exclude-markdown-with-a-syntax-of-its-own-from-rumdl)
- [Fix a skipped heading level by hand](#fix-a-skipped-heading-level-by-hand)
- [Leave generated documents to their generator](#leave-generated-documents-to-their-generator)
- [Gate formatting with `lint-fmt` and `lint-markdown`](#gate-formatting-with-lint-fmt-and-lint-markdown)
- [Reformat once, in its own commit](#reformat-once-in-its-own-commit)
- [Format Renovate branches in CI](#format-renovate-branches-in-ci)
<!-- tocstop -->

## Use one tool per file type

| Files | Tool | Formats | Lints |
|---|---|---|---|
| Python | [ruff](https://docs.astral.sh/ruff/) | yes | yes |
| JSON, TOML, YAML, Dockerfiles | [dprint](https://dprint.dev/) | yes | no |
| Markdown | [rumdl](https://rumdl.dev/) | yes | yes |

**Why:** one tool owns each file, so the editor, the tasks and CI cannot
disagree about its format.

- **dprint for everything with no formatter of its own**: one binary, one plugin
  per format, and no Node toolchain, which Prettier would bring into projects
  that otherwise have none.
- **rumdl for Markdown, not dprint's Markdown plugin**: only rumdl also lints
  (heading levels, broken relative links, bare URLs, fenced code blocks without
  a language).
- **Recommend `dprint.dprint` and `rvben.rumdl`** in the editor, as
  [ide.md](ide.md#commit-the-extension-set-to-vscodeextensionsjson) describes.

## Pin dprint and rumdl in mise

Add both to `[tools]` with `mise use --pin dprint@<version> rumdl@<version>`,
through `aqua:` backends, which `mise.lock` can lock
([workflows.md](workflows.md)).

**Why:** in `[tools]` rather than the dev dependency group, a project without
Python gets them the same way, and Renovate's mise manager keeps them current.

- mise puts them on `PATH`, so their tasks run them bare, not through `uv run`.

## Add dprint's plugins with `dprint config add`

Add plugins with `dprint config add json toml g-plane/pretty_yaml dockerfile`,
which writes the current version of each into `dprint.json`
([dprint.json](../../dprint.json) is a working example). Add no Markdown or
Python plugin.

**Why:** rumdl and ruff own those files.

- The plugins are pins of their own, apart from the dprint binary. The shared
  `base` Renovate preset reads their `npm:` specifiers
  ([dependency-automation.md](dependency-automation.md#extend-the-shared-renovate-presets)):
  extend it rather than adding a manager.

## Exclude from dprint what a tool writes in its own style

List in `dprint.json`'s `excludes`, with its reason in a comment, every file
another tool rewrites in its own style.

```json
"excludes": [
  // Written by pnpm, which rewrites it in its own style on every install.
  "pnpm-lock.yaml"
]
```

**Why:** dprint and the other tool rewrite the file back and forth, and
`lint-fmt` fails after every install.

- `.mise/locks/`, where mise locks an npm tool's dependencies, in every project
  that has it
  ([dependency-automation.md](dependency-automation.md#validate-and-preview-the-config-with-renovate-itself)).
- In a Node project, `pnpm-lock.yaml` and `package-lock.json`.
- Generated data, such as minified JSON a script writes.
- dprint skips what `.gitignore` ignores, and `uv.lock` and `mise.lock` are not
  `.toml` files, so they need no entry.

## Give each array item its own line when a comment trails it

In a file dprint formats, an array whose items carry trailing comments has one
item per line.

**Why:** dprint puts one item per line, so a comment after two items on one line
ends up attached to the second only, and reads as being about it.

## Change rumdl's defaults only where they fail

Run rumdl on its defaults, and change a setting only where the default cannot
work, with its reason beside it. [.rumdl.toml](../../.rumdl.toml) holds the
three settings every project changes (`reflow = true`, `code-blocks = false`,
`headings = false`) and their reasons.

**Why:** a style nobody argues over is one nobody has to maintain, and prose
then wraps at rumdl's 80 columns.

- A repository with Claude Code skills or agents adds `[per-file-ignores]`
  entries for MD041 (first line is a heading), `"skills/**/SKILL.md"` and
  `"agents/*.md"`: they open with YAML front matter, which Claude Code shows
  instead of a title.

## Exclude Markdown with a syntax of its own from rumdl

Exclude Markdown in another dialect, such as Nuxt Content's MDC pages
(`::component` blocks, `#slot` lines, YAML props), with
`exclude = ["content/"]` under `[global]`, and name the condition that retires
the exclusion, such as rumdl gaining a flavor for it.

**Why:** rumdl reads them as plain Markdown, and its fixes can break them: a
`#slot` line looks like a heading missing its space.

## Fix a skipped heading level by hand

Promote every heading under the skipped level, then run `mise run toc`.

**Why:** rumdl's MD001 fix promotes only the first heading under the skipped
level, leaving its siblings one level below it.

## Leave generated documents to their generator

Keep rumdl out of everything a generator writes.

**Why:** let rumdl reflow a generated document, or strip the `$` prompts from
its `console` blocks (MD014), and the next regeneration undoes it: its `lint-*`
task fails, and a hand fix lasts only until the next run.

- **A whole generated file**, such as the CLI reference `iglootools docs cli`
  writes, is excluded in `.rumdl.toml`. A comment inside it would not survive
  the next regeneration.

  ```toml
  [global]
  exclude = ["docs/cli-reference.md"]
  ```

- **A generated section** inside a hand-written document, such as the Module
  Overview `iglootools docs depgraph` writes or a project's configuration
  tables, is fenced with rumdl's inline comments, outside its markers, where the
  generator leaves the text alone. `rumdl fmt` honours them as well as
  `rumdl check`.

  ```markdown
  <!-- rumdl-disable -->
  <!-- BEGIN MODULE OVERVIEW (auto-generated by: mise run depgraph — do not edit manually) -->
  …
  <!-- END MODULE OVERVIEW -->
  <!-- rumdl-enable -->
  ```

- The table of contents needs no fence: `iglootools docs toc` writes a list of
  links that rumdl leaves as it is.
- Regenerate every generated document after adding the fences, and check that
  the fences survived: a generator that rewrote them needs fixing.

## Gate formatting with `lint-fmt` and `lint-markdown`

Give the project the tasks `fmt`, `fmt-ruff`, `fmt-dprint`, `fmt-rumdl`,
`lint-fmt`, `lint-fmt-ruff`, `lint-fmt-dprint` and `lint-markdown`, named as
[mise.md](mise.md#name-tasks-by-family) describes
([mise.toml](../../mise.toml) is a working example). `lint` runs `lint-fmt` and
`lint-markdown`.

**Why:** the formatters exit 0 whether or not they changed anything, so only
the check form can gate `preflight` and CI.

- There is no `lint-fmt-rumdl`: `rumdl check` reports what `rumdl fmt` would
  change along with what it cannot fix, so `lint-markdown` gates both.
- A project without Python drops the ruff tasks. One whose code another tool
  formats, such as ESLint in a Nuxt project, leaves that tool where it is.
- Run `mise run fmt` after `uv add` or `uv remove`, as
  [python-tooling.md](python-tooling.md#add-and-remove-dependencies-with-uv-add-and-uv-remove-then-run-fmt)
  describes.

## Reformat once, in its own commit

Adopt the formatters in one commit that only reformats, record its hash in
`.git-blame-ignore-revs`, and never rebase below it afterwards.

**Why:** the rewrite stays reviewable and out of `git blame`. A rebase changes
the hash, and the entry stops matching.

1. Fix first, each in its own commit, what a formatter would get wrong: a
   comment shared by two array items, a skipped heading level, and
   [generated documents](#leave-generated-documents-to-their-generator) left
   unfenced.
2. Run `dprint fmt` and `rumdl fmt .`, and commit the result alone, with both
   commands in the message
   ([git.md](../coding/git.md#keep-refactoring-apart-from-behaviour-changes)).
   Check that every generator's lint still passes (`lint-toc`, and
   `lint-clidocs`, `lint-configdocs` and `lint-depgraph` where the project has
   them).
3. Fix in a commit of its own what `rumdl check` still reports, such as bold
   text used as a heading (MD036), or an inline code span too long to wrap,
   which moves into a code block (MD013).
4. Record the reformat commit's hash in `.git-blame-ignore-revs`, in a commit of
   its own. GitHub reads the file without configuration. Locally, run
   `git config blame.ignoreRevsFile .git-blame-ignore-revs` once per clone.

## Format Renovate branches in CI

Call the
[shared lock regenerator](shared-workflows.md#call-the-shared-lock-regenerator-on-renovate-branches),
which formats Renovate branches with dprint.

**Why:** Renovate rewrites `mise.toml`, `dprint.json`, `renovate.json` and the
workflows in its own style, and its pull requests would otherwise fail
`lint-fmt`.

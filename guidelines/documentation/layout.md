# Documentation Layout

Where an iglootools project keeps its documentation, which documents it writes
and under what names, and how agents are pointed at them. Read this when adding,
renaming or restructuring `README.md`, `CONTRIBUTING.md`, `AGENTS.md`,
`CLAUDE.md` or anything under `docs/`.

The principle behind every rule here is in
[Documentation for people first, agent configuration for the gaps](../philosophy.md#documentation-for-people-first-agent-configuration-for-the-gaps):
the documentation is written for people, in the project's docs, and `AGENTS.md`,
skills and hooks only decide when an agent reads it.

<!-- toc -->
**On this page**

- [Where documentation lives](#where-documentation-lives)
  - [Keep `docs/guidelines.md` at its fixed path, and lean](#keep-docsguidelinesmd-at-its-fixed-path-and-lean)
  - [Split `README.md`, `CONTRIBUTING.md` and `docs/` by reader](#split-readmemd-contributingmd-and-docs-by-reader)
  - [Keep `AGENTS.md` a short map, with no `CLAUDE.md` beside it](#keep-agentsmd-a-short-map-with-no-claudemd-beside-it)
- [What to write](#what-to-write)
  - [Write the documents the project's shape calls for, one name per role](#write-the-documents-the-projects-shape-calls-for-one-name-per-role)
  - [Record architectural decisions in an append-only log](#record-architectural-decisions-in-an-append-only-log)
  - [Record repository settings as commands in one place](#record-repository-settings-as-commands-in-one-place)
- [Keeping it true](#keeping-it-true)
  - [Generate references from the code, and check them](#generate-references-from-the-code-and-check-them)
  - [Name which document each kind of change updates](#name-which-document-each-kind-of-change-updates)
<!-- tocstop -->

## Where documentation lives

### Keep `docs/guidelines.md` at its fixed path, and lean

The `guidelines` skill reads two paths by convention rather than by being
pointed at them, so they are fixed in every project: `CONTRIBUTING.md`
([below](#split-readmemd-contributingmd-and-docs-by-reader)) and
`docs/guidelines.md`. The latter holds deviations from the shared guidelines,
which shared sections are out of scope, the project's own rules, its
implementation checklists, and an index of area conventions.

The plugin's `SessionStart` hook loads `docs/guidelines.md` into every agent
session after the shared guidelines, so a project rule overrides a shared one
while the code is written. Every line is paid for in every session, so it holds
rules and exceptions, and links to anything long, such as a testing strategy, in
its own file under `docs/`:

- **Implementation checklists** live in it, or are linked from it, under a
  heading that names the task: adding a CLI command, a config field, a
  migration. One long enough to crowd the rest out moves to its own file, linked
  beside that task.
- **Area conventions** are indexed from it. The people who own an area —
  storage, the CLI, the event schema, CI — write its conventions in
  `docs/<area>-conventions.md`, which opens by linking back to its index entry.
  The skill tells the agent to read it before touching the paths listed beside
  it; a document only mentioned in prose is not read when a change reaches the
  area. A skill of the project's own may also deliver it, but the document stays
  the source. The index, as photree has it:

  ```markdown
  ## Area conventions

  Read the linked document in full before changing files under these paths.

  | Paths | Conventions |
  |-------|-------------|
  | `photree/cli/`, `photree/*/cli/` — and adding a command anywhere | [cli-conventions.md](./cli-conventions.md) — command hierarchy, options, progress, exit codes |
  ```

- **Decisions about the project's own stack** — which linter, which framework
  feature, how far to follow an upstream template — are not deviations from
  anything, and go in the
  [architecture decision record](#record-architectural-decisions-in-an-append-only-log)
  instead.

### Split `README.md`, `CONTRIBUTING.md` and `docs/` by reader

| File | Reader | Holds |
|---|---|---|
| `README.md` | someone deciding whether to use the project | what it does, badges, a demo, main use cases, non-goals, known limitations, philosophy, related projects, links to the user documentation, a link to `CONTRIBUTING.md`, the license |
| `CONTRIBUTING.md` | someone changing it | the index of the contributor documentation, one line per document — nothing else |
| `docs/` | either | every document longer than a README section, user-facing and contributor-facing alike |

- **The README links out**: installation, usage and the feature list get one
  sentence and a link. It has no "Development" section, since that is
  `CONTRIBUTING.md`, but it does state non-goals and known limitations, which a
  prospective user needs before installing.
- **Every project has a `CONTRIBUTING.md`**, even one with no `docs/`, where it
  indexes whatever plays those roles and says why its shape differs. GitHub
  links it from the pull request and issue forms, and the skill reads it to find
  everything else. Start from the scaffold below, delete the lines for documents
  the project does not have, and add the ones only it has.
- **Link with relative paths**, so links resolve on GitHub, in the editor and in
  a fork alike — except in a README that is also the package's long description
  (`readme = "README.md"`), which PyPI renders without the repository: use
  absolute GitHub URLs there
  (`https://github.com/iglootools/<repo>/blob/main/docs/usage.md`). Link to the
  shared guidelines at `https://github.com/iglootools/common/...` rather than
  naming a file in prose, so the link checker notices when it is renamed.

```markdown
# Contributing

## Getting started

- [docs/setup-development-environment.md](docs/setup-development-environment.md) — set up the
  toolchain, the editor, and the iglootools Claude Code plugin
- [docs/building-and-testing.md](docs/building-and-testing.md) — build, test, lint, the checks
  CI runs, and the GitHub settings the repository depends on
- [docs/releasing-and-publishing.md](docs/releasing-and-publishing.md) — cut a release and
  publish it

## Guidelines

This project follows the shared
[iglootools guidelines](https://github.com/iglootools/common/tree/main/guidelines).
[docs/guidelines.md](docs/guidelines.md) records where it deviates from them, the rules it adds,
the checklists to run for specific kinds of change, and the conventions for particular areas of
the code. Contributors follow the iglootools
[code of conduct](https://github.com/iglootools/.github/blob/main/CODE_OF_CONDUCT.md); report
vulnerabilities as the [security policy](https://github.com/iglootools/.github/blob/main/SECURITY.md)
describes.

## Understanding the code

- [docs/domain.md](docs/domain.md) — the domain concepts and how they relate
- [docs/architecture.md](docs/architecture.md) — how the code is organized
- [docs/internals.md](docs/internals.md) — runtime behavior and design decisions
- [docs/architecture-decision-record.md](docs/architecture-decision-record.md) — the
  architectural decisions taken, and why

## Reference

- [docs/cli-reference.md](docs/cli-reference.md) — every command and option (generated by
  `mise run clidocs`)
- [docs/config-reference.md](docs/config-reference.md) — every configuration field
```

### Keep `AGENTS.md` a short map, with no `CLAUDE.md` beside it

`AGENTS.md` at the project root is what every coding agent reads first. It is a
map, not a manual: what the project is, the commands that build and check it,
where each kind of knowledge lives, and what only an agent needs, such as which
MCP server answers questions about a framework that moves faster than any
model's training data.

```markdown
# AGENTS.md

nbkp is an rsync-based backup tool for sources and destinations that come and go.

## Commands

- `mise run preflight`: every lint and test CI runs. `mise tasks` lists the rest.
- Run a mise task when one does the job, and `uv run --no-sync <tool>` otherwise, never a bare
  tool.

## Guidelines

The shared iglootools guidelines govern every change. Claude Code loads them through the
`iglootools` plugin. Other agents: read `coding/general.md`, `coding/python.md` and
`coding/git.md` before any change, and the `project-setup/` guideline whose trigger matches the
files you are changing, using the tables in [iglootools/common's
README](https://github.com/iglootools/common#contents). Read
[docs/guidelines.md](docs/guidelines.md) before any change too: it holds this project's deviations
and its own rules.

## Where things are

Read a document when the task reaches it, not up front:

- [CONTRIBUTING.md](CONTRIBUTING.md): the index of every document below, and how to set up.
- [docs/architecture.md](docs/architecture.md): modules and layering, for any structural change.
- [docs/domain.md](docs/domain.md): volumes, endpoints, syncs, snapshots.
- [docs/building-and-testing.md](docs/building-and-testing.md): test suites and their tasks.
```

- **No `CLAUDE.md`.** Claude Code reads `AGENTS.md` itself (since 2.1.277), but
  only when there is no `CLAUDE.md`: one beside it replaces it for Claude, and
  is a second entry point only one agent reads.
- **Link, do not `@`-import.** An import loads the document into every session,
  needed or not. Write paths as links or in backticks: Claude Code treats a bare
  `@path` as an import.
- **Keep it under a screen**, since it is read every session. What applies only
  to some files belongs in the document that covers them.
- **Do not restate** the shared guidelines, the project's documents, or
  `docs/guidelines.md`, which the plugin's `SessionStart` hook already emits.

## What to write

### Write the documents the project's shape calls for, one name per role

Create each document when the project has something to put in it, not as an
empty placeholder. The skill finds them through `CONTRIBUTING.md`, so the names
are not enforced, but every project uses the same one per role, matching the
title (`# Building and Testing` lives in `building-and-testing.md`).

**For contributors:**

| Path | Holds | Write it when |
|---|---|---|
| `docs/setup-development-environment.md` (not `project-setup.md`, which collides with the shared guidelines' `project-setup/` about configuring a repository) | how to get the project running: the toolchain, the editor, installing the plugin | always |
| `docs/building-and-testing.md` (not `build-test.md`) | the task reference, testing strategy, the checks CI runs, and the [GitHub settings](#record-repository-settings-as-commands-in-one-place) | always |
| `docs/releasing-and-publishing.md` (not `release-publish.md`) | how a release is cut, what triggers what, and the publishing target's configuration | the project releases anything |
| `docs/domain.md` | the concepts the code models, in the domain's vocabulary: what each one is, how they relate, and the invariants between them; ends with a glossary | the project models anything a newcomer would have to learn — nearly always |
| `docs/architecture.md` | how the code is organized: modules or layers, what depends on what, the reasoning behind the import contracts, and where a new piece of code goes | there is more than one module |
| `docs/internals.md` | runtime behavior and the reasoning behind it: algorithms, on-disk formats, the external commands invoked, and design decisions as `Why …` subsections next to the behavior they explain | the behavior is not obvious from the code, or a decision would otherwise be relitigated |
| `docs/architecture-decision-record.md` (not `adr/`, `decisions.md`) | the [decision log](#record-architectural-decisions-in-an-append-only-log) | a choice worth arguing has been made |
| `docs/<area>-conventions.md` | an area's conventions, written by the people who own it | an area has [conventions of its own](#keep-docsguidelinesmd-at-its-fixed-path-and-lean) |
| `docs/cli-reference.md` | every command, option and argument | the project ships a CLI — [generate it](#generate-references-from-the-code-and-check-them) |
| `docs/config-reference.md` | every configuration field: type, default, validation rule; examples under `docs/config-examples/` | the project reads a configuration file |

**For users**, linked from the README:

| Path | Holds |
|---|---|
| `docs/installation.md` | system requirements, install commands, optional extras, shell completion |
| `docs/usage.md` | worked examples by task, linking to the references for the exhaustive lists |
| `docs/features.md` | the full feature list the README summarizes |
| `docs/tutorial.md` | one end-to-end walkthrough of a realistic setup, when usage examples are not enough |

- **One question per document**: *what* the project is about (`domain.md`),
  *where* the code for it lives (`architecture.md`), *how* and *why* it behaves
  the way it does (`internals.md`), and *exactly what* a user can type or
  configure (the references). Open each with a sentence saying who it is for and
  what it answers, and link to its neighbours for the rest.
- **Renaming a document changes every file that points at it**: the
  `CONTRIBUTING.md` line, the `AGENTS.md` link, cross-links, the README's
  absolute URLs, and any `description` in `mise.toml`. Search for the old name:
  the link checker runs on a schedule and cannot see a name mentioned without a
  link.

### Record architectural decisions in an append-only log

A decision that affects more than one component, and that someone would
otherwise argue about again
([Document the why, not the what](../philosophy.md#document-the-why-not-the-what)),
goes in `docs/architecture-decision-record.md`: one file, newest entry at the
bottom, each numbered and titled with the decision itself:

```markdown
## ADR-004 — Let retired URLs 404 rather than ship meta-refresh stubs

**Date:** when the decision was taken (plus **Recorded:**, if it was written up later)
**Status:** Accepted (or: Accepted — supersedes ADR-00N)

### Context
### Decision
### Rationale
### Consequences
```

- **Do not edit an entry to change the decision.** Add a new one whose `Status`
  names the entry it supersedes, so the log keeps what was believed at the time.
- **The bar is a choice worth arguing.** Where the project simply does what its
  framework does, or a one-line comment at the setting carries the reasoning,
  the comment is enough.
- **Name what would retire it**, as for a documented exception in
  [Documented Exceptions](../coding/general.md#documented-exceptions).

### Record repository settings as commands in one place

Rulesets, Dependabot alerts and security updates, Actions secrets, the Pages
source, the dependency graph: none of these live in a file, so none are
reviewed, and a repository recreated from its contents comes back without them.
Record each one in the `## GitHub Config` section of
`docs/building-and-testing.md` (`CONTRIBUTING.md` in a repository with no
`docs/`), as:

- the command that applies it (`gh api --method POST …`), so it can be
  re-applied rather than reconstructed from the UI;
- the command that verifies it, with the expected output — several of these
  settings report success while doing nothing (an `active` ruleset with an empty
  `include` list, a `PUT` that returns `204` and prints nothing);
- one sentence of why, where the setting is not self-explanatory.

The publishing *target* — a PyPI trusted publisher and the GitHub environments
it names — is release configuration, in `docs/releasing-and-publishing.md`,
linked from that section. A shared setting the project cannot apply (rulesets on
a private repository on a free plan) is a documented exception in
`docs/guidelines.md`, with the commands to apply once it retires. What the
rulesets contain is in
[repository.md](../project-setup/repository.md#protect-the-default-branch-and-release-tags).

## Keeping it true

### Generate references from the code, and check them

Generate what can be derived from the code, and fail the build when the
committed copy differs:

| Generated | From | Tasks | Command |
|---|---|---|---|
| `docs/cli-reference.md` — the whole file | the Typer app | `clidocs` / `lint-clidocs` | `iglootools docs cli` |
| the field tables in `docs/config-reference.md` | the config models | `configdocs` / `lint-configdocs` | the project's own script, since the models are its own |
| the Module Overview in `docs/architecture.md` | the import graph | `depgraph` / `lint-depgraph` | `iglootools docs depgraph` |
| the "On this page" list in each long document | its `##` and `###` headings | `toc` / `lint-toc` | `iglootools docs toc` |

- **Every generator has a `lint-*` task, and `lint` runs it.** The tasks are
  one-line calls to the [`iglootools`](../project-setup/iglootools-cli.md)
  commands with `--check`, which exit non-zero when the output would change and
  name the task that regenerates it. The task set is in
  [python-tooling.md](../project-setup/python-tooling.md#mise-tasks).
- **Any document long enough to scroll gets a table of contents**:
  `mise run toc --add <file>` puts it between `<!-- toc -->` and
  `<!-- tocstop -->`.
- **Mark what is generated, in the file.** A whole generated file starts with
  `<!-- AUTO-GENERATED by: mise run clidocs — do not edit manually -->`. A
  generated section inside a hand-written document is fenced, and what the
  generator cannot derive goes in the prose outside the markers:

  ```markdown
  <!-- BEGIN CONFIGREF:VOLUMES (auto-generated by: mise run configdocs — do not edit manually) -->
  …
  <!-- END CONFIGREF:VOLUMES -->
  ```

  Keep the Markdown formatter out of both, or it reformats what the generator
  wrote and its `lint-*` task fails on the next run:
  [formatting.md](../project-setup/formatting.md#leave-generated-documents-to-their-generator).
- **A CLI project shows itself in the README** with an
  [asciinema](https://asciinema.org/) recording near the top, re-recorded on a
  major release when the demo script gains the new commands.
- **Broken links** are caught by the shared link checker — see
  [shared-workflows.md](../project-setup/shared-workflows.md#call-the-shared-link-checker-instead-of-copying-it).

### Name which document each kind of change updates

The `Documentation` checklist in `docs/guidelines.md` maps a kind of change to
the documents it has to touch: a new config field updates `config-reference.md`
(regenerate, then the prose the generator cannot derive) and `usage.md`; a
change to an entity or invariant updates `domain.md`; a new module updates the
layering rules in `architecture.md`.

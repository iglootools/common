# Documentation Guidelines

Where an iglootools project keeps its documentation, which documents it writes and under what
names, and how agents are pointed at them. Read this when adding, renaming or restructuring
`README.md`, `CONTRIBUTING.md`, `CLAUDE.md` or anything under `docs/`.

The principle behind every rule here is in
[Documentation for people first, agent configuration for the gaps](../../philosophy.md#documentation-for-people-first-agent-configuration-for-the-gaps):
the documentation is written for people, in the project's docs, and `CLAUDE.md`, skills and
hooks only decide when an agent reads it. A rule that exists only in agent configuration is
invisible to the people reviewing the agent's work, so nobody notices when it goes stale.

## Where documentation lives

### Keep project documentation at the conventional paths

Two paths are fixed across iglootools projects, because the `guidelines` skill reads them by
convention rather than by being pointed at them:

| Path | Holds |
|---|---|
| `CONTRIBUTING.md` | the index of the project's documentation for anyone changing it — see [below](#scaffold-contributingmd-as-the-documentation-index) |
| `docs/guidelines.md` | deviations from the shared guidelines, which shared sections are out of scope, rules of the project's own, its implementation checklists, and an index of the conventions set for particular areas of the code |

Renaming one does not produce an error: the skill finds nothing, concludes the project documented
nothing project-specific, and applies the shared guidelines as written. A project's deviations
then stop being consulted with nothing to say so, which is the failure this repository exists to
prevent. Adding a file later needs no announcement — put it at the path and it is read.

**Implementation checklists live in `docs/guidelines.md`, not in a file of their own.** A
checklist is a project rule applied at a particular moment — adding a CLI command, a config
field, a migration — so it belongs with the project's other rules, under a heading that names the
task. A checklist long enough to crowd the rest out moves to its own file under `docs/`, linked
from `docs/guidelines.md` beside the task it covers; the link is what makes it discoverable, so a
checklist nothing links to is one nobody runs.

### Keep `docs/guidelines.md` lean, and index area conventions from it

**`docs/guidelines.md` is loaded into every agent session**, after the shared guidelines, by the
plugin's `SessionStart` hook — that is what lets a project rule override a shared one at the
moment code is written rather than at review. Two consequences:

- Keep it to rules, exceptions and checklists, and move anything long — a checklist that crowds
  the rest out, an area's full conventions, a testing strategy — to its own file under `docs/`,
  linked from here. Every line in it is paid for in every session.
- Index area conventions here. When the people who own an area — storage, the CLI, the event
  schema, CI — write conventions for it, keep them in their own document and list it here next
  to the paths it governs. The listing is what an agent sees at write time; the skill tells it to
  read the linked document before touching those paths. A project may additionally wrap a large
  area's conventions in a skill of its own scoped to those paths, but the document stays the
  source.

Name the document `docs/<area>-conventions.md`, open it by linking back to the index entry, and
list it in a table under an `## Area conventions` heading, as photree does:

```markdown
## Area conventions

Read the linked document in full before changing files under these paths.

| Paths | Conventions |
|-------|-------------|
| `photree/cli/`, `photree/*/cli/` — and adding a command anywhere | [cli-conventions.md](./cli-conventions.md) — command hierarchy, options, progress, exit codes |
```

The paths column is the trigger. An area document that is only mentioned in prose ("the CLI
conventions are in …") gives an agent nothing to match a file against, so it is read when
someone happens to remember it rather than when a change reaches the area.

`docs/guidelines.md` holds deviations from the *shared* guidelines. A decision about the
project's own stack — which linter, which framework feature, how far to follow an upstream
template — is not a deviation from anything, and belongs in the
[architecture decision record](#record-architectural-decisions-in-an-append-only-log). Filed as a
"deviation", it is loaded into every session and invites someone to "fix" it back to a shared
rule it never contradicted.

### Split `README.md`, `CONTRIBUTING.md` and `docs/` by reader

| File | Reader | Holds |
|---|---|---|
| `README.md` | someone deciding whether to use the project | what it does, badges, a demo, main use cases, non-goals, known limitations, philosophy, related projects, links to the user documentation, a link to `CONTRIBUTING.md`, the license |
| `CONTRIBUTING.md` | someone changing it | the index of the contributor documentation, one line per document — nothing else |
| `docs/` | either | every document longer than a README section, user-facing and contributor-facing alike |

The README links out rather than inlining: installation, usage and the feature list are
documents under `docs/`, and the README says one sentence and links. A README that grows a
"Development" section duplicates `CONTRIBUTING.md`, and the two drift — the README is the one
people read and the index is the one the skill reads, so the drift is invisible to whichever
side did not change.

Non-goals and known limitations go in the README, not further down. They are what a prospective
user most needs before installing, and stating them is also what stops a contributor from
"fixing" a limitation that is deliberate.

**Link with relative paths**, so the links resolve on GitHub, in the editor, and in a fork alike.
Two exceptions:

- When the README is also the package's long description (`readme = "README.md"` in
  `pyproject.toml`), PyPI renders it without the repository, so every link from the README into
  the repository — `docs/`, `CONTRIBUTING.md` — is broken there. Use absolute GitHub URLs
  (`https://github.com/iglootools/<repo>/blob/main/docs/usage.md`) in that README.
- Links to the shared guidelines point at `https://github.com/iglootools/common/...`, since they
  live in another repository. Link to them rather than naming them in prose: shared files are
  renamed, and a link the link checker can follow fails loudly where a bare file name ("see
  `coding.md`") silently points at nothing.

### Scaffold `CONTRIBUTING.md` as the documentation index

Every iglootools project has a `CONTRIBUTING.md` at the root. GitHub links it from the pull
request and issue forms, so it is where a contributor lands, and it is the one file the skill
reads to find everything else. It is an index, not a manual: one line per document, saying what
the reader will find there, with the content in the document itself. The README keeps the user's
view and links to `CONTRIBUTING.md` for everything about changing it, rather than repeating the
list.

Start from this scaffold, delete the lines for documents the project does not have, and add the
ones only it has:

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

A repository with no `docs/` — this one — still has the `CONTRIBUTING.md`, indexing whatever
plays those roles, and says why its shape differs.

### Make `CLAUDE.md` a list of imports

A project's `CLAUDE.md` holds `@` imports of the project's own documents, one line each saying
what the document covers, plus only what an agent needs and a person does not — for example,
which MCP server to ask about a framework that moves faster than any model's training data. It
does not restate the shared guidelines, nor anything the plugin already delivers, nor the
documents it imports. A rule written there instead of in `docs/` is the only copy of that rule,
and no human contributor ever reads it.

```markdown
# CLAUDE.md

## Architecture

Module dependency graph and layering: @docs/architecture.md

Domain concepts (…): @docs/domain.md

## Guidelines

Shared iglootools guidelines come from the `iglootools` plugin, enabled in
`.claude/settings.json` and installed once per machine: @docs/setup-development-environment.md

## Build & Test Commands

@docs/building-and-testing.md

## Releasing and Publishing

@docs/releasing-and-publishing.md
```

- **Do not import `docs/guidelines.md`.** The `SessionStart` hook already emits it, so an import
  loads it twice.
- **Import what most changes need, not everything.** Every import is loaded into every session.
  The documents nearly any change needs — domain, architecture, build and test — earn it. A
  generated reference that runs to a thousand lines does not: `CONTRIBUTING.md` lists it, and the
  agent reads it when the change reaches it.
- **Rename the import with the file.** An `@` import of a file that no longer exists does not
  produce an error; the session simply starts without that document.
- A project with nothing to import may have no `CLAUDE.md` at all.

## What to write

### Write the documents the project's shape calls for

These are recommended rather than fixed: the skill finds them through `CONTRIBUTING.md`, so their
names do not have to match. Matching them anyway means a reader who knows one iglootools project
knows where to look in the next. Create each one when the project has something to put in it, not
as an empty placeholder — a placeholder reads as "documented" in the index and holds nothing.

**For contributors:**

| Path | Holds | Write it when |
|---|---|---|
| `docs/setup-development-environment.md` | how to get the project running: the toolchain, the editor, installing the plugin | always |
| `docs/building-and-testing.md` | the task reference, testing strategy, the checks CI runs, and the [GitHub settings](#record-repository-settings-as-commands-in-one-place) | always |
| `docs/releasing-and-publishing.md` | how a release is cut, what triggers what, and the publishing target's configuration | the project releases anything |
| `docs/domain.md` | the concepts the code models, in the domain's vocabulary: what each one is, how they relate, and the invariants between them; ends with a glossary | the project models anything a newcomer would have to learn — nearly always |
| `docs/architecture.md` | how the code is organized: modules or layers, what depends on what, the reasoning behind the import contracts, and where a new piece of code goes | there is more than one module |
| `docs/internals.md` | runtime behavior and the reasoning behind it: algorithms, on-disk formats, the external commands invoked, and design decisions as `Why …` subsections next to the behavior they explain | the behavior is not obvious from the code, or a decision would otherwise be relitigated |
| `docs/architecture-decision-record.md` | the [decision log](#record-architectural-decisions-in-an-append-only-log) | a choice worth arguing has been made |
| `docs/<area>-conventions.md` | an area's conventions, written by the people who own it | an area has [conventions of its own](#keep-docsguidelinesmd-lean-and-index-area-conventions-from-it) |
| `docs/cli-reference.md` | every command, option and argument | the project ships a CLI — [generate it](#generate-references-from-the-code-and-check-them) |
| `docs/config-reference.md` | every configuration field: type, default, validation rule; examples under `docs/config-examples/` | the project reads a configuration file |

**For users**, linked from the README:

| Path | Holds |
|---|---|
| `docs/installation.md` | system requirements, install commands, optional extras, shell completion |
| `docs/usage.md` | worked examples by task, linking to the references for the exhaustive lists |
| `docs/features.md` | the full feature list the README summarizes |
| `docs/tutorial.md` | one end-to-end walkthrough of a realistic setup, when usage examples are not enough |

The split is by question, so keep each document to its own: *what* the project is about
(`domain.md`), *where* the code for it lives (`architecture.md`), *how* and *why* it behaves the
way it does (`internals.md`), and *exactly what* a user can type or configure (the references). A
reference that explains concepts, or a domain document that lists every field, is two documents
that will drift apart. Open each document with a sentence saying who it is for and what question
it answers, and link to the neighbouring documents for the questions it does not.

### Use one name per role

The file name matches the document's title — `# Building and Testing` lives in
`building-and-testing.md` — so a reader who knows the title can find the file, and every project
names the same role the same way.

| Role | Name | Not |
|---|---|---|
| development environment | `setup-development-environment.md` | `project-setup.md` — it collides with the shared guidelines' `project-setup/`, which is about configuring a repository, not a workstation |
| build and test | `building-and-testing.md` | `build-test.md` |
| release and publish | `releasing-and-publishing.md` | `release-publish.md` |
| decision log | `architecture-decision-record.md` | `adr/`, `decisions.md` |
| area conventions | `<area>-conventions.md` | |

Renaming a document is a change to every file that points at it: the `CONTRIBUTING.md` line,
the `CLAUDE.md` import, cross-links between documents, the README's absolute URLs, and any
`description` in `mise.toml` that names the file. Search for the old name rather than relying on
the link checker: it runs on a schedule rather than on the pull request, it does not read
`CLAUDE.md` imports, and it cannot see a file name mentioned without a link.

### Record architectural decisions in an append-only log

A decision that affects more than one component, and that someone would otherwise argue about
again, goes in `docs/architecture-decision-record.md` (see
[Document the why, not the what](../../philosophy.md#document-the-why-not-the-what)). One file,
entries appended newest at the bottom, each numbered and titled with the decision itself:

```markdown
## ADR-004 — Let retired URLs 404 rather than ship meta-refresh stubs

**Date:** when the decision was taken (plus **Recorded:**, if it was written up later)
**Status:** Accepted (or: Accepted — supersedes ADR-00N)

### Context
### Decision
### Rationale
### Consequences
```

- **Do not edit an entry to change the decision.** Add a new one whose `Status` names the
  entry it supersedes. The log is useful because it shows what was believed at the time;
  an entry rewritten in place erases the reasoning a later reader needs to decide whether the
  conditions behind it still hold.
- **The bar is a choice worth arguing.** Where the project simply does what its framework does,
  or a one-line comment at the setting carries the reasoning, the comment is enough.
- **Name what would retire it**, as for a documented exception in
  [Applying these guidelines](../../README.md#applying-these-guidelines).

### Record repository settings as commands in one place

Rulesets, Dependabot alerts and security updates, Actions secrets, the Pages source, the
dependency graph — none of these live in a file, so none of them are reviewed, and a repository
recreated from its contents comes back without them. Record each one in the
`## GitHub Config` section of `docs/building-and-testing.md`, as:

- the command that applies it (`gh api --method POST …`), so it can be re-applied rather than
  reconstructed from the UI;
- the command that verifies it, with the expected output — several of these settings report
  success while doing nothing (an `active` ruleset with an empty `include` list, a `PUT` that
  returns `204` and prints nothing);
- one sentence of why, where the setting is not self-explanatory.

Keep them in that one section. Split across files, re-applying them means finding every file
that holds one, and the one that is missed is not noticed until it is needed. The configuration
of the publishing *target* — a PyPI trusted publisher and the GitHub environments it names — is
release configuration and belongs in `docs/releasing-and-publishing.md`, which the GitHub
section links to.

Where the project cannot apply a shared setting — rulesets on a private repository on a free
plan — the documented exception goes in `docs/guidelines.md`, with the commands to apply once
the exception retires. A repository with no `docs/` records the settings in `CONTRIBUTING.md`.
What the rulesets themselves should contain is in
[repository.md](repository.md#protect-the-default-branch-and-release-tags).

## Keeping it true

### Generate references from the code, and check them

A reference written by hand drifts the first time someone adds an option and forgets the
document, and nothing reports it. Generate what can be derived from the code, and fail the
build when the committed copy differs:

| Generated | From | Tasks |
|---|---|---|
| `docs/cli-reference.md` — the whole file | the Typer app | `clidocs` / `clidocs-check` |
| the field tables in `docs/config-reference.md` | the config models | `configdocs` / `configdocs-check` |
| the Module Overview in `docs/architecture.md` | the import graph | `depgraph` / `depgraph-check` |

- **Every generator has a `-check` task, and `check` runs it.** A generator nobody is forced to
  run is a hand-maintained document with extra steps: it drifts just as silently. The generator
  takes `--check`, exits non-zero when the output would change, and the error says which task
  regenerates it. The task set is in
  [python-tooling.md](python-tooling.md#mise-tasks).
- **Mark what is generated, in the file.** A whole generated file starts with
  `<!-- AUTO-GENERATED by: mise run clidocs — do not edit manually -->`. A generated section
  inside a hand-written document is fenced, so the prose around it stays editable:

  ```markdown
  <!-- BEGIN CONFIGREF:VOLUMES (auto-generated by: mise run configdocs — do not edit manually) -->
  …
  <!-- END CONFIGREF:VOLUMES -->
  ```

  Without the marker, an edit to generated text looks like a normal change, passes review, and
  is overwritten without a trace on the next regeneration. What the generator cannot derive
  goes in the prose outside the markers.
- **A CLI project shows itself in the README** with an [asciinema](https://asciinema.org/)
  recording near the top, re-recorded on a major release when the demo script gains the new
  commands.

Broken links are caught by the shared link checker — see
[shared-workflows.md](shared-workflows.md#call-the-shared-link-checker-instead-of-copying-it).

### Name which document each kind of change updates

"Keep the documentation in sync with the codebase" is true and checks nothing. The
`Documentation` checklist in `docs/guidelines.md` maps a kind of change to the documents it has
to touch — a new config field updates `config-reference.md` (regenerate, then the prose the
generator cannot derive) and `usage.md`; a change to an entity or invariant updates `domain.md`;
a new module updates the layering rules in `architecture.md`. An agent walking the diff against
the checklist before calling a change done can only check what the checklist names.

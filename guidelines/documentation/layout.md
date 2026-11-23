# Documentation Layout

Where an iglootools project keeps its documentation, which documents it writes
and under what names, and how agents are pointed at them. Read this when adding,
renaming or restructuring `README.md`, `CONTRIBUTING.md`, `AGENTS.md` or
anything under `docs/`.

The documentation is written for people, in the project's docs; `AGENTS.md`,
skills and hooks only decide when an agent reads it, as
[Documentation for people first](../philosophy.md#documentation-for-people-first-agent-configuration-for-the-gaps)
argues. What makes each document good is in [types.md](types.md).

<!-- toc -->
**On this page**

- [Where documentation lives](#where-documentation-lives)
  - [Keep the project's guidelines at conventional paths, and the entry file lean](#keep-the-projects-guidelines-at-conventional-paths-and-the-entry-file-lean)
  - [Split `README.md`, `CONTRIBUTING.md` and `docs/` by reader](#split-readmemd-contributingmd-and-docs-by-reader)
  - [Make the README a pitch that links out](#make-the-readme-a-pitch-that-links-out)
  - [Keep `AGENTS.md` a short map](#keep-agentsmd-a-short-map)
- [What to write](#what-to-write)
  - [Write the documents the project's shape calls for, one name per role](#write-the-documents-the-projects-shape-calls-for-one-name-per-role)
  - [Record architectural decisions in an append-only log](#record-architectural-decisions-in-an-append-only-log)
  - [Record repository settings as commands in one place](#record-repository-settings-as-commands-in-one-place)
- [Keeping it true](#keeping-it-true)
  - [Generate references from the code, and check them](#generate-references-from-the-code-and-check-them)
  - [Give every document longer than two screens a generated table of contents](#give-every-document-longer-than-two-screens-a-generated-table-of-contents)
  - [Name which document each kind of change updates](#name-which-document-each-kind-of-change-updates)
<!-- tocstop -->

## Where documentation lives

### Keep the project's guidelines at conventional paths, and the entry file lean

A project's guidelines take one of two forms: `docs/guidelines.md`, or a
`docs/guidelines/` directory, subfolders allowed, whose entry file is
`docs/guidelines/README.md`. A subsystem may add its own, `<dir>/guidelines.md`
or `<dir>/guidelines/**/*.md`, which govern every file under `<dir>`. The
guidelines write `docs/guidelines.md` for the entry file, whichever form a
project uses.

**Why:** the plugin finds these files by their path, not by being pointed at
them. Guidelines kept next to the code they govern are found by whoever changes
that code, as
[Let the people who own an area set its conventions](../philosophy.md#documentation-for-people-first-agent-configuration-for-the-gaps)
argues.

- **The entry file holds rules and links**: deviations from the shared
  guidelines, which shared sections are out of scope, the project's own rules,
  and a link to everything else. It is loaded into every agent session, after
  the shared guidelines, which it overrides as
  [applying-the-guidelines.md › Precedence](../applying-the-guidelines.md#precedence)
  describes, so it holds only what every change needs, as
  [writing-guidelines.md](writing-guidelines.md#keep-the-always-on-guidelines-to-what-every-change-needs)
  asks. The other guidelines files are read when a change reaches what they
  govern.
- **Anything long moves into its own file under `docs/guidelines/`**, linked
  from the entry under a heading that names the task: an implementation
  checklist (adding a CLI command, a config field, a migration), a testing
  strategy.
- **An area's conventions live with the area.** The people who own it write
  them. An area that is one directory (storage, the event schema) gets that
  directory's `guidelines.md`, and nothing needs to point at it. An area spread
  across directories gets `docs/guidelines/<area>.md`, indexed from the entry
  with the paths it governs, since a document only mentioned in prose is not
  read when a change reaches the area. A skill of the project's own may also
  deliver it, but the document stays the source. photree's index:

  ```markdown
  ## Area conventions

  Read the linked document in full before changing files under these paths.

  | Paths | Conventions |
  |-------|-------------|
  | `photree/cli/`, `photree/*/cli/` — and adding a command anywhere | [cli.md](./guidelines/cli.md) — command hierarchy, options, progress, exit codes |
  ```

- **Decisions about the project's own stack**, such as which linter, which
  framework feature, or how far to follow an upstream template, are not
  deviations from anything. They go in the
  [architecture decision record](#record-architectural-decisions-in-an-append-only-log).

### Split `README.md`, `CONTRIBUTING.md` and `docs/` by reader

| File | Reader | Holds |
|---|---|---|
| `README.md` | someone deciding whether to use the project | the case for the project, and links to everything else, as [below](#make-the-readme-a-pitch-that-links-out) |
| `CONTRIBUTING.md` | someone changing it | the index of the contributor documentation, one line per document — nothing else |
| `docs/` | either | every document longer than a README section, user-facing and contributor-facing alike |

**Why:** each reader comes with a different question, and a file that answers
both answers neither: a prospective user does not need the build instructions,
and a contributor needs more than the pitch.

- **Every project has a `CONTRIBUTING.md`**, even one with no `docs/`, where it
  indexes whatever plays those roles and says why its shape differs. GitHub
  links it from the pull request and issue forms, and the skill reads it to find
  everything else. Start from
  [templates/CONTRIBUTING.md.template](templates/CONTRIBUTING.md.template),
  delete the lines for documents the project does not have, and add the ones
  only it has.
- **Link with relative paths**, so links resolve on GitHub, in the editor and in
  a fork alike. The one exception is a README that PyPI also renders
  ([below](#make-the-readme-a-pitch-that-links-out)). Link to the
  shared guidelines at `https://github.com/iglootools/common/...` rather than
  naming a file in prose, so the link checker notices when it is renamed.

### Make the README a pitch that links out

The README is for someone deciding whether to use the project. It holds what the
project does, badges, a demo, the main use cases, non-goals and known
limitations, its philosophy, related projects, links to the user documentation
and to the
[documents for both readers](#write-the-documents-the-projects-shape-calls-for-one-name-per-role),
a link to `CONTRIBUTING.md`, and the license.

**Why:** every prospective user reads it, on GitHub and on PyPI, and decides
from it. Anything longer than a section belongs in a document they can choose to
open.

- **Installation, usage and the feature list get one sentence and a link.**
  There is no "Development" section: that is `CONTRIBUTING.md`.
- **State non-goals and known limitations.** A prospective user needs them
  before installing, not after.
- **A CLI project embeds its demo near the top**, as
  [cli-demo.md](../project-setup/cli-demo.md#embed-the-cast-at-the-top-of-the-readme)
  describes.
- **Use absolute GitHub URLs when the README is also the package's long
  description** (`readme = "README.md"`), such as
  `https://github.com/iglootools/<repo>/blob/main/docs/usage.md`. PyPI renders
  it without the repository, so relative links break there.

### Keep `AGENTS.md` a short map

`AGENTS.md` at the project root is what every coding agent reads first. It is a
map, not a manual: what the project is, the commands that build and check it,
the guidelines to read, where the documentation index is, and what only an agent
needs, such as which MCP server answers questions about a framework that moves
faster than any model's training data.

**Why:** it is read in every session, so every line costs, and a rule kept only
there is invisible to the people who review the agent's work.

Start from [templates/AGENTS.md.template](templates/AGENTS.md.template),
written for nbkp.

- **Point at `CONTRIBUTING.md` instead of listing documents.** It is the one
  index of the documentation, and a second list drifts from it.
- **Link, do not `@`-import.** An import loads the document into every session,
  needed or not. Write paths as links or in backticks: Claude Code treats a bare
  `@path` as an import.
- **Hold it to a map's limits**, as
  [types.md › Say when to go there, not what is inside](types.md#say-when-to-go-there-not-what-is-inside)
  sets them. Since it is read in every session, what applies only to some files
  belongs in the document that covers them, and nothing agents already receive
  is restated: the shared guidelines, the project's documents,
  `docs/guidelines.md`.
- **Commands may stay, rules may not**: the commands that build and check the
  project, with when to run them, as
  [types.md › Give each fact one home](types.md#give-each-fact-one-home-and-link-to-it)
  allows for commands a reader follows; the rule behind each is cited.

## What to write

### Write the documents the project's shape calls for, one name per role

Create each document when the project has something to put in it, not as an
empty placeholder. The skill finds them through `CONTRIBUTING.md`, so the names
are not enforced, but every project uses the same one per role, matching the
title (`# Building and Testing` lives in `building-and-testing.md`).

**Why:** a contributor moving between projects finds the same document under the
same name, and an empty placeholder is a promise nobody keeps.

**For contributors:**

| Path | Holds | Write it when |
|---|---|---|
| `docs/setup-development-environment.md` (not `project-setup.md`, which collides with the shared guidelines' `project-setup/` about configuring a repository) | how to get the project running: the toolchain, the editor, installing the plugin | always |
| `docs/building-and-testing.md` (not `build-test.md`) | the task reference, testing strategy, the checks CI runs, and the [GitHub settings](#record-repository-settings-as-commands-in-one-place) | always |
| `docs/releasing-and-publishing.md` (not `release-publish.md`) | how a release is cut, what triggers what, and the publishing target's configuration | the project releases anything |
| `docs/architecture.md` | how the code is organized: modules or layers, what depends on what, the reasoning behind the import contracts, and where a new piece of code goes | there is more than one module |
| `docs/internals.md` | runtime behavior and the reasoning behind it: algorithms, on-disk formats, the external commands invoked, and design decisions as `Why …` subsections next to the behavior they explain | the behavior is not obvious from the code, or a decision would otherwise be relitigated |
| `docs/architecture-decision-record.md` (not `adr/`, `decisions.md`) | the [decision log](#record-architectural-decisions-in-an-append-only-log) | a choice worth arguing has been made |
| `docs/guidelines/<area>.md`, `<dir>/guidelines.md` | an area's conventions, written by the people who own it | an area has [conventions of its own](#keep-the-projects-guidelines-at-conventional-paths-and-the-entry-file-lean) |

**For both**, linked from the README and from `CONTRIBUTING.md`:

| Path | Holds | Write it when |
|---|---|---|
| `docs/domain.md` | the concepts the code models, in the domain's vocabulary: what each one is, how they relate, and the invariants between them; ends with a glossary | the project models anything a newcomer would have to learn — nearly always |
| `docs/cli-reference.md` | every command, option and argument | the project ships a CLI — [generate it](#generate-references-from-the-code-and-check-them) |
| `docs/config-reference.md` | every configuration field: type, default, validation rule; examples under `docs/config-examples/` | the project reads a configuration file |

**For users**, linked from the README:

| Path | Holds |
|---|---|
| `docs/installation.md` | system requirements, install commands, optional extras, shell completion |
| `docs/usage.md` | worked examples by task, linking to the references for the exhaustive lists |
| `docs/features.md` | the full feature list the README summarizes |
| `docs/tutorial.md` | one end-to-end walkthrough of a realistic setup, when usage examples are not enough |

- **Each document is one kind**, written as [types.md](types.md) describes.
- **Renaming a document changes every file that points at it**: the
  `CONTRIBUTING.md` line, cross-links, the README's
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

**Why:** without the reasoning on record, the next person to question the choice
reargues it from scratch, or reverses it without knowing what it was protecting.

- **Write it as a [record](types.md#record)**: append, supersede rather than
  edit, and name what would retire the decision.
- **The bar is a choice worth arguing.** Where the project simply does what its
  framework does, or a one-line comment at the setting carries the reasoning,
  the comment is enough.

### Record repository settings as commands in one place

Record each setting that lives outside the repository's files, such as
rulesets, Dependabot alerts and security updates, Actions secrets, the Pages
source and the dependency graph, in the `## GitHub Config` section of
`docs/building-and-testing.md` (`CONTRIBUTING.md` in a repository with no
`docs/`).

**Why:** none of these settings live in a file, so none are reviewed, and a
repository recreated from its contents comes back without them.

Record each one as:

- the command that applies it (`gh api --method POST …`), so it can be
  re-applied rather than reconstructed from the UI;
- the command that verifies it, with the expected output — several of these
  settings report success while doing nothing (an `active` ruleset with an empty
  `include` list, a `PUT` that returns `204` and prints nothing);
- one sentence of why, where the setting is not self-explanatory.

The publishing *target* — a PyPI trusted publisher and the GitHub environments
it names — is release configuration, in `docs/releasing-and-publishing.md`,
linked from that section. What the rulesets contain, and what to do when a plan
cannot have them, is in
[repository.md](../project-setup/repository.md#protect-the-default-branch-and-release-tags).

## Keeping it true

### Generate references from the code, and check them

Generate what can be derived from the code, and fail the build when the
committed copy differs.

**Why:** a hand-kept reference drifts from the code without failing anything; a
generated one with a check cannot.

| Generated | From | Tasks | Command |
|---|---|---|---|
| `docs/cli-reference.md` — the whole file | the Typer app | `clidocs` / `lint-clidocs` | `iglootools docs cli` |
| the field tables in `docs/config-reference.md` | the config models | `configdocs` / `lint-configdocs` | the project's own script, since the models are its own |
| the Module Overview in `docs/architecture.md` | the import graph | `depgraph` / `lint-depgraph` | `iglootools docs depgraph` |
| the "On this page" list in each long document | its `##` and `###` headings | `toc` / `lint-toc` | `iglootools docs toc` |

- **Every generator has a `lint-*` task, and `lint` runs it.** The tasks are
  one-line calls to the [`iglootools`](../project-setup/iglootools-cli.md)
  commands with `--check`, which exit non-zero when the output would change and
  name the task that regenerates it. Their names follow
  [mise.md › Name tasks by family](../project-setup/mise.md#name-tasks-by-family).
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
- **Broken links** are caught by the shared link checker — see
  [shared-workflows.md](../project-setup/shared-workflows.md#call-the-shared-link-checker-instead-of-copying-it).

### Give every document longer than two screens a generated table of contents

Every Markdown document of 80 lines or more with a `##` or `###` heading
carries one "On this page" list, generated from those headings between
`<!-- toc -->` and `<!-- tocstop -->`, after the opening paragraph and before
the first section. `lint-toc` fails on a document that needs one and has none,
on one with two, and on one out of date; `mise run toc` adds and regenerates
them.

**Why:** the list shows a reader the whole document before they scroll, and
lets an agent pick the section it needs instead of reading the file whole. A
shorter document is read at a glance, so the list would only repeat it.

- **Length, not heading depth, decides:** a long page of `##` sections needs
  the list as much as a nested one. A shorter document may keep a list it has;
  it stays up to date. `--min-lines <n>` on both tasks moves the threshold.
- **Exempt, and left out by the command itself:** `AGENTS.md`, `CLAUDE.md` and
  `SKILL.md`, which agents read whole, often every session, so a list only costs
  tokens; and whole generated files, which start with `<!-- AUTO-GENERATED`.
- **Exempt anything else with `--exclude <glob>`** on both tasks, with a comment
  saying why: other prompts an agent loads (common's `agents/*.md` and
  `skills/**`), or pages whose site renders its own table of contents
  (`content/**`).

### Name which document each kind of change updates

The `Documentation` checklist in `docs/guidelines.md` maps a kind of change to
the documents it has to touch: a new config field updates `config-reference.md`
(regenerate, then the prose the generator cannot derive) and `usage.md`; a
change to an entity or invariant updates `domain.md`; a new module updates the
layering rules in `architecture.md`.

**Why:** a change that does not say which documents it reaches leaves them to be
noticed later, by a reader who finds them wrong.

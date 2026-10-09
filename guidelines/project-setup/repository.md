# Repository Conventions

What every iglootools repository carries regardless of language, and where each project type
goes from here.

- Github build/test/release workflows — see [workflows.md](workflows.md)
- `git config user.email "<email>"` and `git config user.name "<name>"` in the project.
- A `CONTRIBUTING.md` indexing the project's documentation — see [below](#scaffold-contributingmd-as-the-documentation-index)

### Keep project documentation at the conventional paths

Two paths are fixed across iglootools projects, because the `guidelines` skill reads them by
convention rather than by being pointed at them:

| Path | Holds |
|---|---|
| `CONTRIBUTING.md` | the index of the project's documentation for anyone changing it — see [below](#scaffold-contributingmd-as-the-documentation-index) |
| `docs/guidelines.md` | deviations from the shared guidelines, which shared sections are out of scope, rules of the project's own, and its implementation checklists |

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

Because these are conventions, a project's `CLAUDE.md` should not restate them, nor restate any
guidance the plugin already delivers. What belongs there is what only that project knows: its
architecture, its domain concepts, its build and release entry points — usually as `@` imports of
the documents below.

### Write the documents the project's shape calls for

These are recommended rather than fixed: the skill finds them through `CONTRIBUTING.md`, so their
names do not have to match. Matching them anyway means a reader who knows one iglootools project
knows where to look in the next. Create each one when the project has something to put in it, not
as an empty placeholder.

| Path | Holds | Write it when |
|---|---|---|
| `docs/domain.md` | the concepts the code models, in the domain's vocabulary: what each one is, how they relate, and the invariants between them | the project models anything a newcomer would have to learn — nearly always |
| `docs/architecture.md` | how the code is organized: modules or layers, what depends on what, and where a new piece of code goes | there is more than one module |
| `docs/internals.md` | runtime behavior and the reasoning behind it: algorithms, on-disk formats, the external commands invoked, design decisions and their trade-offs | the behavior is not obvious from the code, or a decision would otherwise be relitigated |
| `docs/cli-reference.md` | every command, option and argument | the project ships a CLI — generate it (the `clidocs` task in [CLI Projects](#cli-projects)) rather than writing it by hand |
| `docs/config-reference.md` | every configuration field: type, default, validation rule, and an example | the project reads a configuration file |
| `docs/setup-development-environment.md` | how to get the project running, including installing the plugin | always |

The split is by question, so keep each document to its own: *what* the project is about
(`domain.md`), *where* the code for it lives (`architecture.md`), *how* and *why* it behaves the
way it does (`internals.md`), and *exactly what* a user can type or configure (the references). A
reference that explains concepts, or a domain document that lists every field, is two documents
that will drift apart.

### Scaffold `CONTRIBUTING.md` as the documentation index

Every iglootools project has a `CONTRIBUTING.md` at the root. GitHub links it from the pull
request and issue forms, so it is where a contributor lands, and it is the one file the skill
reads to find everything else. It is an index, not a manual: one line per document, saying what
the reader will find there, with the content in the document itself. The README keeps the user's
view — what the project does, how to install and use it — and links to `CONTRIBUTING.md` for
everything about changing it, rather than repeating the list.

Start from this scaffold, delete the lines for documents the project does not have, and add the
ones only it has:

```markdown
# Contributing

## Getting started

- [docs/setup-development-environment.md](docs/setup-development-environment.md) — set up the
  toolchain, the editor, and the iglootools Claude Code plugin
- [docs/build-test.md](docs/build-test.md) — build, test, lint, and the checks CI runs
- [docs/release-publish.md](docs/release-publish.md) — cut a release and publish it

## Guidelines

This project follows the shared
[iglootools guidelines](https://github.com/iglootools/common/tree/main/guidelines).
[docs/guidelines.md](docs/guidelines.md) records where it deviates from them, the rules it adds,
and the checklists to run for specific kinds of change.

## Understanding the code

- [docs/domain.md](docs/domain.md) — the domain concepts and how they relate
- [docs/architecture.md](docs/architecture.md) — how the code is organized
- [docs/internals.md](docs/internals.md) — runtime behavior and design decisions

## Reference

- [docs/cli-reference.md](docs/cli-reference.md) — every command and option (generated)
- [docs/config-reference.md](docs/config-reference.md) — every configuration field
```

Link with relative paths, so the links resolve on GitHub, in the editor, and in a fork alike.

The README's link to `CONTRIBUTING.md` is the exception when the README is also the package's
long description (`readme = "README.md"` in `pyproject.toml`): PyPI renders it without the
repository, so a relative link there is broken. Use the absolute GitHub URL, as the README's other
links to `docs/` already have to.

### Ignore OS and editor cruft in the committed `.gitignore`

Not in `.git/info/exclude` or a personal `core.excludesfile`. Those are not shared on clone, so
they look like coverage to whoever set them up while giving none to anyone else. This is not
cosmetic: hatchling reads only `.gitignore` when selecting files to package, so a `.DS_Store`
inside the package directory that is ignored only locally gets published inside the wheel.

## Python Projects

See [python-tooling.md](python-tooling.md) for the build backend, the mise and uv configuration,
and the task set.

## CLI Projects

Consider providing:
- `asciinema` demo
- auto-generated `clidocs`/`clidocs-check` tasks for CLI documentation
- Provide preflight checks wherever applicable and troubleshooting instructions with the specific commands that need to be executed to fix the problem.

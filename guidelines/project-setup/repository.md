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

**`docs/guidelines.md` is loaded into every agent session**, after the shared guidelines, by the
plugin's `SessionStart` hook — that is what lets a project rule override a shared one at the
moment code is written rather than at review. Two consequences:

- Keep it to rules, exceptions and checklists, and move anything long — a checklist that crowds
  the rest out, an area's full conventions — to its own file under `docs/`, linked from here.
  Every line in it is paid for in every session.
- Index area conventions here. When the people who own an area — storage, the CLI, the event
  schema, CI — write conventions for it, keep them in their own document and list it here next
  to the paths it governs, for example `` `nbkp/sync/**` — [docs/sync-conventions.md](sync-conventions.md) ``.
  The listing is what an agent sees at write time; the skill tells it to read the linked
  document before touching those paths. A project may additionally wrap a large area's
  conventions in a skill of its own scoped to those paths, but the document stays the source.

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

### Merge pull requests with a merge commit

Merge, do not squash or rebase, unless the project has a reason to do otherwise. A merge commit
keeps every commit of the branch and records where the branch joined `main`, so the history can
always be summarized later — `git log --first-parent` reads as one entry per pull request — while
a squash discards the individual steps for good (see "Preserve data, build tooling around it" in
[philosophy.md](../../philosophy.md#event-driven-append-only-replayable)). That only pays off if
the commits are worth keeping, which is what "one concern per commit" in
[Small, reviewable changes](../../philosophy.md#small-reviewable-changes) asks for.

The default-branch ruleset below enforces it (`allowed_merge_methods: ["merge"]`), so the choice
is made once per repository rather than per pull request. A project with a real reason to differ —
a branch whose commits are throwaway by design, say an automated update that lands as a
series of fix-ups — documents it in its `docs/guidelines.md` and adds the method to its
ruleset, rather than having maintainers pick per merge.

### Protect the default branch and release tags

Every repository carries two rulesets: one on the default branch, one on release tags. Branch
protection is the older mechanism; use rulesets, which cover tags as well and are readable
through the API.

**The default branch** — no deletion, no force-push, changes only through a pull request merged
with a merge commit, and the project's CI check green first:

```bash
gh api --method POST repos/<owner>/<repo>/rulesets --input - <<'EOF'
{
  "name": "main",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    { "type": "pull_request", "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": false,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false,
        "allowed_merge_methods": ["merge"] } },
    { "type": "required_status_checks", "parameters": {
        "strict_required_status_checks_policy": false,
        "do_not_enforce_on_create": false,
        "required_status_checks": [{ "context": "<check>", "integration_id": 15368 }] } }
  ]
}
EOF
```

- `~DEFAULT_BRANCH`, not `refs/heads/main`, so a rename does not leave the ruleset guarding a
  branch that no longer exists.
- `required_approving_review_count: 0`: the rule is that changes go through a pull request, where
  CI runs and the change is recorded — not that a second person approves, which a
  single-maintainer project cannot satisfy. Raise it when a project has more than one maintainer.
- `<check>` is the name of the CI job that runs on every pull request (`test` in the Python
  projects). It must run on *every* pull request: a workflow with `paths` filters never reports
  on a docs-only change, and the required check then blocks that pull request forever. A
  repository with no such job omits the `required_status_checks` rule and says so in its docs.
- `integration_id: 15368` is GitHub Actions, so a status reported under the same name by any other
  app does not satisfy the check.
- `strict_required_status_checks_policy: false`: requiring branches to be up to date with `main`
  makes every Renovate pull request rebase after each merge, for little safety in a repository
  where `main` is tested again on push.

**Release tags** — a published version must keep pointing at the commit it was published from:
the plugin installs by tag, consumers pin shared workflows by the commit a `v*` tag names, and
package versions are derived from tags.

```bash
gh api --method POST repos/<owner>/<repo>/rulesets --input - <<'EOF'
{
  "name": "release tags",
  "target": "tag",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["refs/tags/v*"], "exclude": [] } },
  "rules": [{ "type": "deletion" }, { "type": "update" }]
}
EOF
```

Creation stays allowed, which is what lets a release workflow push a new tag with
`GITHUB_TOKEN`. Add every tag prefix the project releases under (this repository also has
`refs/tags/iglootools--v*`).

**Verify the effect, not the configuration.** A ruleset can be `active` and govern nothing: an
empty `include` list matches no ref, and the UI shows it as enabled all the same. Ask GitHub which
rules actually apply:

```bash
gh api repos/<owner>/<repo>/rules/branches/main -q '[.[].type]'
# expect: ["deletion","non_fast_forward","pull_request","required_status_checks"]
```

For the tag ruleset there is no equivalent endpoint, so read its `conditions.ref_name.include`
back and check it is non-empty and names the project's tag prefixes.

**Record it in the project.** List the two rulesets, the project's `<check>`, and the commands
that created them in the project's GitHub setup documentation, so the configuration can be
re-applied and reviewed rather than living only in the repository settings.

**Private repositories on a free plan cannot have rulesets.** GitHub offers them on private
repositories only with a paid plan. That is a documented exception in the project's
`docs/guidelines.md`, retired when the organization moves to a paid plan or the repository
becomes public.

## Python Projects

See [python-tooling.md](python-tooling.md) for the build backend, the mise and uv configuration,
and the task set.

## CLI Projects

Consider providing:
- `asciinema` demo
- auto-generated `clidocs`/`clidocs-check` tasks for CLI documentation
- Provide preflight checks wherever applicable and troubleshooting instructions with the specific commands that need to be executed to fix the problem.

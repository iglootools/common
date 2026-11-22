# Coding Guidelines

The rules for writing code in any language in an iglootools project, and for
departing from any shared rule. Read it before any code change; the plugin puts
it in every session. [python.md](python.md) gives the Python form of these
rules, and [git.md](git.md) how the change is committed.

<!-- toc -->
**On this page**

- [Documented Exceptions](#documented-exceptions)
  - [Write each departure, and its reason, where a reader will hit it](#write-each-departure-and-its-reason-where-a-reader-will-hit-it)
  - [Name the condition that retires it](#name-the-condition-that-retires-it)
- [Structure](#structure)
  - [Prefer pure functions and immutable data](#prefer-pure-functions-and-immutable-data)
  - [Keep functions short, at one level of abstraction](#keep-functions-short-at-one-level-of-abstraction)
  - [Keep cohesion high and coupling low, at every level](#keep-cohesion-high-and-coupling-low-at-every-level)
  - [Keep riskier changes structurally apart](#keep-riskier-changes-structurally-apart)
  - [Enforce with a tool what a tool can check](#enforce-with-a-tool-what-a-tool-can-check)
- [Presentation at the Edges](#presentation-at-the-edges)
  - [Return data from the core, and render it at the edge](#return-data-from-the-core-and-render-it-at-the-edge)
  - [Escape interpolated text, or keep it apart from markup](#escape-interpolated-text-or-keep-it-apart-from-markup)
- [Errors, Encoding and Time](#errors-encoding-and-time)
  - [Surface every error; never fail silently](#surface-every-error-never-fail-silently)
  - [Use UTF-8 and UTC everywhere](#use-utf-8-and-utc-everywhere)
  - [Pass the current time in](#pass-the-current-time-in)
- [Testability](#testability)
  - [Control what a test needs with a decider, a fake or a cheap real resource](#control-what-a-test-needs-with-a-decider-a-fake-or-a-cheap-real-resource)
  - [Patch only in the three documented cases, and list each one](#patch-only-in-the-three-documented-cases-and-list-each-one)
- [Code Comments](#code-comments)
  - [Comment why, never what](#comment-why-never-what)
- [Naming](#naming)
  - [Name from the domain's vocabulary, then the surface's conventions](#name-from-the-domains-vocabulary-then-the-surfaces-conventions)
- [Command Line](#command-line)
  - [Make the CLI navigable from its own output](#make-the-cli-navigable-from-its-own-output)
  - [Provide preflight checks and troubleshooting commands](#provide-preflight-checks-and-troubleshooting-commands)
  - [Treat a file that exists but cannot be read as an error, never as absent](#treat-a-file-that-exists-but-cannot-be-read-as-an-error-never-as-absent)
  - [Report every failure in a batch, apart from the skips](#report-every-failure-in-a-batch-apart-from-the-skips)
  - [Expand `~` in every path a user writes](#expand--in-every-path-a-user-writes)
  - [Exit with 0, 1 or 2](#exit-with-0-1-or-2)
- [Version Management](#version-management)
  - [Pin or lock every dependency, and have CI assert the lock](#pin-or-lock-every-dependency-and-have-ci-assert-the-lock)
<!-- tocstop -->

## Documented Exceptions

### Write each departure, and its reason, where a reader will hit it

A project or module may depart from any shared guideline or
[philosophy.md](../philosophy.md) principle, or add rules of its own, when it
writes the departure down with a reason a reviewer would accept, naming the rule
it overrides: "we ignore this rule because X, and do Y instead".

**Why:** a documented divergence is a decision; an undocumented one is drift.

- **Project-wide**: in the project's `docs/guidelines.md`, against the rule it
  overrides, extending any entry already there on the same subject.
- **Local or config-level**: a comment at the point of departure, such as a
  `[tool.ruff.lint] ignore` entry with its decision, a `# noqa` with its reason,
  or a comment above a constraint in `pyproject.toml`.
- Legitimate reasons: a performance constraint, an ecosystem convention, a
  third-party limitation, a platform or version still supported.
- "We have not gotten around to it" is debt, not an exception: do the work, or
  record it wherever the project tracks debt.

### Name the condition that retires it

Every exception names the event that would retire it: "revisit when X supports
Y", "drop this once we no longer support Z". One that can never retire says why,
such as a constraint of the platform that will not change. The shape to copy is
[When a dependency lags](python.md#when-a-dependency-lags): next to the setting
it overrides, naming the dependency that forces it and the event that retires
it.

**Why:** without one it becomes permanent once nobody remembers why.

## Structure

### Prefer pure functions and immutable data

Mutate only where it genuinely simplifies the logic.

**Why:** side effects stay at the edges.
See [Functional style preferred](../philosophy.md#functional-style-preferred).

### Keep functions short, at one level of abstraction

Extract named helpers when a function grows beyond ~30 lines or handles several
concerns (scanning, processing and persisting), so it reads as an outline.

**Why:** a long procedure makes the reader rebuild the outline.

### Keep cohesion high and coupling low, at every level

Each function, class, module and package owns one slice, grouped by what changes
together, behind a narrow interface.

**Why:** a typical change lands in one place instead of fanning out. See
[High cohesion, low coupling](../philosophy.md#high-cohesion-low-coupling--at-every-boundary).

- Group by domain first, technical layer second: `album/cli/`, not
  `cli/album.py`. A layer-first tree spreads every feature across every package.
- Expose what callers need, and never reach into another module's internals.
- Keep dependencies one-way and acyclic: two modules that import each other are
  one module split in the wrong place.
- Abstract only a concept the domain has. A change that routinely touches many
  modules means the boundaries are wrong: move them.

### Keep riskier changes structurally apart

Read models and projections apart from commands and event schemas; destructive
operations behind an explicit opt-in.

**Why:** review effort follows the risk: a wrong view is rebuilt, a wrong event
is permanent. See
[Practices that help agents](../philosophy.md#practices-that-are-good-on-their-own-and-help-agents).

### Enforce with a tool what a tool can check

A compiler, type checker, linter, import contract or test, rather than prose.

**Why:** a tool rejects the mistake when it is made; prose works only if read.

## Presentation at the Edges

### Return data from the core, and render it at the edge

Results and errors leave the core as values (records, paths, counts, an error
kind with its fields), never as prose. Wording, colours, relative paths,
indentation and escaping are chosen where the data is presented.

**Why:** the same value prints, exports to CSV or is asserted on, and tests do
not break when a message is reworded.
See [Presentation at the edges](../philosophy.md#presentation-at-the-edges).

- Formatting helpers return unindented lines; the call site indents.

### Escape interpolated text, or keep it apart from markup

Text from users or the filesystem is escaped for the language it lands in
(terminal markup, HTML, Markdown, shell, CSV, SQL), or passed through an API
that keeps data apart: an argument list for a command, never a string; a
parameterized query; a plain-text print.

**Why:** unescaped text fails silently, losing characters or changing meaning
for the inputs nobody tested.

## Errors, Encoding and Time

### Surface every error; never fail silently

Validate inputs and configuration early, and report every failure with a clear
message.

**Why:** a silent failure surfaces later, far from its cause. See
[Errors as first-class values](../philosophy.md#errors-as-first-class-values).

### Use UTF-8 and UTC everywhere

Read and write text as UTF-8, naming the encoding rather than relying on the
platform's default, and store and compare times in UTC.

**Why:** a default encoding differs between machines, and local times are
ambiguous.

### Pass the current time in

Core logic never reads the clock: entry points and tests pass `now` to it.

**Why:** a function that reads the clock cannot be tested for a given moment
without patching.

## Testability

Any ambient state is a parameter defaulting to the real value
(`platform: str = sys.platform`), which tests pass explicitly.

### Control what a test needs with a decider, a fake or a cheap real resource

Use the first that fits:

1. **A decider**: the decision as a pure function over plain values (what to
   report, which exit code), tested with plain values; a few wiring tests cover
   the code that gathers its inputs and acts on its answer.
2. **An injected dependency**: a parameter defaulting to the real implementation
   (command runner, clock, environment, tool locator), given a fake in the test.
   Keep the fakes in one shared test module, and pass real values, not
   stand-ins: a real result, a real model, a config file under the test's
   temporary directory.
3. **A cheap real resource**: a child process, a temporary directory, an
   in-process server.

**Why:** a patched test is tied to where the code looks a name up: it passes
against code that no longer calls it, and breaks on a refactor of the lookup.

### Patch only in the three documented cases, and list each one

(a) a third-party boundary the project wraps, when a real instance needs
infrastructure the test cannot have; (b) a fault no real resource can produce
where the test needs it; (c) process-global state to isolate from the
developer's machine, such as a home directory.

**Why:** an enforced list keeps each patch an exception, not a precedent.

- The project's `docs/guidelines.md` lists each patch in a table: file, what it
  replaces, category, why, what would retire it. A tool enforces the list, so a
  new patch fails the build until removed or listed.
- Patches already in place on adoption are listed as **pending**: the guard
  stops new ones on day one, and the table is the work left.
- A test never touches the developer's real environment: a user-level secret
  store, config or SSH configuration. Choose a test backend once for the suite,
  or pass the path in.

## Code Comments

### Comment why, never what

A comment holds what the code cannot say: why the obvious implementation lost,
an outside constraint (a tool's bug, a spec, a platform quirk), a trade-off and
its rejected alternative, an unchecked invariant, what retires a workaround.

**Why:** names and types already say what the code does, and a comment repeating
them drifts without failing anything. See
[Document the why, not the what](../philosophy.md#document-the-why-not-the-what).

- Keep usage hints: how to run the code
  (`gh workflow run check-links.yml --ref <branch>` atop a workflow).
- When code seems to need a "what" comment, rename, extract a helper, name a
  constant or tighten a type instead, and delete the comment. That includes a
  banner repeating function names and a docstring restating the name.
- Keep a docstring that tells the caller what the signature does not (units,
  ownership, errors, side effects), and any a tool shows users (CLI help,
  API docs).
- Delete commented-out code. Update or remove a comment in the edit that changes
  its reasoning: a wrong comment is worse than none.

## Naming

### Name from the domain's vocabulary, then the surface's conventions

The Python layer is in [python.md](python.md#naming).

**Why:** a name the reader already knows needs no lookup.
See [Name things precisely](../philosophy.md#name-things-precisely).

- **kebab-case on every surface a user types**: commands, sub-commands, long
  options, configuration keys, user-defined slugs, mise tasks, files in `docs/`.
- **A duration** uses the language's duration type, or ends with its unit
  (`timeout_seconds`).
- **Abbreviate only what the domain abbreviates**, listed in the project's
  `docs/domain.md` glossary (`ms` for media source, `src`/`dst`).

## Command Line

### Make the CLI navigable from its own output

Commands point to each other (`check` suggests `troubleshoot`, which suggests
`rebuild`). Paths show relative to the base directory; a suggested command uses
paths relative to the working directory.

**Why:** the user follows the output, and copies a suggested command as-is.

### Provide preflight checks and troubleshooting commands

Check preconditions before acting wherever a failure is predictable, and print
the exact commands that fix a failure.

**Why:** an error that names its fix is resolved in seconds.

- Declare each external program the tool runs in one module, with what it is
  for and how to install it, and check for it once per run, before the first
  change, not once per item.

### Treat a file that exists but cannot be read as an error, never as absent

Report a file as missing only when it does not exist. One that exists but is
empty, truncated or invalid raises an error that says so.

**Why:** code that treats a corrupt file as absent recreates it with fresh
values, silently orphaning whatever referred to the old ones, as photree learned
when a truncated `album.yaml` lost its album ID.

### Report every failure in a batch, apart from the skips

Print each item that failed, with its reason, count failures separately from
skipped items, and exit non-zero if any item failed.

**Why:** a failure counted as a skip, or summed into a total, reads as success
in a script and on the screen alike.

### Expand `~` in every path a user writes

Expand `~` in each path read from configuration or from an argument the shell
did not already expand.

**Why:** users write `~` in configuration files as they do on the command line,
and only the shell expands it there.

### Exit with 0, 1 or 2

Exit 0 on success, including when there is nothing to do; 1 when the operation
or a check fails; 2 on a usage or configuration error.

**Why:** a script can tell "fix the input" from "the work failed", and 2 is what
the CLI framework already uses for a usage error, so the two agree.

## Version Management

### Pin or lock every dependency, and have CI assert the lock

Pin an exact version (`mise use --pin uv@<version>`) or commit a lock file
(`uv.lock`, `mise.lock`), and fail CI when the environment would differ from it,
as
[python-tooling.md](../project-setup/python-tooling.md#assert-the-lock-in-ci-with-uv_locked1-and-in-lint-with-uv-lock---check)
does for uv.

**Why:** a lock nothing asserts drifts, and the build stops being reproducible.
See [Reproducible environments](../philosophy.md#reproducible-environments).

- Give every pin an updater: a pin nothing reads rots silently, as
  [`build-constraint-dependencies`](../project-setup/python-tooling.md#pin-the-build-backend-explicitly)
  would without its custom manager.

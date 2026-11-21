# Coding Guidelines

**These are defaults, not dogma**: a project may depart from any shared
guideline, as [Documented Exceptions](#documented-exceptions) describes.

<!-- toc -->
**On this page**

- [Documented Exceptions](#documented-exceptions)
- [Functional Style](#functional-style)
- [Function size](#function-size)
- [High Cohesion, Low Coupling](#high-cohesion-low-coupling)
- [People and AI Agents](#people-and-ai-agents)
- [Code comments](#code-comments)
- [Charsets](#charsets)
- [Time Management](#time-management)
- [Mocks](#mocks)
- [Presentation at the Edges](#presentation-at-the-edges)
- [Version Management](#version-management)
- [Naming](#naming)
- [Command Line](#command-line)
- [Testability](#testability)
- [No Silent Failures](#no-silent-failures)
<!-- tocstop -->

## Documented Exceptions

A project or module may deviate from any shared guideline, or add rules of its
own, provided the deviation and its reasoning are written down. Divergence for a
documented reason is fine; drift without one is not. The same holds for the
principles in [philosophy.md](../philosophy.md), and between projects: two
iglootools projects may differ, but the difference traces to a decision someone
made, not to one of them falling behind.

- **Put it where a reader will hit it**, not in a separate log:
  - *Project-wide*: the project's `docs/guidelines.md`, stated against the rule
    it overrides. Extend an entry already there on the same subject rather than
    adding a second one beside it; two entries on one subject drift apart.
  - *Local or config-level*: a comment at the point of deviation, such as a
    `[tool.ruff.lint] ignore` entry paired with the decision that motivates it,
    a `# noqa` with its reason beside it, or a comment above the constraint in
    `pyproject.toml`.
- **Meet the bar**: a rationale a reviewer would accept, naming the rule it
  overrides. "We ignore this rule" is drift; "we ignore this rule because X, and
  here is what we do instead" is an exception. Legitimate reasons look like a
  performance constraint, an ecosystem convention, a third-party library
  limitation, or a platform or version still supported.
- **"We have not gotten around to it" is debt, not an exception**: do the work,
  or record it wherever the project tracks debt.
- **Name the condition that would retire it**: "revisit when X supports Y",
  "drop this once we no longer support Z". Those conditions expire, and an
  exception without one silently becomes permanent, because nobody is left who
  remembers what it was working around. The shape to copy is
  [When a dependency lags](python.md#when-a-dependency-lags): the exception sits
  next to the setting it overrides, names the dependency that forces it, and
  names the event that retires it.

## Functional Style

- Prefer functional programming style over procedural style. Use pure functions
  and avoid mutability when possible.

## Function size

Keep functions short and focused. When a function grows beyond ~30 lines or
handles multiple concerns (e.g. scanning, processing, and persisting), extract
named helpers. Each function should do one thing at one level of abstraction.
Prefer reading like a high-level outline that delegates to well-named helpers
over a single long procedure.

## High Cohesion, Low Coupling

Apply the same rule at every level of design: functions, classes, abstractions,
modules, packages.

- Group by what changes together. A module or package should own one coherent
  slice of the domain, so a typical change lands in one place instead of fanning
  out across several.
- Group by domain and subdomain first, technical responsibility second:
  top-level packages are slices of the domain (`album/`, `sync/`), and technical
  layers (`cli/`, `store/`) live inside them. A layer-first tree (`models/`,
  `services/`, `cli/`) spreads every feature across every package.
- Communicate across boundaries through narrow, explicit interfaces. Expose the
  operations callers need, keep the rest private, and do not reach into another
  module's internals.
- Keep dependencies one-directional and acyclic. Two modules that import each
  other are one module split in the wrong place: merge them, or extract what
  they share into a third.
- Introduce an abstraction for a concept that exists in the domain, not to
  shuffle code around. An abstraction whose callers all need to know what is
  behind it adds coupling instead of removing it.
- Treat a change that routinely touches many modules as a signal that the
  boundaries are in the wrong place, and move them rather than adding another
  cross-cutting edit.

See
[High cohesion, low coupling](../philosophy.md#high-cohesion-low-coupling--at-every-boundary)
for the reasoning, including how it applies to repositories and teams.

## People and AI Agents

Adopt a practice because it helps the people working on the project; that it
also helps AI agents should be a consequence.

- Write documentation for people first, in the project's docs. `AGENTS.md`,
  `CLAUDE.md`, skills, plugins, hooks and commands point agents at that
  documentation and fill the gaps only agents have — they are never the only
  copy of a rule.
- Conventions for a layer or area (storage, CLI, event schema, CI) are written
  by the people who own it and kept next to the code they govern. Index them in
  the project's `docs/guidelines.md` next to the paths they govern, which agents
  have in context from the start; a project skill scoped to those paths may
  deliver them as well. Do not load every area's full conventions into every
  session.
- When a rule can be checked by a tool — compiler, type checker, linter, import
  contract, test — enforce it with the tool instead of describing it in prose.
- Keep changes that carry more risk structurally apart from those that carry
  less, so review effort can follow the risk: read models and projections apart
  from commands and event schemas, and destructive operations behind explicit
  opt-in.

See [People and AI agents](../philosophy.md#people-and-ai-agents) for the
reasoning.

## Code comments

A comment explains *why*, never *what*. The code already states what it does,
through the names of its functions, classes, variables and constants and through
its types. A comment covers what the code cannot express.

- Write a comment for the reasoning a reader cannot recover from the code: why a
  non-obvious implementation was chosen over the obvious one, a constraint
  imposed from outside (a tool's bug, a spec, a platform quirk), a trade-off and
  the alternative that was rejected, an invariant the code relies on without
  checking, or the condition that would retire a workaround.
- Usage hints are welcome: how to run, invoke or trigger the code
  (`gh workflow run check-links.yml --ref <branch>` at the top of a workflow, an
  example invocation in a script header). A reader cannot get those from the
  code either.
- Remove a comment that only restates the code beneath it. That includes
  `# increment the counter`, `# extract node declarations` above a regex already
  named for them, a section banner that repeats the names of the functions under
  it, and a docstring that turns the name of the function, class or module (or
  the module's path) into a sentence. Each one is text the reader has to skip,
  and nothing fails when it goes out of date.
- When the code seems to need a "what" comment, it is not saying enough. Improve
  the code instead: rename the variable, extract a named helper, introduce a
  named constant, or tighten a type. Then delete the comment.
- Docstrings follow the same rule. A docstring on an interface is worth keeping
  when it tells a caller something the signature does not, such as units,
  ownership, error conditions or side effects. A docstring that a tool shows to
  users, like CLI help text or generated API docs, is user documentation and
  stays.
- Delete commented-out code. Version control keeps it.
- Keep comments true. A change that alters the reasoning updates or removes the
  comment in the same edit. A comment that is wrong is worse than no comment.

## Charsets

- UTF-8 everywhere.

## Time Management

- UTC for all timestamps
- Do not generate the current timestamps directly inside the core logic: pass
  the timestamps from the higher-level functions, tests, and other entry points.

## Mocks

Mocks and patches are the exception, not the rule. A test that patches a module
attribute is tied to where the code looks a name up rather than to what it does.
It passes against code that no longer calls the patched name, and it breaks when
a refactor changes how the name is looked up but not the behaviour.

- Prefer passing values as explicit parameters (with sensible defaults) over
  reading global/ambient state internally. This makes functions testable without
  mocking. For example, pass `now: datetime` instead of calling `datetime.now()`
  internally, pass `platform: str = sys.platform` instead of reading
  `sys.platform` internally. Tests should pass these values explicitly rather
  than patching modules.
- When a test needs to control something, use the first option that fits:
  1. **A decider.** Put the decision in a pure function over plain values (what
     to report, which exit code, whether a finding is fatal) and test that
     function with plain values. The code around it only gathers the inputs and
     acts on the answer, and a few wiring tests are enough for it.
  2. **An injected dependency.** Take the dependency as a parameter whose
     default is the real implementation, such as a command runner, a clock, the
     environment or a tool locator, and pass a fake in the test. Keep the fakes
     in one shared test module so every test drives the same few. Pass real
     values rather than stand-ins: a real result object, a real model instance,
     a config file written under the test's temporary directory.
  3. **A cheap real resource.** A child process, a temporary file or directory,
     an in-process server.
- Patching is reserved for three cases:
  - **(a) A third-party boundary the project wraps**, where the test is about
    the wrapper and a real instance needs infrastructure the test cannot have.
  - **(b) A fault no real resource can produce** at the point the test needs it.
  - **(c) Process-global state** the test must isolate from the developer's
    machine, such as a home directory or a user-level config file.
- **Each exception is documented** in the project's `docs/guidelines.md`, in a
  table that gives the file, what it replaces, its category, why it is needed,
  and what would retire it. The same list is enforced by a tool, so a new patch
  fails the build until it is either removed or added to the table. A project
  that adopts this rule with patches already in place lists them in the same
  table under a **pending** category, so the guard stops new ones on day one and
  the table becomes the list of work left to do.
- **Tests never touch the developer's real environment.** Without a test double,
  a test that reaches a user-level secret store, config file or SSH
  configuration reads, or prompts for, whatever is on the developer's machine.
  Choose a test backend once for the whole suite, or pass the path in.

## Presentation at the Edges

Core logic returns data; the edge of the program decides how that data looks.

- Results and errors leave the core as values — records, paths, counts, error
  kinds with their fields — never as pre-rendered prose. Wording, colors,
  relative paths, indentation and escaping are chosen where the data is
  presented, so the same value can be printed to a terminal, written to CSV, or
  asserted on in a test.
- Do not hardcode indents in strings. Formatting helpers return unindented lines
  and the call site applies the indent, so the same helper renders correctly at
  any nesting depth.
- Treat interpolated text as data, not markup. Text that comes from users or the
  filesystem — names, paths, file contents, error messages — must be escaped for
  the language it is embedded in (terminal markup, HTML, Markdown, shell, CSV,
  SQL), or passed through an API that keeps data and markup apart (argument
  lists, parameterized queries, a plain-text print). Unescaped text does not
  fail loudly: it silently loses characters or changes meaning, typically only
  for the inputs nobody tested with.

See [Presentation at the edges](../philosophy.md#presentation-at-the-edges)
for the reasoning.

## Version Management

- Pin specific versions of all dependencies or use a lock file (e.g. `uv.lock`,
  `mise.lock`) to ensure reproducible builds and avoid issues with breaking
  changes in dependencies.

  ```bash
  # examples
  mise use --pin uv@0.12.3
  ```

- A lock file only helps if something asserts that the environment matches it.
  Provide both assertions, because they catch different failures:
  `uv lock --check` asks whether the lock is consistent with the manifest, while
  `UV_LOCKED=1` in CI asks whether installing would *change* the lock. Prefer
  the environment variable over a `--locked` flag on the command, so the install
  command stays identical locally and in CI and only the strictness differs.
- Watch for pins that no updater reads.
  `[tool.uv] build-constraint-dependencies` is the clearest example: `uv.lock`
  does not cover PEP 517 build dependencies, and no built-in Renovate or
  Dependabot manager parses that field, so those pins rot silently unless a
  custom manager is added for them. A pin nothing updates is a pin nothing tells
  you about.

## Naming

Names follow what the reader already knows: the domain's vocabulary, then the
conventions of the surface the name appears on. The Python layer is in
[python.md](python.md#naming).

- **kebab-case on every surface a user types**: CLI commands, sub-commands and
  long options, configuration keys, user-defined slugs, mise tasks, and file
  names under `docs/`.
- **A duration uses the language's duration type.** Where there is none, the
  name ends with its unit (seconds, milliseconds), so a bare timeout does not
  leave the reader to guess.
- **Abbreviate only what the domain abbreviates**, and list those abbreviations
  in the project's `docs/domain.md` glossary (`ms` for media source,
  `src`/`dst`). An abbreviation nobody defined is a word the next reader has to
  reverse-engineer.

## Command Line

- When calling external commands, build the command lines as lists of arguments
  instead of strings to avoid issues with quoting and escaping — the
  command-line case of treating interpolated text as data (see
  [Presentation at the Edges](#presentation-at-the-edges)).
- Make CLIs discoverable: commands should reference each other (e.g. a `check`
  command suggests `troubleshoot`, which suggests `rebuild`). The user should be
  able to navigate the tool by following its output.
- Display paths relative to the base directory for readability. When suggesting
  sample commands, use paths relative to the current working directory so they
  can be copy-pasted and run as-is.

## Testability

- Expose exceptions/errors as structured data — an error kind plus the fields
  that describe it (paths, identifiers, values) — and render the human message
  in the presentation layer. Tests then assert on the kind and fields instead of
  matching raw message strings, so they are not brittle to changes in wording.

## No Silent Failures

- Avoid silent failures and ensure that all errors are surfaced with clear
  messages. This includes validating inputs and configurations early, and
  providing informative error messages when something goes wrong.

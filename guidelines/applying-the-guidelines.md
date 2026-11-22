# Applying the Guidelines

How the shared guidelines apply to an iglootools project, which rule wins when a
project has its own, and how a project departs from one. It covers every
guideline and [philosophy.md](philosophy.md), not only the coding rules; the
plugin puts it in every session.

<!-- toc -->
**On this page**

- [Precedence](#precedence)
  - [The most specific documented rule wins](#the-most-specific-documented-rule-wins)
- [Documented Exceptions](#documented-exceptions)
  - [Write each departure, and its reason, where a reader will hit it](#write-each-departure-and-its-reason-where-a-reader-will-hit-it)
  - [Name the condition that retires it](#name-the-condition-that-retires-it)
<!-- tocstop -->

## Precedence

### The most specific documented rule wins

A subsystem's guidelines (`<dir>/guidelines.md`, `<dir>/guidelines/`) override
the project's for every file under `<dir>`; the project's (`docs/guidelines.md`
and what it links) override the shared guidelines; the shared guidelines apply
[philosophy.md](philosophy.md). Where no more specific rule is written down, the
shared one stands. Where the guidelines live and what goes in them is
[layout.md](documentation/layout.md#keep-the-projects-guidelines-at-conventional-paths-and-the-entry-file-lean)'s.

**Why:** the people who own an area know its constraints, so their written rule
beats a general one; written down, it can be reviewed, where a divergence only
in the code cannot be told from a mistake.

- **Check before departing:** the project's guidelines entry file, already in
  context; any guidelines file that governs what you are editing; and any
  comment at the point of departure in the file itself.
- **Undocumented divergence is drift, not an override:** do not carry it into
  the change. Follow the shared rule, and say what you found.

## Documented Exceptions

### Write each departure, and its reason, where a reader will hit it

A project or module may depart from any shared guideline or
[philosophy.md](philosophy.md) principle, or add rules of its own, when it
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
[When a dependency lags](project-setup/python-tooling.md#when-a-dependency-lags):
next to the setting it overrides, naming the dependency that forces it and the
event that retires it.

**Why:** without one it becomes permanent once nobody remembers why.

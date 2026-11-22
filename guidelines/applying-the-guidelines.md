# Applying the Guidelines

How the shared guidelines apply to an iglootools project, and how a project
departs from one. It covers every guideline and
[philosophy.md](philosophy.md), not only the coding rules; the plugin puts it in
every session.

<!-- toc -->
**On this page**

- [Documented Exceptions](#documented-exceptions)
  - [Write each departure, and its reason, where a reader will hit it](#write-each-departure-and-its-reason-where-a-reader-will-hit-it)
  - [Name the condition that retires it](#name-the-condition-that-retires-it)
<!-- tocstop -->

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
[When a dependency lags](coding/python.md#when-a-dependency-lags): next to the
setting it overrides, naming the dependency that forces it and the event that
retires it.

**Why:** without one it becomes permanent once nobody remembers why.

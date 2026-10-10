# Coding Guidelines

**These are defaults, not dogma.** A project is free to deviate from any rule here, or add its own,
as long as the deviation and its rationale are documented — project-wide ones in the project's
`docs/guidelines.md`, local ones in a comment at the point of deviation. A justified exception is fine;
silent drift is not. Where the exception depends on a condition that may change, name the condition that
would retire it — a written rationale is what lets the exception be re-evaluated later instead of becoming
permanent by default. See [Applying these guidelines](../../README.md#applying-these-guidelines) for the bar
a rationale has to meet.

**Functional Style**:
- Prefer functional programming style over procedural style. Use pure functions and avoid mutability when possible.

**Function size**: Keep functions short and focused. When a function grows beyond ~30 lines or handles multiple concerns (e.g. scanning, processing, and persisting), extract named helpers. Each function should do one thing at one level of abstraction. Prefer reading like a high-level outline that delegates to well-named helpers over a single long procedure.

**High Cohesion, Low Coupling**: Apply the same rule at every level of design: functions, classes, abstractions, modules, packages.
- Group by what changes together. A module or package should own one coherent slice of the domain, so a typical change lands in one place instead of fanning out across several.
- Communicate across boundaries through narrow, explicit interfaces. Expose the operations callers need, keep the rest private, and do not reach into another module's internals.
- Keep dependencies one-directional and acyclic. Two modules that import each other are one module split in the wrong place: merge them, or extract what they share into a third.
- Introduce an abstraction for a concept that exists in the domain, not to shuffle code around. An abstraction whose callers all need to know what is behind it adds coupling instead of removing it.
- Treat a change that routinely touches many modules as a signal that the boundaries are in the wrong place, and move them rather than adding another cross-cutting edit.

See [High cohesion, low coupling](../../philosophy.md#high-cohesion-low-coupling--at-every-boundary) for the reasoning, including how it applies to repositories and teams.

**Code comments**: When making changes to the codebase, explain the reasoning when the implementation is non-obvious, and document any non-trivial design decisions or trade-offs that were made.

**Charsets**:
- UTF-8 everywhere.

**Time Management**
- UTC for all timestamps
- Do not generate the current timestamps directly inside the core logic: pass the timestamps from the higher-level functions, tests, and other entry points.

**Mocks**
- Prefer passing values as explicit parameters (with sensible defaults) over reading global/ambient state internally. This makes functions testable without mocking. For example, pass `now: datetime` instead of calling `datetime.now()` internally, pass `platform: str = sys.platform` instead of reading `sys.platform` internally. Tests should pass these values explicitly rather than patching modules.

**Presentation at the Edges**: Core logic returns data; the edge of the program decides how that data looks.
- Results and errors leave the core as values — records, paths, counts, error kinds with their fields — never as pre-rendered prose. Wording, colors, relative paths, indentation and escaping are chosen where the data is presented, so the same value can be printed to a terminal, written to CSV, or asserted on in a test.
- Do not hardcode indents in strings. Formatting helpers return unindented lines and the call site applies the indent, so the same helper renders correctly at any nesting depth.
- Treat interpolated text as data, not markup. Text that comes from users or the filesystem — names, paths, file contents, error messages — must be escaped for the language it is embedded in (terminal markup, HTML, Markdown, shell, CSV, SQL), or passed through an API that keeps data and markup apart (argument lists, parameterized queries, a plain-text print). Unescaped text does not fail loudly: it silently loses characters or changes meaning, typically only for the inputs nobody tested with.

See [Presentation at the edges](../../philosophy.md#presentation-at-the-edges) for the reasoning.

**Version Management**
- Pin specific versions of all dependencies or use a lock file (e.g. `uv.lock`, `mise.lock`) to ensure reproducible builds and avoid issues with breaking changes in dependencies.

  ```bash
  # examples
  mise use --pin uv@0.12.3
  ```
- A lock file only helps if something asserts that the environment matches it. Provide both
  assertions, because they catch different failures: `uv lock --check` asks whether the lock is
  consistent with the manifest, while `UV_LOCKED=1` in CI asks whether installing would *change*
  the lock. Prefer the environment variable over a `--locked` flag on the command, so the install
  command stays identical locally and in CI and only the strictness differs.
- Watch for pins that no updater reads. `[tool.uv] build-constraint-dependencies` is the clearest
  example: `uv.lock` does not cover PEP 517 build dependencies, and no built-in Renovate or
  Dependabot manager parses that field, so those pins rot silently unless a custom manager is
  added for them. A pin nothing updates is a pin nothing tells you about.

**Command Line**
- When calling external commands, build the command lines as lists of arguments instead of strings to avoid issues with quoting and escaping — the command-line case of treating interpolated text as data (see Presentation at the Edges).
- Make CLIs discoverable: commands should reference each other (e.g. a `check` command suggests `troubleshoot`, which suggests `rebuild`). 
  The user should be able to navigate the tool by following its output.
- Display paths relative to the base directory for readability. 
  When suggesting sample commands, use paths relative to the current working directory so they can be copy-pasted and run as-is.

**Testability**
- Expose exceptions/errors as structured data — an error kind plus the fields that describe it (paths, identifiers, values) — and render the human message in the presentation layer. Tests then assert on the kind and fields instead of matching raw message strings, so they are not brittle to changes in wording.

**No Silent Failures**
- Avoid silent failures and ensure that all errors are surfaced with clear messages. This includes validating inputs and configurations early, and providing informative error messages when something goes wrong.

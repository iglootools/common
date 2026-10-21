# Python Guidelines

- **Functional Style**:
  - Avoid mutable accumulator lists (`errors = []; errors.append(...)`). Instead, build lists as single expressions using `[*(...), *(...)]` unpacking, conditional `[item] if cond else []` fragments, and helper functions that return lists.
  - Prefer dict/list comprehensions over imperative loops for building collections.
  - When a function computes a list from multiple independent branches, compose the result by unpacking sub-expressions rather than mutating a shared list across branches.
- **String Literals**:
  - Prefer `dedent("""\...""")` multiline strings over concatenated single-line strings with `\n` escapes when the content has meaningful structure (e.g. YAML, config snippets, multi-line templates). Short single-line strings (e.g. `"key: value\n"`) are fine as-is.
- **Typing**: Use type annotations for all functions and methods, including return types. Use `pyright` for static type checking.
- **Data Classes**:
  - All serialized model objects are frozen pydantic dataclasses, immutable once created.
  - Other data classes should also be frozen.
  - Exception classes are the exception: write them as plain classes that set their attributes
    in `__init__`, never as `@dataclass(frozen=True)`. Python assigns `__traceback__` (and
    `add_note` writes `__notes__`) while an exception propagates — for instance when it passes
    through a `@contextmanager` — and a frozen dataclass turns that into `FrozenInstanceError`,
    replacing the real error with a confusing one.
- **Errors**: the Python form of structured errors (see `Testability` in [general.md](general.md)).
  - An error value is a frozen dataclass with a `kind: StrEnum` and the fields that describe it.
  - An exception carries the same as attributes, and subclasses the built-in its callers already
    handle (`OSError` for a failed external tool, `ValueError` for malformed input) so existing
    `except` clauses keep catching it.
  - `__str__` stays a plain fallback; the message users see is rendered by the output layer.
- **Imports**: import at module level. Where an import has to be deferred — an expensive
  module the CLI does not need to start, or a cycle between modules — use a module-level
  `lazy import` / `lazy from ... import` (PEP 810) rather than an import inside a function,
  a `TYPE_CHECKING` block, or a module `__getattr__`.
  - A lazy import is still a dependency edge: import-linter and pydeps both see it, so
    the module-boundary contracts keep applying.
  - Enable ruff's `TID255` (lazy-import-immediately-resolved), which flags a lazy import
    that module-level code resolves straight away, so the deferral is lost.
  - When the deferral is the point, such as keeping CLI startup fast, back it with a test
    that imports the entry point in a fresh interpreter and asserts the heavy modules are
    absent from `sys.modules`. Nothing else notices when an eager import creeps back.
  - An optional extra stays an in-function `try: import ... except ImportError`. PEP 810
    forbids `lazy` inside `try`, and a lazy import would move the `ImportError` to the
    first use, where the except clause no longer surrounds it.
- **Formatting**:
  - 88 characters (ruff default).
- **Python Version**: the latest stable release (3.15), one version for development, CI
  and users alike. See [Python Version Policy](#python-version-policy) below.
- **Control Flow**
  - Prefer match-case over if-elif-else chains
  - Prefer comprehensions and built-ins (map, filter) over manual loops when appropriate.
  - Avoid `continue` in loops, and prefer filtering with comprehensions or built-ins instead.
  - Prefer single-expression returns over early returns when the logic can be expressed concisely
    (e.g. `return bool(x) and all(...)` over guard clauses with `return False`).
  - Prefer explicit if/else syntax over implicit else
  - Prefer dict unpacking with a filtered comprehension over if-chains when conditionally
    including keys (e.g. `**{k: v for k, v in {...}.items() if v is not None}`).
- **Console Output**: print through [Rich](https://github.com/textualize/rich), which
  [Typer](https://typer.tiangolo.com/) already bundles. The Python form of
  `Presentation at the Edges` in [general.md](general.md):
  - Apply indentation at the call site with `textwrap.indent` (or a small project helper built
    on it); formatting helpers return unindented lines.
  - Rich parses square brackets as markup and silently drops tags it does not recognize, so a
    name such as `Hiking [private]` prints as `Hiking `. Escape interpolated user text with
    `rich.markup.escape` where it meets intentional markup, or print with `markup=False` when
    the line has none. Escape exactly once: a formatter that escapes what it embeds must be
    printed with markup on, not escaped again.
- **Module Boundaries**: the Python form of `High Cohesion, Low Coupling` in
  [general.md](general.md). Which package may import which is declared as
  [import-linter](https://import-linter.readthedocs.io/) contracts in `pyproject.toml`
  (`[tool.importlinter]`), and a check task enforces them. The setup is in
  [python-tooling.md](../project-setup/python-tooling.md#module-boundaries-import-linter).
  - The contracts are the source of truth for the layering. A generated dependency graph only
    *shows* the edges; the project's architecture doc explains why each rule exists.
  - When a change needs an edge a contract forbids, first decide whether the edge belongs: move
    the code to the layer that may own it rather than bending the contract. Never add an
    `ignore_imports` entry just to make a new edge pass.
  - When the architecture itself changes, change the contracts deliberately, in the same commit
    as the restructuring, together with the architecture doc that explains them.
  - Core modules do not import `rich` or `typer`. A contract names them, which is how
    `Presentation at the Edges` is enforced rather than only stated.

## Python Version Policy

Projects target **one** Python version: the **latest stable CPython release** — 3.15 at
the time of writing. The minimum supported version, the version developed on and the
version CI tests are the same, so there is no compatibility floor to guard and no
second interpreter to keep working.

### Why the latest, and only the latest

Supporting an older Python costs more than it buys for these projects. Every feature
newer than the floor is off-limits, a separate check (`vermin`) is needed to enforce
that because ruff's and pyright's targets miss cases, and CI has to test a version
nobody develops on. Meanwhile the tools are installed by people who can get a current
interpreter in one step:

- `uv tool install <tool>` downloads a managed Python when the system has no matching
  one, so the distro's `python3` does not matter.
- `pipx install --python <path-to-python3.15> <tool>` works the same way with an
  interpreter installed by any other means (mise, pyenv, a PPA, Homebrew).

The system `python3` of an LTS distribution is therefore not a constraint, and the
projects do not track it.

### The knobs

Four settings name the version. All of them move together, in one change:

| Knob | Where | Value |
|---|---|---|
| `[tools] python` | `mise.toml` | `3.15.x` — the exact patch release; CI installs it from here |
| `requires-python` | `pyproject.toml` | `>=3.15,<3.16` |
| ruff `target-version` | `pyproject.toml` | `py315` |
| pyright `pythonVersion` | `pyproject.toml` | `3.15` |

The `<3.16` upper bound keeps the package from installing on a Python nobody has
tested; it is raised deliberately, together with the other knobs, not automatically.

CI takes its interpreter from `mise.toml` like a developer machine does, with no
version matrix: there is only one version to test.

### Moving to a new release

Move once every dependency publishes wheels for the new version. `uv lock` is not the
check: it resolves happily to a release that has only an sdist, and a developer machine
with a compiler then builds it without a word, so the gap shows up later as a failed
install on a user's machine. After raising `requires-python`, relock with
`uv lock --upgrade` (an older locked release often predates the new wheels) and ask
for wheels explicitly:

```bash
uv sync --no-build --dry-run
```

It names every package that would have to be built from source. A pure-Python package
whose sdist builds without a compiler — PyYAML falling back from its C extension — is
acceptable; anything that needs a C, C++ or Rust toolchain is not. Then:

1. Move all four knobs, relock (`uv lock`, `mise lock`), and run the full check and test
   suite.
2. Run `ruff check --fix`; with the new `target-version` its `UP` rules rewrite the
   idioms the new version makes redundant.
3. Adopt the release's new features where they remove a workaround or make the code
   simpler — not everywhere they could apply.

### When a dependency lags

A dependency that publishes no wheels for the latest release holds the project back. Stay
on the newest version that dependency supports, and record it as an exception the way
[general.md](general.md) asks: a comment next to `requires-python` naming the
dependency, and the condition that retires the exception — usually "move when it
publishes wheels for 3.x". Do not build the dependency from source to get ahead of it:
that trades a version number for a toolchain every user then needs.

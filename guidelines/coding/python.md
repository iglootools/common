# Python Guidelines

The Python form of [general.md](general.md)'s rules, and the rules only Python
has. Read it before changing Python code. Building, packaging and checking a
Python project is [python-tooling.md](../project-setup/python-tooling.md)'s.

<!-- toc -->
**On this page**

- [Functional Style](#functional-style)
  - [Build a collection in one expression, not by appending](#build-a-collection-in-one-expression-not-by-appending)
  - [Prefer `match` and explicit branches over chains and early returns](#prefer-match-and-explicit-branches-over-chains-and-early-returns)
  - [Freeze every data class, but write exceptions as plain classes](#freeze-every-data-class-but-write-exceptions-as-plain-classes)
- [Style](#style)
  - [Write structured multi-line strings with `dedent`](#write-structured-multi-line-strings-with-dedent)
  - [Annotate every function, including its return type](#annotate-every-function-including-its-return-type)
- [Naming](#naming)
  - [Follow PEP 8 casing](#follow-pep-8-casing)
  - [Name a package after its domain slice, and its layers by fixed names](#name-a-package-after-its-domain-slice-and-its-layers-by-fixed-names)
  - [Name a class by its role](#name-a-class-by-its-role)
  - [Start a function's name with the verb that says what the caller gets](#start-a-functions-name-with-the-verb-that-says-what-the-caller-gets)
  - [Name a parameter by the word its CLI option or role uses](#name-a-parameter-by-the-word-its-cli-option-or-role-uses)
  - [Name a test after the behaviour it checks](#name-a-test-after-the-behaviour-it-checks)
- [Errors](#errors)
  - [Give an error a kind and its fields, and subclass what callers catch](#give-an-error-a-kind-and-its-fields-and-subclass-what-callers-catch)
- [Imports](#imports)
  - [Import at module level, and defer with `lazy import`](#import-at-module-level-and-defer-with-lazy-import)
- [Console Output](#console-output)
  - [Print through Rich, escaping interpolated text exactly once](#print-through-rich-escaping-interpolated-text-exactly-once)
- [Module Boundaries](#module-boundaries)
  - [Change the import-linter contracts deliberately, never to let an edge through](#change-the-import-linter-contracts-deliberately-never-to-let-an-edge-through)
- [Tests](#tests)
  - [Build serialized test data from the models](#build-serialized-test-data-from-the-models)
  - [Make a seam a keyword parameter whose default is the real function](#make-a-seam-a-keyword-parameter-whose-default-is-the-real-function)
<!-- tocstop -->

## Functional Style

The Python form of
[general.md › Prefer pure functions and immutable data](general.md#prefer-pure-functions-and-immutable-data):
values built in one expression, every branch visible, data that never
changes.

### Build a collection in one expression, not by appending

Build lists from `[*(...), *(...)]` unpacking, conditional
`[item] if cond else []` fragments, comprehensions and helpers that return
lists, never an accumulator (`errors = []; errors.append(...)`).

**Why:** the result's shape is visible where it is defined.

- A result computed from independent branches unpacks each branch's
  sub-expression.
- Include keys conditionally with a filtered comprehension:
  `**{k: v for k, v in {...}.items() if v is not None}`.
- Filter with a comprehension or a built-in (`map`, `filter`) instead of a loop
  with `continue`.

### Prefer `match` and explicit branches over chains and early returns

Use `match`-`case` over `if`-`elif`-`else` chains, write the `else` explicitly,
and return a single expression where the logic allows
(`return bool(x) and all(...)` over guard clauses returning `False`).

**Why:** every case is visible at one level, with no implicit path.

### Freeze every data class, but write exceptions as plain classes

Serialized models are frozen pydantic dataclasses, and other data classes are
frozen too. An exception is a plain class that sets its attributes in
`__init__`, never a `@dataclass(frozen=True)`.

**Why:** a frozen value is safe to share. But Python assigns `__traceback__`
(and `add_note` writes `__notes__`) as an exception propagates, for instance
through a `@contextmanager`, and a frozen dataclass replaces the real error with
a `FrozenInstanceError`.

## Style

### Write structured multi-line strings with `dedent`

Use `dedent("""\...""")` for content with structure (YAML, config snippets,
templates), not concatenated lines with `\n` escapes. A short single-line string
such as `"key: value\n"` stays as it is.

**Why:** the string reads as the text it produces.

### Annotate every function, including its return type

**Why:** pyright
([setup](../project-setup/python-tooling.md#type-check-with-pyright-in-strict-mode-tests-included))
checks only what is annotated.

## Naming

The Python form of [general.md › Naming](general.md#naming).

### Follow PEP 8 casing

`snake_case` functions, modules and variables, `CamelCase` classes,
`UPPER_SNAKE` constants and enum members, and a leading `_` for anything private
to its module.

**Why:** the code reads like any Python.

- A model read from or written to a file a user edits keeps snake_case fields
  and maps them to kebab keys through Pydantic's `alias_generator`, not an
  alias per field, so the user still types kebab-case.
- Machine-readable output (JSON keys, CSV headers) uses the fields' snake_case
  names, so a consumer writes `.failure_reason` in `jq` without quoting. A
  command that echoes configuration back (`config show`) keeps its kebab keys.

### Name a package after its domain slice, and its layers by fixed names

A package takes the domain's own noun (`disks/`, `album/`). Layers inside it:

| Name | Holds |
|---|---|
| `cli/` | the Typer commands, one per `<command>_cmd.py` |
| `output.py` / `output/` | presentation: turning results into text, tables or JSON |
| `protocol.py` / `protocol/` | an on-disk or wire format (not `typing.Protocol`) |
| `models.py` | the domain's data types, when they outgrow the module that uses them |
| `testkit.py` / `testkit/` | factories and sample values the tests share |

**Why:** every package reads the same way.

### Name a class by its role

- A result is `<Subject>Result`, a plan a decider returns `<Subject>Plan`,
  configuration a user writes `<Subject>Config`.
- Only an exception is `<Subject>Error`. An enum of problem kinds is
  `<Subject>ErrorKind` for a problem found before an operation runs (a missing
  volume, an invalid config), `<Subject>FailureKind` for how an operation that
  ran went wrong (`MountFailureKind`), and `<Subject>WarningKind` for one that
  does not stop it. The exception carries that kind ([Errors](#errors)).
- Enums subclass `StrEnum`, not `(str, Enum)`. Their values are stable tokens,
  kebab-case or one lowercase word (`"no-metadata"`, `"mounted"`), never prose:
  scripts match on the value, and the sentence a user reads is rendered at the
  [edge](general.md#the-core-and-its-edges).
- A `typing.Protocol` is named by its role (`VolumeCommandRunner`,
  `ConvertFile`); a callable type alias ends in `Fn` (`PromptFn`, `WhichFn`).
  Write aliases with `type X = ...`.
- A test double is `Fake<Thing>` as a class, `fake_<thing>()` as a factory.

**Why:** the name tells the reader what kind of thing it is before they open it.

### Start a function's name with the verb that says what the caller gets

| Verb | Means |
|---|---|
| `load_` / `save_` | read or write a persisted file as a model |
| `read_` / `write_` | read or write raw content |
| `parse_` | text to a value, raising on malformed input |
| `resolve_` | derive a value from configuration or the environment |
| `find_` / `scan_` / `discover_` | search the filesystem |
| `build_` | assemble a structure from parts |
| `compute_` | a pure calculation |
| `check_` | run a check and return its result, without raising for a failed check |
| `validate_` | raise when input is invalid |
| `require_` | raise, or exit at the CLI, when a precondition is missing |
| `plan_` / `classify_` | a decider: plain values in, a decision out |
| `format_` | return the text for a value; never prints |
| `print_` | print; only in `cli/` modules |
| `is_` / `has_` | a boolean predicate |

**Why:** the name says whether it raises, prints or touches the disk.

- `_or_exit` marks a CLI helper that exits the process on failure, and only
  those.
- A Typer command function is `<command>_cmd` (`detect_faces_cmd`), so it never
  shadows a builtin or the domain function it calls (`mount`, `run`). A Typer
  sub-app is `app` in its own module, read as `<scope>.app`; it is
  `<scope>_app` only where the module does not already say which app it is.
- An option two commands share is an `Annotated` constant `<NAME>_OPTION` in one
  module.

### Name a parameter by the word its CLI option or role uses

A boolean uses the CLI option's word (`dry_run`, `force`); a negative one starts
with `skip_`. A collection is a plural noun, a mapping `<values>_by_<key>`. A
directory is `<name>_dir`, any other path `<name>_path`. An injected seam is
named for what it does (`run`, `which`, `now`), a callback `on_<event>`, a
function parameter `<role>_fn`.

**Why:** a concept keeps one name from the command line to the core.

### Name a test after the behaviour it checks

`test_<module>.py` files mirror the package, tests group in `Test<Subject>`
classes, and each name is `test_<subject>_<outcome>[_when_<condition>]`
(`test_failed_open_is_not_kept`).

**Why:** a failing test's name says which behaviour broke.

## Errors

### Give an error a kind and its fields, and subclass what callers catch

The Python form of
[general.md › Return data from the core](general.md#return-data-from-the-core-and-render-it-at-the-edge):
an error value is a frozen dataclass with a `kind: StrEnum` and its fields. An
exception carries the same as attributes, and subclasses the built-in its
callers already handle (`OSError` for a failed external tool, `ValueError` for
malformed input). `__str__` stays a plain fallback; the output layer renders the
message users see.

**Why:** existing `except` clauses keep catching it, and tests assert on the
kind and fields, not the wording.

## Imports

### Import at module level, and defer with `lazy import`

Where an import has to be deferred (an expensive module the CLI does not need
to start, or a cycle), use a module-level `lazy import` / `lazy from ... import`
(PEP 810), not an import inside a function, a `TYPE_CHECKING` block or a module
`__getattr__`.

**Why:** every dependency stays visible at the top of the module, and
import-linter and pydeps still see a lazy import as an edge, so the
module-boundary contracts keep applying.

- A lazy import that module-level code resolves straight away loses its
  deferral; ruff's `TID255` flags it.
- An optional extra stays an in-function `try: import ... except ImportError`.
  PEP 810 forbids `lazy` inside `try`, and a lazy import would move the
  `ImportError` to the first use, outside the `except`.
- When the deferral is the point, such as a fast CLI startup, a test imports the
  entry point in a fresh interpreter and asserts the heavy modules are absent
  from `sys.modules`: nothing else notices an eager import creeping back.

## Console Output

### Print through Rich, escaping interpolated text exactly once

Print through [Rich](https://github.com/textualize/rich), which
[Typer](https://typer.tiangolo.com/) bundles. Escape user text with
`rich.markup.escape` where it meets intentional markup, print with
`markup=False` when the line has none, or wrap the text in `rich.text.Text` or
`Text.assemble`, which keeps it apart from markup. A formatter that escapes what
it embeds is printed with markup on, not escaped again.

**Why:** Rich silently drops square-bracket tags it does not recognize, so
`Hiking [private]` prints as `Hiking `; escaping twice prints the backslashes.

- Prefer `Text` when the same value also feeds a non-Rich output, such as JSON:
  the value stays unescaped, and only its styling is Rich's.
- Indent at the call site with `textwrap.indent`, or a small helper built on it
  ([general.md](general.md#return-data-from-the-core-and-render-it-at-the-edge)).

## Module Boundaries

### Change the import-linter contracts deliberately, never to let an edge through

Which package may import which is declared as
[import-linter](https://import-linter.readthedocs.io/) contracts under
`[tool.importlinter]` in `pyproject.toml`, enforced by
`mise run lint-boundaries`
([setup](../project-setup/python-tooling.md#declare-module-boundaries-as-import-linter-contracts)).
They are the Python form of
[general.md › Keep cohesion high](general.md#keep-cohesion-high-and-coupling-low-at-every-level).
When a change needs an edge a contract forbids, move the code to the layer that
may own it. Never add an `ignore_imports` entry just to make a new edge pass.

**Why:** the contracts are the source of truth for the layering; bent once,
they stop saying anything.

- When the architecture itself changes, change the contracts in the same commit
  as the restructuring, with the architecture doc that explains each rule. A
  generated dependency graph only shows the edges.
- Core modules do not import `rich` or `typer`, and a contract names them, so
  presentation at the edges is enforced rather than only stated.

## Tests

The Python form of [general.md › Testability](general.md#testability), enforced
as
[python-tooling.md](../project-setup/python-tooling.md#enforce-the-patching-rule)
sets up.

### Build serialized test data from the models

Write a test's YAML or JSON input by dumping the model (`model_dump`, then the
serializer), not as a hand-written string.

**Why:** a hand-written string keeps passing after the model's fields change,
testing a format the code no longer reads.

### Make a seam a keyword parameter whose default is the real function

Run the whole suite after introducing one, not only the tests you converted.

**Why:** the default is bound when the function is defined, so a test that still
patches the module attribute no longer reaches the code, and keeps passing
without testing anything.

- Patching means `unittest.mock` and pytest's `monkeypatch` fixture. Changing
  directory is not (use `contextlib.chdir`), nor is choosing a backend through a
  library's own API.
- [Real values, not stand-ins](general.md#control-what-a-test-needs-with-a-decider-a-fake-or-a-cheap-real-resource)
  matter more in Python: a `Mock` accepts any attribute access, so a typo or a
  renamed field still passes.

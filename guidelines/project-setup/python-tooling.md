# Python Tooling Guidelines

The toolchain: how a Python project is built, how its environment is created,
and what tasks it exposes. For the language itself — what to write, rather than
what builds it — see [python.md](../coding/python.md). Editor configuration is
in [ide.md](ide.md), and what every repository carries regardless of language is
in [repository.md](repository.md).

<!-- toc -->
**On this page**

- [Build and Packaging](#build-and-packaging)
  - [Build backend](#build-backend)
  - [Pin the build backend explicitly](#pin-the-build-backend-explicitly)
  - [Guard against a `0.0.0` release](#guard-against-a-000-release)
  - [Know what hatchling packages by default](#know-what-hatchling-packages-by-default)
  - [Keep the version honest in editable installs](#keep-the-version-honest-in-editable-installs)
- [Mise and uv](#mise-and-uv)
  - [Configuration](#configuration)
  - [Invoke tools through `uv run --no-sync <tool>` in mise tasks, not bare](#invoke-tools-through-uv-run---no-sync-tool-in-mise-tasks-not-bare)
  - [Adding and removing dependencies](#adding-and-removing-dependencies)
- [Code Quality Tools](#code-quality-tools)
  - [Module boundaries (import-linter)](#module-boundaries-import-linter)
  - [Dead code (deadcode)](#dead-code-deadcode)
- [Tests](#tests)
  - [Run test suites in parallel with pytest-xdist](#run-test-suites-in-parallel-with-pytest-xdist)
  - [Enforce the patching rule](#enforce-the-patching-rule)
- [Mise Tasks](#mise-tasks)
  - [Lock checks](#lock-checks)
  - [Reinstalling the environment](#reinstalling-the-environment)
<!-- tocstop -->

## Build and Packaging

### Build backend

Build tool: `uv`, with `hatchling` as the build backend and
[`uv-dynamic-versioning`](https://github.com/ninoseki/uv-dynamic-versioning) for
git-tag-derived versions. Commit `uv.lock`.

```toml
[build-system]
requires = ["hatchling", "uv-dynamic-versioning"]
build-backend = "hatchling.build"

[tool.hatch.version]
source = "uv-dynamic-versioning"
```

`uv-dynamic-versioning` is powered by the same `dunamai` library as the
`poetry-dynamic-versioning` plugin used before, so version strings are identical
across the switch — `0.6.1` on a tagged commit, `0.6.1.post6.dev0+2a99beb` off
one. It is a third-party plugin; `uv`'s own `uv_build` backend cannot derive
versions from a VCS at all
([astral-sh/uv#14561](https://github.com/astral-sh/uv/issues/14561)), and
`hatch-vcs` would change the dev-version format.

### Pin the build backend explicitly

`uv.lock` does **not** resolve PEP 517 build dependencies: `uv build` resolves
them fresh from PyPI on a cold cache. `[tool.uv] build-constraint-dependencies`
is the only pin, and it must cover the whole closure — most importantly
`dunamai`, which is what computes the version. Regenerate with:

```bash
printf '%s\n' hatchling uv-dynamic-versioning \
  | uv pip compile - --no-annotate --no-header --quiet
```

Leave `[build-system].requires` unpinned so the two can never contradict each
other. No built-in Renovate manager reads `build-constraint-dependencies`, so
these pins rot silently unless a `customManagers` regex entry is added for them.
It takes two patterns:

```json
{
  "customType": "regex",
  "managerFilePatterns": ["/pyproject.toml/"],
  "matchStrings": [
    "build-constraint-dependencies = \\[[^\\]]*\\]",
    "\"(?<depName>[a-zA-Z0-9._-]+)==(?<currentValue>[^\"]+)\""
  ],
  "matchStringsStrategy": "recursive",
  "datasourceTemplate": "pypi"
}
```

The first isolates the array, and the second, applied within it, captures every
pin. The obvious single pattern, anchored on the field name and capturing a pin,
extracts only the first pin: its anchor is consumed by the first match, so the
rest of the array is never matched. That fails quietly, since Renovate keeps
updating one dependency and the build closure looks maintained. In photree it
extracted one of ten pins, and it went unnoticed in two iglootools projects
until an audit.

The shared `python` Renovate preset carries this entry, so extend it rather than
copying the entry
([dependency-automation.md](dependency-automation.md#extend-the-shared-renovate-presets)).

That entry only gets the bump halfway. `uv.lock` does not resolve the build
closure, but it does record the constraints themselves, in its `[manifest]`, and
Renovate regenerates the lock only for dependencies its built-in managers
extracted. A regex-manager bump therefore arrives with `pyproject.toml` changed
and `uv.lock` stale, and a CI job running with `UV_LOCKED=1` fails on it before
any test. The
[shared lock regenerator](shared-workflows.md#call-the-shared-lock-regenerator-too)
runs `uv lock` on Renovate branches to close that gap, so a project with these
pins needs to call it.

### Guard against a `0.0.0` release

With a VCS-derived version, `[tool.uv-dynamic-versioning] fallback-version` is
required — Renovate runs `uv lock --upgrade-package`, which builds with no git
context, and without a fallback every such PR fails. The cost is that "no git
history" becomes a *successful* build producing `0.0.0`: verified by building
from a source tree with `.git` removed, which yields
`<pkg>-0.0.0-py3-none-any.whl` and exits 0. Nothing else in the publish path
catches this, and PyPI never allows a version to be re-uploaded. So provide a
`build-verify` task and wire it into the CI build:

```toml
[tasks.build-verify]
description = "Fail if the built wheel carries the 0.0.0 fallback version"
run = "uv run --no-sync iglootools python verify-version"
```

[`iglootools python verify-version`](iglootools-cli.md) reads the fallback
version from `pyproject.toml` rather than keeping its own copy, which would let
fallback builds through as soon as the two differed. It reads each wheel's
`METADATA` rather than pattern-matching filenames, since a legitimate
`1.0.0.dev0` contains `0.0.0` as a substring, and it fails when `dist/` holds no
wheel at all, or the guard would be defeated by the very situation it exists to
catch.

Building the wheel *from an sdist* is safe, contrary to expectation: hatchling
writes the resolved version into the sdist's `PKG-INFO` and reads it back,
verified by building from an extracted sdist with no `.git`.
`uv build --sdist --wheel` (both from source) is still mildly preferable at no
cost, but it is not a workaround for a broken path.

### Know what hatchling packages by default

Which is more than poetry did:

| Default | Consequence |
|---|---|
| sdist includes every file not ignored by the VCS | ships `tests/`, `docs/`, `.github/` and the lockfiles unless constrained with `[tool.hatch.build.targets.sdist] only-include` |
| wheel contents inferred from a `<NAME>/__init__.py` heuristic | when the heuristic misses, the result is a silently *empty* wheel rather than an error — so set `[tool.hatch.build.targets.wheel] packages` explicitly |
| `.gitignore` is the only ignore file read — not `.git/info/exclude`, not `core.excludesfile` | a file ignored only locally is published. See the `.gitignore` rule under [All Projects](repository.md) |

Prove parity rather than assuming it when migrating a build backend: diff the
wheel payload and sdist file lists against the previous toolchain's at the same
tag, and install the wheel and exercise anything read through
`importlib.resources` or `Path(__file__).parent`, which a file-list diff does
not cover.

### Keep the version honest in editable installs

Code that reads its own version through `importlib.metadata` gets whatever was
frozen into `.dist-info` at install time, so a VCS-derived version goes stale on
the next commit. Fix it with:

```toml
[tool.uv]
cache-keys = [{ file = "pyproject.toml" }, { git = { commit = true, tags = true } }]
```

This *replaces* the default `[{ file = "pyproject.toml" }]` rather than
extending it, hence the explicit file entry. Note the interaction with
`[deps.uv]`: a plain commit changes neither `uv.lock` nor `pyproject.toml`, so
no automatic sync fires and the staleness persists until something forces one.
An uncommitted tree also still reports the last commit's version — `dunamai`'s
default format carries no dirty marker.

## Mise and uv

### Configuration

For uv projects mise documents `python.uv_venv_auto` in `[settings]`, *not*
`_.python.venv` in `[env]` — the latter is for projects that do not use uv, and
the two are separate code paths, so this is a replacement rather than an
addition. Pair it with `[deps.uv]` so mise's dependency engine owns
installation:

```toml
[tools]
python = "3.15.0"
uv = "0.12.3"

[env]
UV_PYTHON = { value = "{{ tools.python.path }}", tools = true }
UV_PYTHON_DOWNLOADS = "never"
UV_PYTHON_PREFERENCE = "only-system"

[settings]
lockfile = true
experimental = true            # required by `mise deps`
python.uv_venv_auto = "source"     # creation is [deps.uv]'s job, not mise's

[deps.uv]
auto = true
run = "uv sync"                # add --all-extras if the project has extras
```

| Setting | Why | Consequence if missing |
|---|---|---|
| `UV_PYTHON` as an **absolute path** | mise's docs are explicit that a bare version number "does not guarantee that uv uses the specific interpreter managed by mise" | uv may silently build the venv on a system or self-managed Python of the same version; a raised `[tools] python` pin also stops recreating `.venv`, since the old interpreter still satisfies `requires-python` |
| `experimental = true` in the committed `mise.toml` | `mise deps` is experimental, and relying on each developer exporting `MISE_EXPERIMENTAL` makes a fresh clone behave differently from CI | dependencies mysteriously do not install, with no error naming the cause |
| `[deps.uv] auto = true` | runs `uv sync` before any `mise run`, gated on a blake3 hash of `uv.lock` + `pyproject.toml` and on `.venv` existing | every task needs a manual `install` first, or silently runs against a stale environment |
| `[deps.uv] run = "..."` | the built-in command is a bare `uv sync`, which misses `--all-extras` | extras are absent from the dev environment. Note that overriding `run` **keeps** the built-in source hashing and `.venv` tracking — only `install_command()` reads it |
| `python.uv_venv_auto = "source"`, not `"create\|source"` | mise's cookbook is explicit that with `[deps.uv]` enabled, creating the venv is the deps provider's job — keep the setting at `"source"`, enable `[deps.uv]`, and let `mise deps` create it | the two mechanisms collide. Measured on a fresh clone with `"create\|source"`, `mise install` announced `creating venv with uv at: …` and then failed on its own result: `error: Failed to create virtual environment / Caused by: A virtual environment already exists at: .venv`, then `WARN uv venv creation failed`. With `"source"` the same clone installs silently and the first `mise run` lets `[deps.uv]` create and populate `.venv` |
| `UV_LOCKED: 1` in CI job env | asserts a sync will not change `uv.lock` | a stale lockfile is papered over by an implicit re-resolve on the runner. Prefer the environment variable over a `--locked` flag, so the `[deps.uv]` command stays identical locally and in CI and only the strictness differs |

A consequence of leaving creation to `[deps.uv]` is that on a genuinely fresh
clone `.venv` does not exist until the first `mise run` — `mise install` alone
does not create it. That is by design rather than a gap, but it means nothing is
on `PATH` for that first run, which is one of the two reasons for the next rule.

### Invoke tools through `uv run --no-sync <tool>` in mise tasks, not bare

mise activates the project's `.venv`, but it does not remove a *foreign*
`.venv/bin` that is already on `PATH`, so in a shell where another project's
virtualenv is active a bare `ruff` silently runs that project's copy. Measured
in a multi-project checkout: the current project's venv landed at `PATH`
position 16 and the foreign one at position 1. `uv run` resolves the environment
from the project root and ignores `PATH`, so it is immune; `--no-sync` keeps
installation the `[deps.uv]` provider's job alone. It was not measurably slower
than a bare invocation.

State the same rule in the project's own docs. Under `poetry run` the
requirement for an activated environment was implicit in every command; without
a prefix it has to be written down, including `mise exec -- <tool>` as the way
to run something from an unactivated shell.

### Adding and removing dependencies

Add dependencies with `uv add` / `uv remove`, which update `pyproject.toml` and
`uv.lock` together. `mise deps add` does not support uv — its ecosystems are
npm, yarn, pnpm, bun, deno, aube, dart and flutter — so do not go looking for a
mise verb. Both write `pyproject.toml` in uv's style, so run `mise run format`
before committing ([formatting.md](formatting.md)).

## Code Quality Tools

Use `ruff` for linting and formatting the Python (the other files are formatted
as [formatting.md](formatting.md) describes), `pyright` for type-checking,
`import-linter` for module boundaries, and `deadcode` for code nothing uses.
There is no compatibility check (`vermin`): projects support only the version
they are developed on, so nothing can be too new (see the
[Python Version Policy](../coding/python.md#python-version-policy)).

### Module boundaries (import-linter)

What the contracts mean, and when to change them, is in
[python.md › Module Boundaries](../coding/python.md#module-boundaries). This
section covers how they are set up.

Add `import-linter>=2.15,<3.0` to the dev dependency group, and declare the
contracts in `pyproject.toml`:

```toml
# Module boundaries, enforced by `mise run boundaries-check` (part of `check`).
# The rationale for each rule is in docs/architecture.md#layering.
[tool.importlinter]
root_package = "<pkg>"
# Lets a contract name third-party packages, so core code can be kept off rich and typer.
include_external_packages = true
```

Point the comment above `[tool.importlinter]` at the task and at the
architecture section that explains the rules. A comment naming a task that has
since been renamed points the next reader at something that does not exist, and
nothing fails to say so.

Expose it as a `boundaries-check` task, run through `uv run --no-sync` like
every other tool, and add it to `check` so CI runs it through `check-all`:

```toml
[tasks.boundaries-check]
description = "Check module boundaries (import-linter contracts in pyproject.toml)"
run = "uv run --no-sync lint-imports"
```

The name follows the `*-check` convention and says what is asserted. It is
neither `lint-imports`, which names the tool rather than the property, nor
`import-check`, which a CLI that imports anything (photos, files) may already
use for one of its own commands.

**Prefer contracts whose coverage follows the code.** A `forbidden` contract
with an enumerated `source_modules` list covers exactly the modules listed. A
module added later is unchecked, and the run still passes. Choose the contract
type that does not depend on the list being kept up to date:

| Type | Use it for | Coverage of a new module |
|---|---|---|
| `layers` | the top-level ordering of packages, highest first; `\|` separates siblings that must not import each other | automatic: a layer is a whole package |
| `protected` | "only X may import Y", such as only CLI modules importing `typer` | automatic: an allowlist of importers catches any new importer |
| `independence` | sibling sub-apps that must not import each other | only the listed modules |
| `forbidden` | everything else, especially "core never reaches the CLI layer, even indirectly" | only the listed `source_modules`, unless written with wildcards (`<pkg>.*.cli`) |

Where an enumerated list is unavoidable, say so in a comment above it ("a new
subpackage outside `cli/` belongs on this list"). That comment is the only
reminder the next person gets. If a package keeps its `cli/` subpackage beside
its core, a package listed as a `forbidden` source also covers its own `cli/`.
List its non-CLI subpackages instead, and cover the package's `__init__` with a
second contract that sets `as_packages = false`.

**Every `ignore_imports` entry carries a comment** saying why the edge is
acceptable. Leave `unmatched_ignore_imports_alerting` at its default, `error`,
so an entry that no longer matches anything fails the check instead of lingering
as an exemption for code that has moved.

**Know what a contract cannot express.** import-linter reads every import
statement, including those inside functions. A rule such as "the ML stack is
imported lazily, never at startup" is therefore not a contract. Check it with a
test that imports the entry point and inspects `sys.modules`.

`acyclic_siblings` is not a default. Run against nbkp and photree with the root
package as ancestor, it reported cycles between each module's `cli/` subpackage
and the shared CLI wiring below them, which is layering both projects intend. It
suits a project whose packages are split by layer, not one where each package
keeps its own `cli/`.

### Dead code (deadcode)

Ruff and pyright report an unused import or local variable within one file, but
neither notices a function, method or class that nothing in the project calls
any more. [deadcode](https://github.com/albertas/deadcode) does, across the
package and its tests, and also reports commented-out code, which
[general.md](../coding/general.md#code-comments) says to delete. Retire it once
Ruff or ty detects unused definitions across files: that is a check the project
already runs, with one tool fewer to pin.

Add `deadcode>=2.7.0,<3.0` to the dev dependency group (2.6.0 is the first
release that runs on Python 3.15), expose it as a `dead-code-check` task in
`check`, and configure it in `pyproject.toml`:

```toml
[tasks.dead-code-check]
description = "Check for unused code (deadcode, configured in pyproject.toml)"
run = "uv run --no-sync deadcode <pkg> tests"
```

```toml
# Unused code, enforced by `mise run dead-code-check` (part of `check`). Each entry is code
# that runs without being named in the project, so the scan cannot see it used.
[tool.deadcode]
ignore-names-if-decorated-with = [
  "@*.command", "@*.callback",                # Typer registers commands by decorator
  "@pytest.fixture",                          # pytest injects fixtures by parameter name
  "@field_validator", "@model_validator",     # Pydantic calls them while validating
  "@field_serializer", "@model_serializer",
]
ignore-names = [
  "main",                                     # the [project.scripts] entry point
  "model_config",                             # read by Pydantic
  "pytestmark", "pytest_plugins", "pytest_*", # read by pytest
]
```

- **Scan the package and its tests together**, so a test helper or a `testkit`
  module counts as used. Code only the tests use is then not reported; that is
  the price of not flagging every helper the tests share.
- **Exceptions sit on the line they excuse**, with their reason:
  `# noqa: DC04 -- Paramiko calls it on an unknown host key`. The config holds
  only patterns that recur across the code, each with its comment, so a reader
  of the config learns which frameworks call code by name. Ruff reports a `noqa`
  code it does not know as unused (`RUF100`), so declare deadcode's codes to it
  under `[tool.ruff.lint]`: `external = ["DC"]`.
- **What deadcode reports is deleted**, unless it is one of those exceptions. A
  commented-out line that is really prose (`# SSH: StrictHostKeyChecking`) is
  rephrased or marked, not kept as code.
- **Review `deadcode --fix` like any other diff**, and commit it on its own with
  the command in the message
  ([git.md](../coding/git.md#keep-refactoring-apart-from-behaviour-changes)). It
  reports a definition used only by other dead code in the same run, so one pass
  removes a whole cascade, but it can also cut a multi-line function short and
  leave a file that does not parse: run the checks after it, and remove what it
  mangles by hand.

## Tests

### Run test suites in parallel with pytest-xdist

Add `pytest-xdist` to the dev dependency group and pass `-n auto` in every test
task whose tests are isolated — each one working under its own `tmp_path`,
taking its dependencies as fakes, and sharing no module-level state. It spreads
the suite across one worker per CPU, which is what keeps the common case of
[Shorten every feedback loop](../../philosophy.md#shorten-every-feedback-loop)
running in seconds as the suite grows.

```toml
[tasks.test-unit]
description = "Run unit tests"
# -n auto: unit tests are isolated (tmp_path, injected fakes), so they parallelize cleanly.
run = "uv run --no-sync pytest tests/ --ignore=tests/integration_fs/ -n auto -v"
```

- **Put `-n auto` in the task, not in `addopts`.** `addopts` applies to every
  invocation, so running one test by hand, or under `--pdb` or a debugger, would
  also start a worker per CPU — slower to start and, under xdist, without an
  interactive terminal for the debugger.
- **Parallel runs surface hidden coupling.** A test that passes alone and fails
  under `-n auto` depends on state another test leaves behind, or on running in
  a particular order. Fix the isolation rather than dropping `-n auto` for the
  suite.
- **A suite that cannot be parallelized says why, at the task.** Some suites
  share a resource that is expensive to duplicate per worker — a Docker
  environment started once for the session, say. Leave `-n auto` off there, with
  a comment naming the shared resource, so the next person does not "fix" it by
  adding the flag.

### Enforce the patching rule

What counts as patching, and the three exceptions to the rule against it, are in
[general.md › Mocks](../coding/general.md#mocks) and
[python.md › Tests](../coding/python.md#tests). pytest and ruff enforce it
between them, with no custom code:

1. **Replace the `monkeypatch` fixture** in the root `tests/conftest.py` with
   one that fails the test and says why. A fixture defined there overrides
   pytest's for every test below it.

   ```python
   @pytest.fixture
   def monkeypatch() -> NoReturn:
       """Replace pytest's fixture for every test: tests do not patch."""
       pytest.fail(
           "The monkeypatch fixture is disabled: inject a fake through a parameter"
           " instead (docs/guidelines.md, Tests).",
           pytrace=False,
       )
   ```

   Do not reach for `-p no:monkeypatch` in `addopts` instead. pytest loads its
   built-in plugins before it reads `addopts` from `pyproject.toml`, so the flag
   only works on the command line, and a suite configured that way still has the
   fixture.
2. **Ban what is left with ruff.** `TID251` (flake8-tidy-imports banned-api)
   bans `unittest.mock` and `pytest.MonkeyPatch`, the only ways to patch once
   the fixture is gone. Enable `RUF100` as well, which reports a `noqa` that no
   longer suppresses anything:

   ```toml
   [tool.ruff.lint]
   # TID251: tests inject fakes through parameters instead of patching
   # (docs/guidelines.md, Tests). unittest.mock is banned, and so is
   # pytest.MonkeyPatch: tests/conftest.py replaces the monkeypatch fixture with one
   # that fails. Each documented exception carries `# noqa: TID251` on its import, and
   # RUF100 reports a noqa that is no longer needed.
   extend-select = ["RUF100", "TID251"]

   [tool.ruff.lint.flake8-tidy-imports.banned-api]
   "unittest.mock".msg = "Inject a fake through a parameter instead of patching (docs/guidelines.md, Tests)."
   "pytest.MonkeyPatch".msg = "Inject a fake through a parameter instead of patching (docs/guidelines.md, Tests)."
   ```

3. **Mark each exception at its import**, with its category, rather than in
   `per-file-ignores`: ruff does not report a `per-file-ignores` entry that no
   longer matches anything, while `RUF100` does report a stale `noqa`. A file
   that patches in several tests can define its own `monkeypatch` fixture, so
   the tests themselves stay as they are. Define it in the test module, never in
   a `conftest.py`, where it would re-enable patching for the whole directory.

   ```python
   from pytest import MonkeyPatch  # noqa: TID251 -- (c) HOME, read by a library below any seam


   @pytest.fixture
   def monkeypatch() -> Iterator[MonkeyPatch]:
       """Patching is allowed in this file only: see docs/guidelines.md (Tests)."""
       with MonkeyPatch.context() as patch:
           yield patch
   ```

Changing directory goes with the fixture. Give `tests/conftest.py` a `chdir`
fixture over `contextlib.chdir`, undone at the end of the test:

```python
@pytest.fixture
def chdir() -> Iterator[Callable[[Path], None]]:
    """Change the working directory until the end of the test."""
    with contextlib.ExitStack() as stack:
        yield lambda path: stack.enter_context(contextlib.chdir(path))
```

The exceptions table in `docs/guidelines.md` stays the one list of reasons. The
`noqa` comment carries a short form of its row, so a reader can tell which one
it belongs to. A project that adopts the rule with patches already in place
marks each of them **pending** the same way, which is what lets the checks go in
before the tests are converted.

## Mise Tasks

Consider providing:

- `configdocs`/`configdocs-check`, and `depgraph`/`depgraph-check` tasks for
  config and dependency documentation, respectively; `depgraph` runs
  `iglootools docs depgraph`
- `format`, `lint`, `type-check`, `boundaries-check`, `dead-code-check` tasks
  for code quality checks

The rules for tasks in any project — `ci-*` tasks, multi-line bodies as file
tasks under `mise-tasks/`, and checking `mise.lock` — are in [mise.md](mise.md).

### Lock checks

A `lock-check-uv` task runs `uv lock --check`, which asks whether `uv.lock` is
consistent with `pyproject.toml`, while `UV_LOCKED` in CI asks whether a sync
would *change* it. Its `mise.lock` counterpart, `lock-check`, is in
[mise.md](mise.md#check-miselock-in-a-scratch-copy).

### Reinstalling the environment

A `reinstall` task that deletes `.venv` and reinstalls from scratch. Most of
what this used to be for is gone: `uv sync` is exact by default, so it removes
packages present in neither `pyproject.toml` nor `uv.lock`, and the `UV_PYTHON`
pin above is what picks up a raised `[tools] python`. It survives for the one
case `[deps.uv]`'s hashing cannot see — a venv that is *dirty* rather than
*stale*, after someone ran `uv pip install` into it by hand.
[`iglootools python reinstall`](iglootools-cli.md) deletes `.venv` and runs
`mise deps install uv --force`:

```toml
[tasks.reinstall]
description = "Delete .venv and reinstall dependencies from scratch"
run = "uv run --no-sync iglootools python reinstall"
```

`build` and `clean` are commands too, `iglootools python build` and
`iglootools python clean`, so none of the Python tasks needs a file under
`mise-tasks/`.

Keep `install` as a named task delegating to `mise deps install uv`, rather than
calling `uv sync` directly. `mise deps` is experimental, and that indirection is
what makes reverting to a plain `uv sync` a one-line change in one place.

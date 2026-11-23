# Python Tooling Guidelines

How a Python project is built, how its environment is created, and which tools
check it: `pyproject.toml`, the Python settings in `mise.toml` (`[deps.uv]`, the
`python` and `uv` pins, `UV_*`), `uv.lock` and a test `conftest.py`. Read it
before changing any of them, or the Python version. The language itself is in
[python.md](../coding/python.md), the editor in [ide.md](ide.md), and task
naming in [mise.md](mise.md#name-tasks-by-family).

<!-- toc -->
**On this page**

- [Target the latest stable Python, unless others install the package](#target-the-latest-stable-python-unless-others-install-the-package)
  - [Name the version in the four places that pin it](#name-the-version-in-the-four-places-that-pin-it)
  - [Move to a new Python release](#move-to-a-new-python-release)
  - [When a dependency lags](#when-a-dependency-lags)
- [Build and Packaging](#build-and-packaging)
  - [Build with hatchling and uv-dynamic-versioning](#build-with-hatchling-and-uv-dynamic-versioning)
  - [Pin the build backend explicitly](#pin-the-build-backend-explicitly)
  - [Guard against a `0.0.0` release](#guard-against-a-000-release)
  - [Tell hatchling what to package](#tell-hatchling-what-to-package)
  - [Keep the version honest in editable installs](#keep-the-version-honest-in-editable-installs)
- [Mise and uv](#mise-and-uv)
  - [Pin uv to mise's interpreter by absolute path](#pin-uv-to-mises-interpreter-by-absolute-path)
  - [Let `[deps.uv]` install the environment, and mise only source it](#let-depsuv-install-the-environment-and-mise-only-source-it)
  - [Assert the lock in CI with `UV_LOCKED=1` and in `lint` with `uv lock --check`](#assert-the-lock-in-ci-with-uv_locked1-and-in-lint-with-uv-lock---check)
  - [Invoke tools through `uv run --no-sync <tool>` in mise tasks, not bare](#invoke-tools-through-uv-run---no-sync-tool-in-mise-tasks-not-bare)
  - [Add and remove dependencies with `uv add` and `uv remove`, then run `fmt`](#add-and-remove-dependencies-with-uv-add-and-uv-remove-then-run-fmt)
  - [Keep `install` and `reinstall` as tasks over `mise deps`](#keep-install-and-reinstall-as-tasks-over-mise-deps)
- [Code Quality Tools](#code-quality-tools)
  - [Lint and format with ruff](#lint-and-format-with-ruff)
  - [Type-check with pyright, in strict mode, tests included](#type-check-with-pyright-in-strict-mode-tests-included)
  - [Declare module boundaries as import-linter contracts](#declare-module-boundaries-as-import-linter-contracts)
  - [Prefer contracts whose coverage follows the code](#prefer-contracts-whose-coverage-follows-the-code)
  - [Give every `ignore_imports` entry its reason](#give-every-ignore_imports-entry-its-reason)
  - [Find unused code with deadcode](#find-unused-code-with-deadcode)
- [Tests](#tests)
  - [Run test suites in parallel with pytest-xdist](#run-test-suites-in-parallel-with-pytest-xdist)
  - [Enforce the patching rule](#enforce-the-patching-rule)
- [Rationale](#rationale)
  - [Target the latest stable Python, unless others install the package](#target-the-latest-stable-python-unless-others-install-the-package-1)
  - [Pin the build backend explicitly](#pin-the-build-backend-explicitly-1)
  - [Guard against a `0.0.0` release](#guard-against-a-000-release-1)
  - [Let `[deps.uv]` install the environment, and mise only source it](#let-depsuv-install-the-environment-and-mise-only-source-it-1)
  - [Invoke tools through `uv run --no-sync <tool>` in mise tasks, not bare](#invoke-tools-through-uv-run---no-sync-tool-in-mise-tasks-not-bare-1)
  - [Prefer contracts whose coverage follows the code](#prefer-contracts-whose-coverage-follows-the-code-1)
<!-- tocstop -->

## Target the latest stable Python, unless others install the package

How far back a project supports Python depends on who installs it:

- **An application**, a CLI installed with `uv tool`, `pipx` or `uvx`, or a
  site or service, targets one version: the latest stable CPython release, the
  one `[tools] python` in `mise.toml` pins. The minimum supported version, the
  version developed on and the version CI tests are the same.
- **A library**, a package installed into other projects' environments,
  supports a range: from the oldest Python its consumers run to the latest. For
  one used only by iglootools projects, such as common's `iglootools`, the
  floor is the oldest Python those projects pin. It is developed and tested on
  the latest, like an application, while ruff and pyright check it against the
  floor.

**Why:** an older floor puts every newer feature off-limits, and has CI test a
version nobody develops on. An application's users can get a current
interpreter in one step, so it pays none of that cost. A library runs on its
consumers' interpreter, so it has to meet the oldest one.
[Rationale](#target-the-latest-stable-python-unless-others-install-the-package-1)

- CI takes its interpreter from `mise.toml`, as a developer machine does, with
  no version matrix.
- There is no compatibility check (`vermin`). An application has nothing that
  can be too new. A library's ruff and pyright targets catch most uses of newer
  syntax and standard-library APIs. A behaviour that differs on the floor shows
  up in the CI of the consumer that runs it.
- Raise a library's floor when its last consumer on that version moves, and
  say so in a comment next to `requires-python`.
- A dependency without wheels for the latest release holds the project back as
  [When a dependency lags](#when-a-dependency-lags) describes.

### Name the version in the four places that pin it

Four settings name the floor `F` and the latest `L`. In an application they are
the same version, and all four move together, in one change; in a library, the
settings that name the same version move together:

| Setting | Where | Value |
|---|---|---|
| `[tools] python` | `mise.toml` | the latest, as the exact patch release `3.L.Y`; CI installs it from here |
| `requires-python` | `pyproject.toml` | `>=3.F,<3.(L+1)` |
| ruff `target-version` | `pyproject.toml` | the floor, `py3F` |
| pyright `pythonVersion` | `pyproject.toml` | the floor, `3.F` |

**Why:** settings that disagree check the code against one version and run it on
another. The upper bound keeps the package off a Python nobody has tested, so it
is raised deliberately, with the others, never automatically.

### Move to a new Python release

Move once every dependency publishes wheels for the new version. After raising
`requires-python`, relock with `uv lock --upgrade` and ask for wheels
explicitly:

```bash
uv sync --no-build --dry-run
```

**Why:** `uv lock` resolves happily to a release that has only an sdist, and a
developer machine with a compiler builds it without a word, so the gap shows up
later as a failed install on a user's machine.

- `--upgrade`, because an older locked release often predates the new wheels.
- The dry run names every package that would be built from source. A pure-Python
  package whose sdist builds without a compiler, such as PyYAML falling back
  from its C extension, is acceptable. Anything that needs a C, C++ or Rust
  toolchain is not.
- Then:
  1. Move all four settings, relock (`uv lock`, `mise lock`), and run
     `mise run preflight`. A library moves only the latest, `[tools] python`
     and the upper bound of `requires-python`; its floor moves with its last
     consumer.
  2. Run `ruff check --fix`: with the new `target-version`, its `UP` rules
     rewrite the idioms the new version makes redundant.
  3. Adopt the release's new features where they remove a workaround or make
     the code simpler, not everywhere they could apply.

### When a dependency lags

A dependency that publishes no wheels for the latest release holds the project
back. Stay on the newest version that dependency supports, and record it as a
[documented exception](../applying-the-guidelines.md#documented-exceptions): a
comment next to `requires-python` naming the dependency and the condition that
retires it, usually "move when it publishes wheels for 3.x". Do not build the
dependency from source to get ahead of it.

**Why:** building from source trades a version number for a toolchain every
user then needs.

## Build and Packaging

### Build with hatchling and uv-dynamic-versioning

Build with `uv`, `hatchling` as the backend and
[`uv-dynamic-versioning`](https://github.com/ninoseki/uv-dynamic-versioning) for
versions derived from git tags. Commit `uv.lock`.

```toml
[build-system]
requires = ["hatchling", "uv-dynamic-versioning"]
build-backend = "hatchling.build"

[tool.hatch.version]
source = "uv-dynamic-versioning"
```

**Why:** `uv`'s own `uv_build` backend cannot derive a version from a VCS
([astral-sh/uv#14561](https://github.com/astral-sh/uv/issues/14561)), and
`hatch-vcs` uses a different dev-version format.

- Versions come from `dunamai`: `0.6.1` on a tagged commit,
  `0.6.1.post6.dev0+2a99beb` off one.

### Pin the build backend explicitly

Pin the whole build closure in `[tool.uv] build-constraint-dependencies`,
including `dunamai`, which computes the version. Leave `[build-system].requires`
unpinned, so the two never contradict each other.

**Why:** `uv.lock` does not resolve PEP 517 build dependencies, so without the
constraints `uv build` resolves them fresh from PyPI on a cold cache.
[Rationale](#pin-the-build-backend-explicitly-1)

- Regenerate the list with:

  ```bash
  printf '%s\n' hatchling uv-dynamic-versioning \
    | uv pip compile - --no-annotate --no-header --quiet
  ```

- No built-in Renovate manager reads `build-constraint-dependencies`. The shared
  `python` preset ([renovate/python.json](../../renovate/python.json)) carries
  the custom manager that does: extend it
  ([dependency-automation.md](dependency-automation.md#extend-the-shared-renovate-presets))
  rather than copying it.
- `uv.lock` records the constraints in its `[manifest]`, and Renovate relocks
  only for what its built-in managers extracted. A bump from the custom manager
  therefore leaves `uv.lock` stale, and CI fails under `UV_LOCKED=1`. A project
  with these pins calls the
  [shared lock regenerator](shared-workflows.md#call-the-shared-lock-regenerator-on-renovate-branches),
  which runs `uv lock` on Renovate branches.

### Guard against a `0.0.0` release

Set `[tool.uv-dynamic-versioning] fallback-version`, and add a `build-verify`
task that `ci-build` runs after `build`:

```toml
[tasks.build-verify]
description = "Fail if the built wheel carries the 0.0.0 fallback version"
run = "uv run --no-sync iglootools python verify-version"
```

**Why:** Renovate runs `uv lock --upgrade-package` with no git context, so
without a fallback every such PR fails. With one, a build with no git history
succeeds as `0.0.0`, nothing else in the publish path catches it, and PyPI
never accepts a version twice. [Rationale](#guard-against-a-000-release-1)

- `iglootools python verify-version` is described in
  [iglootools-cli.md](iglootools-cli.md).

### Tell hatchling what to package

Set `[tool.hatch.build.targets.wheel] packages` and
`[tool.hatch.build.targets.sdist] only-include` explicitly.

**Why:** hatchling's sdist includes every file the VCS does not ignore,
shipping `tests/`, `docs/`, `.github/` and the lockfiles. Its wheel is inferred
from a `<NAME>/__init__.py` heuristic, and when the heuristic misses the wheel
is silently empty rather than an error.

- hatchling reads only `.gitignore`, so a file ignored only locally is
  published: see
  [repository.md › the committed `.gitignore`](repository.md#ignore-os-and-editor-cruft-and-generated-iglootools-output-in-the-committed-gitignore).
- When changing build backend, prove parity: diff the wheel payload and the
  sdist file list against the previous toolchain's at the same tag, and install
  the wheel and exercise anything read through `importlib.resources` or
  `Path(__file__).parent`, which a file-list diff does not cover.

### Keep the version honest in editable installs

Add git to uv's cache keys, keeping the `pyproject.toml` entry:

```toml
[tool.uv]
cache-keys = [{ file = "pyproject.toml" }, { git = { commit = true, tags = true } }]
```

**Why:** code that reads its own version through `importlib.metadata` gets what
was frozen into `.dist-info` at install time, which goes stale on the next
commit.

- The setting replaces the default `[{ file = "pyproject.toml" }]` rather than
  extending it, hence the explicit file entry.
- `[deps.uv]` hashes only `uv.lock` and `pyproject.toml`, so a plain commit
  fires no automatic sync, and the version stays stale until something forces
  one.
- An uncommitted tree reports the last commit's version: `dunamai`'s default
  format carries no dirty marker.

## Mise and uv

Common's [mise.toml](../../mise.toml) is a working example of these settings,
with each line's reason.

These apply to every iglootools project, with Python or without, since each
installs the `iglootools` command through uv
([iglootools-cli.md](iglootools-cli.md#install-it-as-a-dev-dependency-pinned-to-a-release)).
The rest of this file is for Python projects only.

### Pin uv to mise's interpreter by absolute path

Set `UV_PYTHON` to `{{ tools.python.path }}`, with
`UV_PYTHON_DOWNLOADS = "never"` and `UV_PYTHON_PREFERENCE = "only-system"`.

**Why:** mise documents that a bare version number does not guarantee uv uses
the interpreter mise manages. uv may build the venv on a system Python of the
same version, and a raised `[tools] python` pin stops recreating `.venv`,
since the old interpreter still satisfies `requires-python`.

### Let `[deps.uv]` install the environment, and mise only source it

Set `python.uv_venv_auto = "source"` in `[settings]`, not `"create|source"`,
and not `_.python.venv` in `[env]`. Enable `[deps.uv]` with `auto = true`, and
`experimental = true` in the committed `mise.toml`.

**Why:** with `[deps.uv]` enabled, creating the venv is the deps provider's job,
and the two collide when both try.
[Rationale](#let-depsuv-install-the-environment-and-mise-only-source-it-1)

- `_.python.venv` is for projects that do not use uv: a separate code path, so
  `uv_venv_auto` replaces it rather than adding to it.
- `auto = true` runs `uv sync` before any `mise run`, gated on a hash of
  `uv.lock` and `pyproject.toml` and on `.venv` existing. Without it, every task
  needs a manual `install` first or runs against a stale environment.
- `experimental = true` in the file, not in each developer's
  `MISE_EXPERIMENTAL`: otherwise a fresh clone behaves differently from CI, and
  dependencies do not install with no error naming the cause.
- The built-in command is a bare `uv sync`. Set `run = "uv sync --all-extras"`
  only in a project with extras. Overriding `run` keeps the source hashing and
  the `.venv` tracking.
- On a fresh clone, `.venv` does not exist until the first `mise run`:
  `mise install` alone does not create it, so nothing is on `PATH` for that
  first run.

### Assert the lock in CI with `UV_LOCKED=1` and in `lint` with `uv lock --check`

Set `UV_LOCKED: 1` in the environment of every CI job that syncs, and give the
project a `lint-lock-uv` task running `uv lock --check`.

**Why:** without the assertion, a stale lockfile is papered over by an implicit
re-resolve on the runner, and CI tests something nobody committed.

- The two ask different questions: `uv lock --check` whether `uv.lock` is
  consistent with `pyproject.toml`, `UV_LOCKED` whether a sync would change it.
- Prefer the environment variable to a `--locked` flag, so the `[deps.uv]`
  command stays identical locally and in CI and only the strictness differs.
- The `mise.lock` counterpart, `lint-lock-mise`, is in
  [mise.md](mise.md#check-miselock-in-a-scratch-copy).

### Invoke tools through `uv run --no-sync <tool>` in mise tasks, not bare

Write `run = "uv run --no-sync ruff check ."`, not `run = "ruff check ."`, and
state the same rule in the project's own docs, with `mise exec -- <tool>` as the
way to run a tool from an unactivated shell.

**Why:** mise does not remove a foreign `.venv/bin` already on `PATH`, so in a
shell where another project's virtualenv is active a bare `ruff` silently runs
that project's copy.
[Rationale](#invoke-tools-through-uv-run---no-sync-tool-in-mise-tasks-not-bare-1)

- `uv run` resolves the environment from the project root and ignores `PATH`.
  `--no-sync` leaves installing to `[deps.uv]` alone.
- Tools mise itself installs, such as dprint and rumdl, run bare.

### Add and remove dependencies with `uv add` and `uv remove`, then run `fmt`

Use `uv add` and `uv remove`, which update `pyproject.toml` and `uv.lock`
together, and run `mise run fmt` before committing.

**Why:** both write `pyproject.toml` in uv's style, which `lint-fmt` rejects.

- `mise deps add` does not support uv: its ecosystems are npm, yarn, pnpm, bun,
  deno, aube, dart and flutter.

### Keep `install` and `reinstall` as tasks over `mise deps`

`install` runs `mise deps install uv`, not `uv sync`. `reinstall` runs
`iglootools python reinstall`, which deletes `.venv` and runs
`mise deps install uv --force`.

```toml
[tasks.reinstall]
description = "Delete .venv and reinstall dependencies from scratch"
run = "uv run --no-sync iglootools python reinstall"
```

**Why:** `mise deps` is experimental, and delegating to it keeps reverting to a
plain `uv sync` a one-line change in one place. `reinstall` covers the one case
the hashing cannot see: a venv that is dirty rather than stale, after a
`uv pip install` by hand.

- `uv sync` is exact by default, and `UV_PYTHON` picks up a raised
  `[tools] python`, so neither needs `reinstall`.
- `build` and `clean` are `iglootools python build` and `iglootools python
  clean`, so no Python task needs a file under `mise-tasks/`.
- The generated-document tasks (`clidocs`, `depgraph`, `configdocs`) are in
  [layout.md](../documentation/layout.md#generate-references-from-the-code-and-check-them).

## Code Quality Tools

Each tool runs as a `lint-*` task in `lint`, so `preflight` and CI run it:

| Tool | Checks | Task |
|---|---|---|
| ruff | lint and format | `lint-ruff`, `lint-fmt-ruff`, `fmt-ruff` |
| pyright | types | `lint-types` |
| import-linter | module boundaries | `lint-boundaries` |
| deadcode | code nothing uses | `lint-dead-code` |

The other files are formatted as [formatting.md](formatting.md) describes.

### Lint and format with ruff

Configure ruff in `pyproject.toml` with `target-version` as
[Name the version](#name-the-version-in-the-four-places-that-pin-it) gives it,
`select = ["ALL"]`, and `ignore` holding only the rules
[ADR-003](../../docs/architecture-decision-record.md#adr-003--enable-every-ruff-rule-except-those-our-conventions-are-against)
lists: the rules a convention is against, or that fight the formatter. Copy
common's `[tool.ruff.lint]` block, which also bans relative imports, sets
`max-statements = 30` and selects the preview rule `PLW1514`.

**Why:** a rule that is on rejects the mistake when it is made
([general.md](../coding/general.md#enforce-with-a-tool-what-a-tool-can-check)),
and an ignore list with reasons makes each exception a deliberate choice.

- **Ignore a rule for a project's own exception as narrowly as the exception
  reaches**, saying why: a `# noqa: <rule>` on the line, a `per-file-ignores`
  entry, or, for an exception the whole project shares such as photree's naive
  EXIF times, an `ignore` entry under `DTZ001`. An optional extra's in-function
  import carries `# noqa: PLC0415`.
- **A rule a convention is against goes into ADR-003**, with its reason, and
  into every project's `ignore`.
- **A ruff upgrade turns on new rules.** Fix their findings in the upgrade's
  pull request, or add the rule to ADR-003.

### Type-check with pyright, in strict mode, tests included

Add `pyright` to the dev dependency group and run it as `lint-types`
(`uv run --no-sync pyright`, with no paths), configured under `[tool.pyright]`:

```toml
[tool.pyright]
include = ["src", "tests"]                    # every directory of Python: package, tests, scripts
typeCheckingMode = "strict"
reportUnnecessaryTypeIgnoreComment = "error"
```

**Why:** the same configuration then serves the CLI, CI, the editor and Claude
Code's language server, and checks the same files in each. Strict mode reports
what standard mode lets through: values of unknown type, a `match` that misses a
case, a bare `list` or `dict`, a check that cannot fail, a private name used
from another module. Tests are code too; left unchecked, they drift from the
signatures they call.
[ADR-002](../../docs/architecture-decision-record.md#adr-002--keep-pyright-as-the-type-checker-rather-than-switching-to-ty)
records why pyright rather than ty.

- **A `match` that handles only some cases ends in `case _: pass`** with a
  comment saying where the other cases go, so the fall-through is visible.
- **Suppress one line, never a rule project-wide:**
  `# pyright: ignore[<rule>]` with its reason, as
  [applying-the-guidelines.md › Write each departure where a reader will hit it](../applying-the-guidelines.md#write-each-departure-and-its-reason-where-a-reader-will-hit-it)
  asks. The usual reason is a dependency that leaves something unannotated.
  `reportUnnecessaryTypeIgnoreComment` fails on a suppression that is no longer
  needed, so none outlives its reason.
- **Give an empty container its type** (`found: list[Reference] = []`), and
  test a public function rather than a `_private` one: make the function public
  when a test needs it.
- `pythonVersion` is one of the
  [four version settings](#name-the-version-in-the-four-places-that-pin-it).
- `venvPath` and `venv` are in
  [ide.md](ide.md#pin-the-venv-for-pyright-in-toolpyright).

### Declare module boundaries as import-linter contracts

Add `import-linter>=2.15,<3.0` to the dev dependency group, declare the
contracts under `[tool.importlinter]`, and run them as `lint-boundaries`
(`uv run --no-sync lint-imports`). What the contracts mean is in
[python.md › Module Boundaries](../coding/python.md#module-boundaries).

```toml
# Module boundaries, enforced by `mise run lint-boundaries` (part of `lint`).
# The rationale for each rule is in docs/architecture.md#layering.
[tool.importlinter]
root_package = "<pkg>"
include_external_packages = true   # lets a contract name rich and typer
```

**Why:** a boundary no check enforces erodes one convenient import at a time.

- The comment above the table names the task and the architecture section that
  explains the rules. Update it when either is renamed: nothing fails when it
  points at something that no longer exists.
- The task is `lint-boundaries`, named for the property, not `lint-imports`,
  which names the tool and is easily mistaken for its command.
- import-linter reads every import, including those inside functions, so a rule
  such as "the ML stack is imported lazily" is not a contract. Check it with a
  test that imports the entry point and inspects `sys.modules`.

### Prefer contracts whose coverage follows the code

Choose the contract type that covers a new module without editing a list:

| Type | Use it for | Coverage of a new module |
|---|---|---|
| `layers` | the top-level ordering of packages, highest first; `\|` separates siblings that must not import each other | automatic: a layer is a whole package |
| `protected` | "only X may import Y", such as only CLI modules importing `typer` | automatic: any new importer is caught |
| `independence` | sibling sub-apps that must not import each other | only the listed modules |
| `forbidden` | everything else, especially "core never reaches the CLI layer, even indirectly" | only the listed `source_modules`, unless written with wildcards (`<pkg>.*.cli`) |

**Why:** a contract with an enumerated list covers exactly what is listed. A
module added later is unchecked, and the run still passes.

- Where a list is unavoidable, say so in a comment above it ("a new subpackage
  outside `cli/` belongs on this list"): it is the only reminder the next person
  gets.
- A package listed as a `forbidden` source also covers its own `cli/`. List its
  non-CLI subpackages instead, and cover its `__init__` with a second contract
  that sets `as_packages = false`.
- `acyclic_siblings` is not a default: it suits a project split by layer, not
  one where each package keeps its own `cli/`.
  [Rationale](#prefer-contracts-whose-coverage-follows-the-code-1)

### Give every `ignore_imports` entry its reason

Put a comment on each `ignore_imports` entry saying why the edge is acceptable,
and leave `unmatched_ignore_imports_alerting` at its default, `error`.

**Why:** an entry that no longer matches then fails the check instead of
lingering as an exemption for code that has moved.

### Find unused code with deadcode

Add `deadcode>=2.7.0,<3.0` to the dev dependency group, run it as
`lint-dead-code` (`uv run --no-sync deadcode <pkg> tests`), and list in
`[tool.deadcode]` what runs without being named in the project: commands and
fixtures registered by decorator, Pydantic validators and serializers, the
entry point, and names pytest reads. nbkp's
[pyproject.toml](https://github.com/iglootools/nbkp/blob/main/pyproject.toml)
is a working example.

**Why:** ruff and pyright report an unused import or variable within one file,
but not a function, method or class nothing calls any more. deadcode also
reports commented-out code, which
[general.md](../coding/general.md#code-comments) says to delete.

- Scan the package and its tests together, so a test helper or a `testkit`
  module counts as used. Code only the tests use is then not reported.
- An exception sits on the line it excuses, with its reason:
  `# noqa: DC04 -- Paramiko calls it on an unknown host key`. The config holds
  only patterns that recur, each with its comment. Declare deadcode's codes to
  ruff with `external = ["DC"]` under `[tool.ruff.lint]`, or `RUF100` reports
  them as unused.
- Delete what deadcode reports, unless it is one of those exceptions. A
  commented-out line that is really prose (`# SSH: StrictHostKeyChecking`) is
  rephrased, not kept as code.
- Review `deadcode --fix` like any other diff, and commit it alone with the
  command in the message
  ([git.md](../coding/git.md#keep-refactoring-apart-from-behaviour-changes)). It
  removes a whole cascade in one pass, but can cut a multi-line function short
  and leave a file that does not parse: run the checks after it, and fix by hand
  what it mangles.
- Retire deadcode once ruff or ty detects unused definitions across files.

## Tests

### Run test suites in parallel with pytest-xdist

Add `pytest-xdist` to the dev dependency group and pass `-n auto` in every test
task whose tests are isolated: each working under its own `tmp_path`, taking
its dependencies as fakes, and sharing no module-level state.

```toml
[tasks.test-unit]
description = "Run unit tests"
# -n auto: unit tests are isolated (tmp_path, injected fakes), so they parallelize cleanly.
run = "uv run --no-sync pytest tests/ --ignore=tests/integration_fs/ -n auto -v"
```

**Why:** one worker per CPU keeps the suite running in seconds as it grows
([Shorten every feedback loop](../philosophy.md#shorten-every-feedback-loop)).

- Put `-n auto` in the task, not in `addopts`, which applies to every
  invocation: one test run by hand, or under `--pdb`, would also start a worker
  per CPU, and under xdist a debugger has no interactive terminal.
- A test that passes alone and fails under `-n auto` depends on state another
  test leaves behind, or on order. Fix the isolation rather than dropping
  `-n auto`.
- A suite that shares a resource too expensive to duplicate per worker, such as
  a Docker environment started once per session, leaves `-n auto` off, with a
  comment at the task naming the resource.

### Enforce the patching rule

Enforce
[general.md › Patch only in the three documented cases](../coding/general.md#patch-only-in-the-three-documented-cases-and-list-each-one)
and
[python.md › Tests](../coding/python.md#tests) with pytest and ruff, in three
steps.

**Why:** a rule only reviewers enforce is broken in the first rushed change,
and nothing reports it.

1. **Replace the `monkeypatch` fixture** in the root `tests/conftest.py` with
   one that calls `pytest.fail` and says why
   ([tests/conftest.py](../../tests/conftest.py) is a working example). A
   fixture defined there overrides pytest's for every test below it. Not
   `-p no:monkeypatch` in `addopts`: pytest loads its built-in plugins before it
   reads `addopts` from `pyproject.toml`, so the flag works only on the command
   line.
2. **Ban what is left with ruff.** `TID251` (`banned-api`) bans `unittest.mock`
   and `pytest.MonkeyPatch`, the only ways to patch once the fixture is gone,
   each with a message pointing at the rule
   ([pyproject.toml](../../pyproject.toml) is a working example).
3. **Mark each exception at its import**, with its category, not in
   `per-file-ignores`: ruff does not report a stale `per-file-ignores` entry,
   while `RUF100` reports a stale `noqa`. A file that patches in several tests
   defines its own `monkeypatch` fixture in the test module, never in a
   `conftest.py`, where it would re-enable patching for the whole directory.

   ```python
   from pytest import MonkeyPatch  # noqa: TID251 -- (c) HOME, read by a library below any seam


   @pytest.fixture
   def monkeypatch() -> Iterator[MonkeyPatch]:
       """Patching is allowed in this file only: see docs/guidelines.md (Tests)."""
       with MonkeyPatch.context() as patch:
           yield patch
   ```

- Give `tests/conftest.py` a `chdir` fixture over `contextlib.chdir`, undone at
  the end of the test:

  ```python
  @pytest.fixture
  def chdir() -> Iterator[Callable[[Path], None]]:
      """Change the working directory until the end of the test."""
      with contextlib.ExitStack() as stack:
          yield lambda path: stack.enter_context(contextlib.chdir(path))
  ```

- The exceptions table in `docs/guidelines.md` stays the one list of reasons.
  Each `noqa` comment carries a short form of its row.
- A project adopting the rule with patches in place marks each one **pending**
  the same way, so the checks go in before the tests are converted.

## Rationale

### Target the latest stable Python, unless others install the package

Supporting an older Python costs more than it buys for these projects. Every
feature newer than the floor is off-limits, a separate check (`vermin`) is
needed to enforce that fully because ruff's and pyright's targets miss cases,
and CI has to test a version nobody develops on. Meanwhile the applications are
installed by people who can get a current interpreter in one step:

- `uv tool install <tool>` downloads a managed Python when the system has no
  matching one, so the distribution's `python3` does not matter.
- `pipx install --python <path-to-python3.X> <tool>` works the same way with an
  interpreter installed by any other means (mise, pyenv, a PPA, Homebrew).

The system `python3` of an LTS distribution is therefore not a constraint, and
the projects do not track it.

A library has no such way out: it is imported by its consumers' interpreter,
whichever version that is. Its floor follows the oldest consumer, and it pays
the cost above only for the versions between that floor and the latest. For a
library used only by iglootools projects that range is small, and the floor
rises as the projects move.

### Pin the build backend explicitly

The custom manager in [renovate/python.json](../../renovate/python.json) uses
two patterns under the `recursive` strategy: the first isolates the array, the
second captures every pin within it. The obvious single pattern, anchored on the
field name, extracts only the first pin, since the anchor is consumed by the
first match. That fails quietly: Renovate keeps updating one dependency, and the
build closure looks maintained. In photree it extracted one of ten pins.

### Guard against a `0.0.0` release

Building the wheel from an sdist is safe: hatchling writes the resolved version
into the sdist's `PKG-INFO` and reads it back, verified by building from an
extracted sdist with no `.git`. `uv build --sdist --wheel` (both from source),
which `iglootools python build` runs, is mildly preferable at no cost, but it is
not a workaround for a broken path. Building from a source tree with `.git`
removed is what yields `<pkg>-0.0.0-py3-none-any.whl` and exits 0.

### Let `[deps.uv]` install the environment, and mise only source it

mise's cookbook says that with `[deps.uv]` enabled, creating the venv is the
deps provider's job. Measured on a fresh clone with `"create|source"`,
`mise install` announced `creating venv with uv at: …` and then failed on its
own result: `error: Failed to create virtual environment / Caused by: A virtual
environment already exists at: .venv`, then `WARN uv venv creation failed`. With
`"source"` the same clone installs silently, and the first `mise run` lets
`[deps.uv]` create and populate `.venv`.

### Invoke tools through `uv run --no-sync <tool>` in mise tasks, not bare

Measured in a multi-project checkout, the current project's venv landed at
`PATH` position 16 and a foreign one at position 1. `uv run --no-sync` was not
measurably slower than a bare invocation. It also covers the first `mise run` on
a fresh clone, when `.venv` does not yet exist and nothing of the project's is
on `PATH`.

### Prefer contracts whose coverage follows the code

Run against nbkp and photree with the root package as ancestor,
`acyclic_siblings` reported cycles between each module's `cli/` subpackage and
the shared CLI wiring below them, which is layering both projects intend.

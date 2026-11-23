# IDE Guidelines

Editor configuration: `.vscode/`, a `*.code-workspace` and `[tool.pyright]`.
Read it before changing any of them, or when the editor and the tasks disagree
about a file. The Claude Code side is in [claude-code.md](claude-code.md), and
the toolchain the editor points at in [python-tooling.md](python-tooling.md).

<!-- toc -->
**On this page**

- [Pin the venv for pyright in `[tool.pyright]`](#pin-the-venv-for-pyright-in-toolpyright)
- [VSCode](#vscode)
  - [Commit the extension set to `.vscode/extensions.json`](#commit-the-extension-set-to-vscodeextensionsjson)
  - [Format on save with the tools the tasks run](#format-on-save-with-the-tools-the-tasks-run)
  - [Check the in-project venv into `.vscode/settings.json`](#check-the-in-project-venv-into-vscodesettingsjson)
  - [Let `hverlin.mise-vscode` write the other tools' paths, but fence it in](#let-hverlinmise-vscode-write-the-other-tools-paths-but-fence-it-in)
  - [Reload after changing interpreter or pyright settings](#reload-after-changing-interpreter-or-pyright-settings)
  - [Keep projects apart in a multi-root workspace with per-project settings](#keep-projects-apart-in-a-multi-root-workspace-with-per-project-settings)
- [Rationale](#rationale)
  - [Let `hverlin.mise-vscode` write the other tools' paths, but fence it in](#let-hverlinmise-vscode-write-the-other-tools-paths-but-fence-it-in-1)
  - [Keep projects apart in a multi-root workspace with per-project settings](#keep-projects-apart-in-a-multi-root-workspace-with-per-project-settings-1)
<!-- tocstop -->

## Pin the venv for pyright in `[tool.pyright]`

Pin the project's virtualenv in `pyproject.toml`:

```toml
[tool.pyright]
venvPath = "."
venv = ".venv"
```

**Why:** with nothing configured, pyright falls back to the `python` on `PATH`.
A language server spawned by an editor inherits no activated environment, so it
reports `Import "<dep>" could not be resolved` on a file `mise run lint-types`
passes.

- The two settings serve every consumer at once: Pylance, the Claude Code
  pyright server, the CLI and CI. They restate uv's default `.venv` for the
  consumers that cannot discover it.
- Both keys are needed: `venv` is a directory name looked up inside `venvPath`,
  not a path.
- `pythonVersion` is a separate setting, the language level to check against,
  which pyright does not infer from `.venv`. It is one of the
  [four version settings](python-tooling.md#name-the-version-in-the-four-places-that-pin-it).
- Verify it the way a language server sees it, with the venv off `PATH` (an
  activated shell or a `uv run` prefix masks the failure):

  ```bash
  env -u VIRTUAL_ENV PATH=/usr/bin:/bin ./.venv/bin/pyright <file importing a dependency>
  ```

  Expect `0 errors`. With `--verbose`, the search paths include
  `.venv/lib/python<X.Y>/site-packages`.

## VSCode

### Commit the extension set to `.vscode/extensions.json`

Recommend every extension a committed setting depends on, as common's
[.vscode/extensions.json](../../.vscode/extensions.json) does.

**Why:** a setting whose extension is absent is not an error but a silent
no-op, and a fresh clone is prompted for the extensions only if they are
listed.

| Extension | Needed for | Consequence if missing |
|---|---|---|
| `ms-python.python` | every Python project | no test discovery, debugger, or terminal activation |
| `ms-python.vscode-pylance` | every Python project | the language server. Without it the Python extension falls back to Jedi and ignores `[tool.pyright]` |
| `ms-python.vscode-python-envs` | projects committing `python-envs.*` settings | the committed `pythonProjects` entry does nothing |
| `charliermarsh.ruff` | projects using ruff | `editor.defaultFormatter` names it, so format-on-save silently stops |
| `hverlin.mise-vscode` | projects using mise | `mise.enable` has no reader; tasks and tool versions stop surfacing |
| `tombi-toml.tombi` | every project with TOML, which is all of them | no validation of `pyproject.toml` and the other TOML files it has schemas for |
| `dprint.dprint` | projects with a `dprint.json` ([formatting.md](formatting.md)) | format-on-save stops for JSON, TOML and YAML |
| `rvben.rumdl` | projects with a `.rumdl.toml` | no Markdown lint findings in the editor, and format-on-save stops for Markdown |

### Format on save with the tools the tasks run

In `.vscode/settings.json`, name for each language the formatter the `fmt` task
runs, and turn on `formatOnSave`:

**Why:** several extensions format the same file (tombi and dprint both format
TOML, and VSCode has built-in JSON and Markdown formatters), so a file saved in
the editor passes `lint-fmt` only if the editor uses the task's formatter.
Without `formatOnSave` they run only on **Format Document**.

- tombi stays for validation, which dprint does not do.
- **Where another tool formats the code, turn `formatOnSave` on per language.**
  In a Nuxt project ESLint's stylistic rules own `.vue` and `.ts`, and a global
  `formatOnSave` would let Volar format them against those rules:

  ```json
  {
      "[yaml]": { "editor.defaultFormatter": "dprint.dprint", "editor.formatOnSave": true },
      "[markdown]": { "editor.defaultFormatter": "rvben.rumdl", "editor.formatOnSave": true }
  }
  ```

### Check the in-project venv into `.vscode/settings.json`

Commit the interpreter and the environment manager, with `envManager` set to
`ms-python.python:venv`:

```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
    "python-envs.pythonProjects": [
        {
            "path": ".",
            "envManager": "ms-python.python:venv"
        }
    ]
}
```

**Why:** these are what the rest of the Python extension reads (test discovery,
the debugger, the environment new terminals activate), instead of each developer
running **Python: Select Interpreter**. A committed `ms-python.python:system`
would point everyone who clones at the system interpreter.

- **Leave `packageManager` out.** `ms-python.vscode-python-envs` (checked at
  1.36.0) registers no uv package manager, and naming another tool would point
  at one the project does not use. The default, `:pip`, drives only the
  extension's install and uninstall UI. Add it once the extension registers uv.

### Let `hverlin.mise-vscode` write the other tools' paths, but fence it in

Let the extension derive each extension's tool path from `mise.toml`, as
symlinks, from the project's tools only, and never for `ms-python.python`, as
the `mise.*` keys in common's
[.vscode/settings.json](../../.vscode/settings.json) do.

```json
{
    "mise.enable": true,
    "mise.configureExtensionsAutomatically": true,
    "mise.configureExtensionsUseSymLinks": true,
    "mise.configureExtensionsIncludeGlobalTools": false,
    "mise.configureExtensionsAutomaticallyIgnoreList": [
        "biomejs.biome",
        "oxc.oxc-vscode",
        "ms-python.python"
    ]
}
```

**Why:** each extension has its own key for its toolchain (`metals.javaHome`,
`deno.path`, `go.goroot`, …), and keys maintained by hand against `mise.toml`
drift.
[Rationale](#let-hverlinmise-vscode-write-the-other-tools-paths-but-fence-it-in-1)

- **`configureExtensionsUseSymLinks: true`** writes
  `${workspaceFolder}/.vscode/mise-tools/<tool>` rather than an absolute install
  path, which is version- and home-directory-specific and does not exist on
  anyone else's machine.
- **`configureExtensionsIncludeGlobalTools: false`**, the value the extension's
  documentation recommends, keeps tools from `~/.config/mise/config.toml` out of
  the project's settings.
- **Repeat the two default ignore-list entries**, `biomejs.biome` and
  `oxc.oxc-vscode`: supplying the setting replaces the default array. Both write
  absolute paths whatever the symlink setting says.
- **Ignore `ms-python.python`**, and keep the explicit `.venv` pin above: its
  generated value is wrong.
- **Ignore `.vscode/mise-tools/` in the committed `.gitignore`**, not only in
  `.git/info/exclude`, as
  [repository.md › the committed `.gitignore`](repository.md#ignore-os-and-editor-cruft-and-generated-iglootools-output-in-the-committed-gitignore)
  describes: the symlinks are per machine, and the extension's documentation
  makes this a condition of sharing the settings file.

### Reload after changing interpreter or pyright settings

Use **Developer: Reload Window**.

**Why:** a running server keeps serving diagnostics from the configuration it
started with, and current Pylance releases have no "Python: Restart Language
Server" command.

### Keep projects apart in a multi-root workspace with per-project settings

Rely on the per-project mechanisms below to keep projects apart, and never
accept or commit settings mise-vscode generates into a `.code-workspace` file.
Turn `configureExtensionsAutomatically` on per project, so it writes only in
single-folder windows, and repeat `"mise.enable": true` in the
`.code-workspace` file's `settings` block.

| Consumer | Mechanism | Scope |
|---|---|---|
| pyright: CLI, CI, Claude Code's LSP | `[tool.pyright] venvPath`/`venv` in each `pyproject.toml` | per project, with no VSCode involvement |
| Pylance, test discovery, debugger | `python.defaultInterpreterPath` in the folder's own `.vscode/settings.json` | `machine-overridable`, so a folder value overrides the workspace one |
| terminals and tasks | `uv run --no-sync <tool>` for a tool in the project's environment, which resolves from the project root and ignores `PATH`; `mise exec -- <tool>` for one mise installs; a bare name only in an interactive, mise-activated terminal with no other virtualenv active | per invocation |

**Why:** every `mise.*` setting is window-scoped, so a folder's value is ignored
in a multi-root window, and the extension writes one folder's tools into the
workspace file, where they apply to every folder.
[Rationale](#keep-projects-apart-in-a-multi-root-workspace-with-per-project-settings-1)

- The workspace file is a view onto projects, not a place for any one project's
  toolchain.
- The `configureExtensions*` keys serve toolchains with no equivalent of
  `.venv`; they replace no row of the table.

## Rationale

### Let `hverlin.mise-vscode` write the other tools' paths, but fence it in

**The ignore list.** `biomejs.biome` and `oxc.oxc-vscode` are upstream's
defaults, added as opt-in integrations ("biome extension support (disabled by
default)" in 0.57.0, "optional oxc-vscode support" in 1.8.0); the ignore list is
the only way to opt in. Both pass `useSymLinks: false` internally, so they write
absolute `~/.local/share/mise/installs/…` paths regardless of
`configureExtensionsUseSymLinks`. `oxc.oxc-vscode` also has a registry entry
keyed on `node`, so it fires for any project with `node` in `mise.toml`.

**Global tools.** With global tools included, a Nuxt repository declaring only
`node` and `pnpm` acquired `metals.javaHome` and a
`python.defaultInterpreterPath` pointing at a global mise interpreter, because
those tools were in `~/.config/mise/config.toml`.

**Why `ms-python.python` is excluded.** The extension prefers mise's
`VIRTUAL_ENV` and writes it verbatim, so the generated value is the environment
directory, `"${workspaceFolder}/.venv"`, not the interpreter
`${workspaceFolder}/.venv/bin/python` that `ms-python.python` documents ("Path
to default Python"). It shows up as an unexplained modification to a committed
`settings.json`. When `VIRTUAL_ENV` is absent, the extension writes the mise
toolchain interpreter instead, which is the state of a fresh clone, since
`mise install` does not create `.venv`
([Mise and uv](python-tooling.md#mise-and-uv)): generation then commits a Python
with none of the project's dependencies. Nothing is lost by excluding it:
Python already has `.venv`, pinned in `python.defaultInterpreterPath` and
`[tool.pyright]`.

### Keep projects apart in a multi-root workspace with per-project settings

Checked against `hverlin.mise-vscode` 1.23.0: every `mise.*` key, `mise.enable`
and all four `configureExtensions*` keys included, declares the default `window`
scope. VSCode reads window-scoped settings from user, remote and workspace
settings only, so a project that commits `"mise.enable": true` configures itself
as a single root and nothing when it is one folder among several.

The extension resolves a single current folder (chosen with **mise: Select
workspace folder**, defaulting to `workspaceFolders[0]`) and writes the
generated keys at `ConfigurationTarget.Workspace`, which in a multi-root window
is the `.code-workspace` file, with paths relative to an unqualified
`${workspaceFolder}`. On a seven-folder workspace, that sent all seven to
`${workspaceFolder}/.vscode/mise-tools/python`, which only the first folder had,
and whose symlink pointed at a global interpreter rather than any project's
`.venv`.

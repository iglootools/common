# Project Setup Guidelines

How an iglootools repository is configured, as opposed to how its code is
written ([../coding/](../coding/README.md)).

| File | Read it when the change touches |
|---|---|
| [repository.md](repository.md) | the committed `.gitignore`, setting up a new repository, its rulesets (branch or tag protection), how pull requests are merged, or the code of conduct and security policy |
| [workflows.md](workflows.md) | anything under `.github/workflows/`, `.github/actionlint.yaml`, or the `lint-github-actions` task |
| [shared-workflows.md](shared-workflows.md) | a workflow that calls one of the shared workflows: the link checker, the `mise.lock` regenerator, the uv dependency-graph submission, or the `release.yml` and `demo.yml` stubs; read it with `workflows.md`, not instead of it |
| [dependency-automation.md](dependency-automation.md) | `renovate.json`, `renovate/`, `dependabot.yml`, the `lint-renovate` or `renovate-dry-run` tasks, the `npm:renovate` pin and `.mise/locks/`, or a dependency update that did or did not appear |
| [mise.md](mise.md) | `mise.toml`, anything under `mise-tasks/`, `mise.lock`, or a shell script, in any project; adding, renaming or changing a mise task, including choosing its name, wherever the edit lands |
| [python-tooling.md](python-tooling.md) | Python building, packaging and dependencies: `pyproject.toml`, `uv.lock`, a test `conftest.py`, the import-linter setup, the dead-code check, the patching checks (ruff `TID251`, the failing `monkeypatch` fixture), the Python settings in `mise.toml` (`[deps.uv]`, the `python` and `uv` pins), the Python task set, or the Python version; adding a dependency, wherever the edit lands |
| [pypi-publishing.md](pypi-publishing.md) | publishing a Python project to PyPI: `release.yml`, `publish.yml` or `publish-test.yml`, the version scheme, or cutting a release by hand |
| [formatting.md](formatting.md) | `dprint.json`, `.rumdl.toml` or `.git-blame-ignore-revs`; the `fmt*`, `lint-fmt*` or `lint-markdown` tasks; or a formatting or Markdown lint failure to fix |
| [ide.md](ide.md) | `.vscode/`, a `*.code-workspace`, or the `[tool.pyright]` section of `pyproject.toml` |
| [claude-code.md](claude-code.md) | `.claude/settings.json`, which Claude Code plugins the project enables, or searching the code for a symbol's definition, references or callers |
| [iglootools-cli.md](iglootools-cli.md) | `[tool.iglootools]` in `pyproject.toml`, the `iglootools` dependency or its pin, a mise task that calls `iglootools`, or a bug found in one of its commands, which is fixed in iglootools/common rather than worked around in the project |
| [cli-demo.md](cli-demo.md) | a CLI project's asciinema demo: `demo/`, `.github/workflows/demo.yml`, the `demo-*` tasks, or the README's embed |
| [../documentation/layout.md](../documentation/layout.md#generate-references-from-the-code-and-check-them) | a CLI project's generated reference, and the `clidocs`/`lint-clidocs` tasks |

A change often reaches more than one row: a workflow that runs a mise task, or a
Python project's mise settings, needs every file whose row it matches. Two files
are split between guidelines. In `pyproject.toml`, `[tool.pyright]` is
`ide.md`'s and building, packaging and dependencies are `python-tooling.md`'s.
In `mise.toml`, tasks and the `mise.lock` check are `mise.md`'s, and a Python
project's uv settings are `python-tooling.md`'s.

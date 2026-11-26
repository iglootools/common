# Project Setup Guidelines

How an iglootools repository is configured, as opposed to how its code is
written ([../coding/](../coding/)).

| File | Read it when the change touches |
|---|---|
| [repository.md](repository.md) | `.gitignore`, repository rulesets or merge settings, community files, or setting up a new repository |
| [workflows.md](workflows.md) | anything under `.github/workflows/` |
| [shared-workflows.md](shared-workflows.md) | a caller of one of the five shared workflows: the link checker, the lock regenerator, the uv dependency-graph submission, the `release.yml` stub or the `demo.yml` stub |
| [dependency-automation.md](dependency-automation.md) | `renovate.json`, `renovate/`, `dependabot.yml`, the Renovate tasks or pin, or a dependency update that did or did not appear |
| [mise.md](mise.md) | `mise.toml`'s tasks, `mise-tasks/`, `mise.lock`, a shell script, or adding a mise task |
| [python-tooling.md](python-tooling.md) | a Python project: `pyproject.toml`, a test `conftest.py`, the Python settings in `mise.toml`, `uv.lock`, or the Python version |
| [pypi-publishing.md](pypi-publishing.md) | publishing a Python project to PyPI: `release.yml`, `publish.yml`, `publish-test.yml`, or cutting a release |
| [formatting.md](formatting.md) | `dprint.json`, `.rumdl.toml`, `.git-blame-ignore-revs`, the `fmt*`, `lint-fmt*` or `lint-markdown` tasks, or a formatting or Markdown lint failure |
| [ide.md](ide.md) | `.vscode/`, a `*.code-workspace`, or `[tool.pyright]` |
| [claude-code.md](claude-code.md) | `.claude/settings.json`, which plugins the project enables, or searching the code for a symbol's definition, references or callers |
| [iglootools-cli.md](iglootools-cli.md) | `[tool.iglootools]`, the `iglootools` pin, or a task that calls `iglootools` |
| [cli-demo.md](cli-demo.md) | a CLI project's asciinema demo: `demo/`, `demo.yml`, the `demo-*` tasks, or the README embed |
| [../documentation/layout.md](../documentation/layout.md#generate-references-from-the-code-and-check-them) | a CLI project's generated reference, and the `clidocs`/`lint-clidocs` tasks |

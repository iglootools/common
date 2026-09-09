# Project Setup Guidelines

How an iglootools repository is configured, as opposed to how its code is written. These are read
**on demand**: the `guidelines` skill routes to the one file a change actually reaches, because
each is long and stays in context for the rest of the session once read. One file per trigger is
deliberate — this was a single 501-line file, so a one-line workflow change pulled the Renovate
rules and the editor settings along with it.

| File | What is in it | Read it when the change touches |
|---|---|---|
| [workflows.md](workflows.md) | Pinning actions by SHA, pinning mise, lockable mise backends, `install: false`/`env: false` as a pair, naming a workflow after its file, choosing a concurrency group, job timeouts | anything under `.github/workflows/` |
| [shared-workflows.md](shared-workflows.md) | The three workflows this repository hosts and every project calls by pinned SHA — the link checker, the `mise.lock` regenerator, the uv dependency-graph submission — and what a caller must declare for each | adding or changing a caller of one of them |
| [dependency-automation.md](dependency-automation.md) | The Renovate/Dependabot split by latency, why committing `renovate.json` does not turn Renovate on, and the repository settings alerts and security updates depend on | `renovate.json`, `dependabot.yml`, or a dependency update that did or did not appear |
| [python-tooling.md](python-tooling.md) | The Python toolchain: hatchling, guarding against a `0.0.0` release, uv and mise configuration, invoking tools through `uv run --no-sync`, the mise task set, lock checks | `pyproject.toml`, `mise.toml`, `uv.lock`, `mise.lock`, or the task set |
| [ide.md](ide.md) | Pyright environment resolution, the committed extension set, checking `.venv` into `.vscode/settings.json`, fencing in `mise-vscode`, multi-root workspaces | `.vscode/`, a `*.code-workspace`, or `[tool.pyright]` |
| [claude-code.md](claude-code.md) | The Pyright LSP plugin, multi-project workspaces, picking up configuration changes, and committing the plugin set so the team gets it | `.claude/settings.json`, or which plugins the project enables |
| [repository.md](repository.md) | The conventional `docs/` paths the skill reads, ignoring OS and editor cruft in the committed `.gitignore`, `git config`, and where each project type goes next | `.gitignore`, or setting up a new repository |

Code rather than configuration is in [../coding/](../coding/).

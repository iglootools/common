# Project Setup Guidelines

How an iglootools repository is configured, as opposed to how its code is written. These are read
**on demand**: the `guidelines` skill routes to the one file a change actually reaches, because
each is long and stays in context for the rest of the session once read. One file per trigger is
deliberate — this was a single 501-line file, so a one-line workflow change pulled the Renovate
rules and the editor settings along with it.

| File | What is in it | Read it when the change touches |
|---|---|---|
| [workflows.md](workflows.md) | Thin workflows (a job calls one `mise run ci-*` task), least-privilege `permissions` on every job, pinning actions by SHA, pinning mise, lockable mise backends, `install: false`/`env: false` as a pair, naming a workflow after its file, choosing a concurrency group, job timeouts | anything under `.github/workflows/` |
| [shared-workflows.md](shared-workflows.md) | The three workflows this repository hosts and every project calls by pinned SHA — the link checker, the `mise.lock` and `uv.lock` regenerator, the uv dependency-graph submission — and what a caller must declare for each | adding or changing a caller of one of them |
| [dependency-automation.md](dependency-automation.md) | The Renovate/Dependabot split by latency, why committing `renovate.json` does not turn Renovate on, and the repository settings alerts and security updates depend on | `renovate.json`, `dependabot.yml`, or a dependency update that did or did not appear |
| [python-tooling.md](python-tooling.md) | The Python toolchain: hatchling, guarding against a `0.0.0` release, uv and mise configuration, invoking tools through `uv run --no-sync`, module boundaries with import-linter, the mise task set (including `ci-*` tasks), lock checks | `pyproject.toml` (including `[tool.importlinter]`), `mise.toml`, `uv.lock`, `mise.lock`, or the task set |
| [ide.md](ide.md) | Pyright environment resolution, the committed extension set, checking `.venv` into `.vscode/settings.json`, fencing in `mise-vscode`, multi-root workspaces | `.vscode/`, a `*.code-workspace`, or `[tool.pyright]` |
| [claude-code.md](claude-code.md) | The Pyright LSP plugin, multi-project workspaces, picking up configuration changes, and committing the plugin set so the team gets it | `.claude/settings.json`, or which plugins the project enables |
| [repository.md](repository.md) | Merge-commit pull requests, the default-branch and release-tag rulesets, the code of conduct and security policy inherited from `iglootools/.github`, ignoring OS and editor cruft in the committed `.gitignore`, `git config`, and where each project type goes next | `.gitignore`, repository rulesets or merge settings, community files, or setting up a new repository |
| [documentation.md](documentation.md) | The conventional paths the skill reads, keeping `docs/guidelines.md` lean and indexing area conventions from it, README vs `CONTRIBUTING.md` vs `docs/`, the `CONTRIBUTING.md` scaffold, `CLAUDE.md` as a list of imports, the recommended `docs/` set and one name per role, ADRs, recording repository settings as commands, generated references | `README.md`, `CONTRIBUTING.md`, `CLAUDE.md` or anything under `docs/` |
| [pypi-publishing.md](pypi-publishing.md) | Versions from git tags, conventional-commit bumps and choosing one by hand, the release → publish chain, trusted publishing and the `pypi`/`testpypi` environments, the Test PyPI rehearsal, recovering a failed publish | `release.yml`, `publish.yml`, `publish-test.yml`, or cutting a release |
| [cli-demo.md](cli-demo.md) | The asciinema demo: a scripted, deterministic, seeded session, recorded by mise tasks and in CI on every release, published from a developer machine and embedded in the README | `demo/`, `demo.yml`, the `demo-*` tasks, or the README embed |

Code rather than configuration is in [../coding/](../coding/).

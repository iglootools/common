# Repository Conventions

See [philosophy.md](../../philosophy.md) for the reasoning behind these guidelines, and
[Applying these guidelines](../../README.md#applying-these-guidelines) for how to deviate from
them — these are defaults, and a documented, justified exception is always allowed.

What every iglootools repository carries regardless of language, and where each project type
goes from here.

- Github build/test/release workflows — see [workflows.md](workflows.md)
- `git config user.email "<email>"` and `git config user.name "<name>"` in the project.

### Keep project documentation at the conventional paths

Three paths are fixed across iglootools projects, because the `guidelines` skill reads them by
convention rather than by being pointed at them:

| Path | Holds |
|---|---|
| `docs/guidelines.md` | deviations from the shared guidelines, which shared sections are out of scope, and rules of the project's own |
| `docs/implementation-checklists.md` | project-specific checks with no counterpart in the shared set |
| `docs/setup-development-environment.md` | how to get the project running, including installing the plugin |

Renaming one does not produce an error: the skill finds nothing, concludes the project documented
nothing project-specific, and applies the shared guidelines as written. A project's deviations
then stop being consulted with nothing to say so, which is the failure this repository exists to
prevent. Adding a file later needs no announcement — put it at the path and it is read.

Because these are conventions, a project's `CLAUDE.md` should not restate them, nor restate any
guidance the plugin already delivers. What belongs there is what only that project knows: its
architecture, its domain concepts, its build and release entry points.

### Ignore OS and editor cruft in the committed `.gitignore`

Not in `.git/info/exclude` or a personal `core.excludesfile`. Those are not shared on clone, so
they look like coverage to whoever set them up while giving none to anyone else. This is not
cosmetic: hatchling reads only `.gitignore` when selecting files to package, so a `.DS_Store`
inside the package directory that is ignored only locally gets published inside the wheel.

## Python Projects

See [python-tooling.md](../python-tooling.md) for the build backend, the mise and uv configuration,
and the task set.

## CLI Projects

Consider providing:
- `asciinema` demo
- auto-generated `clidocs`/`clidocs-check` tasks for CLI documentation
- Provide preflight checks wherever applicable and troubleshooting instructions with the specific commands that need to be executed to fix the problem.

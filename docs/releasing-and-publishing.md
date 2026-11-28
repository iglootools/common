# Releasing and Publishing

The plugin, the `iglootools` command and the shared workflows are released
together, under one version, and every other iglootools project pins that
release. This covers changing what they pin without breaking them, and cutting
the release.

<!-- toc -->
**On this page**

- [Changing what other repositories pin](#changing-what-other-repositories-pin)
- [The plugin](#the-plugin)
- [The `iglootools` command](#the-iglootools-command)
- [The shared workflows](#the-shared-workflows)
- [The version is the pin](#the-version-is-the-pin)
- [Releasing](#releasing)
  - [By hand](#by-hand)
<!-- tocstop -->

## Changing what other repositories pin

The plugin, the `iglootools` command and the shared workflows are consumed by
every other iglootools project, each pinned to a release. A change to one is a
change to an interface.

## The plugin

Try a change by loading the plugin from the working tree, as
[setup-development-environment.md](setup-development-environment.md#loading-the-plugin-from-the-working-tree)
describes. Keep it in step with the guidelines. The hook emits every directory's
index on its own, and `mise run lint-guideline-indexes` fails on a guideline
missing from its index, but renaming or moving a guideline file still leaves
`agents/auditor.md` or the audit skills pointing at something that is no longer
there, and a reference that fails to resolve fails silently, which is the
failure mode this repository exists to prevent. They spell the paths out from
the plugin root (`${CLAUDE_PLUGIN_ROOT}/guidelines/coding/git.md`), so search
them for the old path. The hook is runnable, which is the cheapest check of what
a session starts with:

```bash
CLAUDE_PLUGIN_ROOT="$PWD" CLAUDE_PROJECT_DIR="$PWD" bash hooks/load-guideline-indexes.sh
```

It prints a loud `ERROR:` line per file it cannot read rather than falling
silent.

## The `iglootools` command

Like the shared workflows, it is an interface other repositories pin: its
command and option names, the `[tool.iglootools]` settings and their defaults,
and the markers and headers it writes into generated files. Renaming any of them
breaks every project still on the old pin, and a changed marker rewrites their
generated documents. Change them deliberately, and document the consumer side in
`guidelines/project-setup/iglootools-cli.md` in the same change.

Core modules return data and raise errors with a kind; only the `cli` modules
print, and the import-linter contracts in `pyproject.toml` hold that. Before
merging a change, run it against a consumer from this checkout, as the guideline
describes:

```bash
cd ../nbkp && uv run --no-sync --with-editable ../common iglootools docs depgraph --check
```

## The shared workflows

The `.github/workflows/reusable-*.yml` workflows are consumed by the other
iglootools repositories, which pin them by commit SHA. Each is therefore an
interface: changing its inputs, or what a caller has to declare for it to work,
breaks every caller that has not been updated. Document the consumer side in
`guidelines/project-setup/shared-workflows.md` in the same change, and remember
that consumers do not move until someone repoints their pin.

`check-links.yml` and `renovate-mise-lock.yml` here call theirs through a local
path ref, so this repository exercises them as changed rather than as last
released. Use that: dispatch the link checker on the branch
(`gh workflow run check-links.yml --ref <branch>`) before merging a change to
it.

## The version is the pin

Because the pin is the version string,
**a release that does not bump it reaches nobody**. Claude Code sees the same
version and keeps the cached copy, with no error. Use `claude plugin tag` rather
than tagging by hand, since it refuses to create a tag that already exists and
so turns a forgotten bump into a failure instead of silence.

## Releasing

Cut a release, then move every project to it, from common's checkout. Set the
version once and paste the rest:

```bash
VERSION=1.34.0                     # the release to cut

cd ~/Workspace/iglootools/common
uv run --no-sync iglootools preflight                          # git, a GitHub token, mise, claude
uv run --no-sync iglootools common release "$VERSION" -n       # the plan, changing nothing
uv run --no-sync iglootools common release "$VERSION"
uv run --no-sync iglootools workspace adopt-common "$VERSION" -n  # every project: checks and plan
uv run --no-sync iglootools workspace adopt-common "$VERSION"
```

- **`common release`** opens the pull request bumping
  `.claude-plugin/plugin.json`, merges it once every check has passed, then tags
  the merge commit both ways and checks the two tags name it. It plans from what
  GitHub already has, so rerunning it after an interruption finishes the
  release, and rerunning it on a finished release changes nothing.
- **`--latest`** adopts the newest release, in place of a version, with either
  command: `iglootools workspace adopt-common --latest`.
- **`workspace adopt-common`** takes every iglootools project checked out in the
  [workspace](setup-development-environment.md#the-iglootools-workspace) that
  pins common, and fails if a repository of the organization pins common without
  a checkout there. It checks that every project's origin is reachable before
  changing any, then adopts them in parallel, each in a temporary worktree, so
  the checkouts are left to whoever works in them: each moves every pin on
  common (the reusable workflows to the release's commit, the `iglootools`
  command, the Renovate presets), regenerates `uv.lock`, and merges its pull
  request once green, deleting the branch. It then fast-forwards each checkout's
  default branch where that is safe, or says why it did not;
  `--skip-fast-forward` leaves them as they are, and `--keep-worktree` keeps the
  worktree of a project whose steps failed, to inspect. It moves the workspace's
  own `iglootools` to the release as well. Then it updates the Claude Code
  plugin installed for each project on the release whose `.claude/settings.json`
  enables it, since the repository and the plugin a session loads would
  otherwise disagree until someone ran
  [the update](installation.md#updating-every-project); `--skip-plugin` leaves
  the plugin as it is. It runs from common's own environment, so the release
  being adopted needs no install in the projects. Rerunning it picks up each
  project where it stopped; `--only` and `--exclude` narrow it.
  `repo adopt-common` does the same for one project, from its checkout;
  `--in-place` makes it work in the checkout itself, for a branch you mean to
  finish by hand.

Renovate would open the adopt pull requests on its own, since the shared preset
exempts common's releases from the release-age hold; adopt-common does it at
once, and reports what merged.

### By hand

From a clean working tree on `main`, with `version` already bumped in
`.claude-plugin/plugin.json` through a merged pull request:

```bash
claude plugin validate .
claude plugin tag --push -m "Release %s"
git tag -a v<version> -m "Release <version>" 'iglootools--v<version>^{}'
git push origin v<version>
```

Each release carries two tags at the same commit: `iglootools--v<version>`,
which `claude plugin tag` creates and the plugin installs by, and a plain
`v<version>`, which projects pin the shared workflows, the Renovate presets and
the `iglootools` command by. The plain tag exists because Renovate resolves
ordinary version tags, not the prefixed spelling; without it no project gets an
update pull request for the release.

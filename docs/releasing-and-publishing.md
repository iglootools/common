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
- [Propagating a release](#propagating-a-release)
<!-- tocstop -->

## Changing what other repositories pin

The plugin, the `iglootools` command and the shared workflows are consumed by
every other iglootools project, each pinned to a release. A change to one is a
change to an interface.

## The plugin

Try a change by loading the plugin from the working tree, as
[setup-development-environment.md](setup-development-environment.md#loading-the-plugin-from-the-working-tree)
describes. Keep it in step with the guidelines. Renaming or moving a guideline
file, changing which files trigger it, or adding a new one leaves
`skills/guidelines/SKILL.md`, `hooks/load-always-on-guidelines.sh`,
`agents/auditor.md` or the audit skills pointing at something that is no longer
there — and a dispatch table that fails to fire fails silently, which is the
failure mode this repository exists to prevent. All of them spell the paths out
from the plugin root (`${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/ide.md`,
`$plugin_root/guidelines/coding/general.md`), so no amount of moving files is
picked up for you. The hook is runnable, which is the cheapest check:

```bash
CLAUDE_PLUGIN_ROOT="$PWD" CLAUDE_PROJECT_DIR="$PWD" bash hooks/load-always-on-guidelines.sh
```

It prints a loud `ERROR:` line per file it cannot read rather than falling
silent, so an empty error count means every always-on path still resolves.

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

From a clean working tree on `main`, with `version` already bumped in
`.claude-plugin/plugin.json`:

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

## Propagating a release

Each project moves to the release through a pull request that
`iglootools common adopt` opens and merges once its checks pass. It moves every
pin on common: the reusable workflows to the release's commit, the `iglootools`
command, the Renovate presets and `IGLOOTOOLS_VERSION`, and regenerates
`uv.lock` where there is one. Run it from each project's checkout, with
`-n` first to see the pins it would move:

```bash
for repo in ~/Workspace/iglootools/{nbkp,photree,network-infra,alberta-hiking-resources}; do
  (cd "$repo" && uvx --from git+https://github.com/iglootools/common@v<version> \
    iglootools common adopt <version>)
done
```

uvx runs the release being adopted, in an environment of its own, so the loop
works in projects with and without Python alike.

Renovate would open the same pull requests without the release-age hold, which
the shared preset lifts for common's own releases; the command does it at once,
and reports what merged.

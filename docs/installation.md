# Installation

How an iglootools project installs the Claude Code plugin that delivers the
guidelines, and moves it to a new release.
**No clone of this repository is required**, and no project needs to sit in a
sibling directory. How the plugin works once installed is in
[internals.md](internals.md).

<!-- toc -->
**On this page**

- [Install it per project, not per user](#install-it-per-project-not-per-user)
- [Pinned versions](#pinned-versions)
- [Updating one project](#updating-one-project)
- [Updating every project](#updating-every-project)
<!-- tocstop -->

## Install it per project, not per user

These rules are for iglootools projects. Installing the plugin at **user scope**
would surface them in every repository on the machine, including ones this
repository has no business governing. Install at **project scope** instead, so a
repository opts in by committing the decision:

```bash
claude plugin marketplace add iglootools/common
claude plugin install iglootools@iglootools-plugins --scope project
```

Both commands are needed on each machine. `marketplace add` registers the
catalog in *your user* settings, and the install writes `enabledPlugins` into
the project's `.claude/settings.json`. A project that declares the marketplace
in `extraKnownMarketplaces` does not spare a collaborator the `marketplace add`:
without it the install fails with
`Plugin "iglootools" not found in marketplace "iglootools-plugins"`.

Commit `extraKnownMarketplaces` alongside `enabledPlugins` anyway, so the
marketplace is declared by the repository rather than only by whoever installed
it first. Committing both is what scopes the skills to this repository:
membership in the `iglootools` GitHub org is not something Claude Code can
check, so the opt-in is explicit and committed.

```json
{
  "extraKnownMarketplaces": {
    "iglootools-plugins": {
      "source": { "source": "github", "repo": "iglootools/common" }
    }
  },
  "enabledPlugins": {
    "iglootools@iglootools-plugins": true
  }
}
```

Committing those keys is enough to register the marketplace for a collaborator
who trusts the folder, but it does not install the plugin for them: a plugin
from an external source that only the project's settings enable stays
uninstalled until each person runs the `claude plugin install` line above.
Claude Code reports it as not installed and prints that command, so the gap is
visible rather than silent.

## Pinned versions

`.claude-plugin/plugin.json` declares an explicit `version`, and a plugin with
one is pinned to that string: an install stays on the version it has until the
string changes *and* someone runs the update below. Nothing arrives on its own.
Do not turn on auto-update for the marketplace — the version pin is what makes a
guideline change land deliberately rather than mid-task.

## Updating one project

Adopting a release with `iglootools common adopt` or `adopt-all` already does
this for each project that enables the plugin, once the project is on the
release, as
[releasing-and-publishing.md](releasing-and-publishing.md#releasing)
describes. Run it by hand to update without adopting:

```bash
claude plugin marketplace update iglootools-plugins
claude plugin update iglootools@iglootools-plugins --scope project
```

Then restart Claude Code, or run `/reload-plugins`, to apply it.

Both arguments matter. The bare plugin name is looked up at user scope and
reports `Plugin "iglootools" not found`.

## Updating every project

The download is shared: every project points at one
`~/.claude/plugins/cache/iglootools-plugins/iglootools/<version>`, and a version
is fetched once per machine. What is per project is the *pointer* to it, which
is the pin doing its job — one repository can sit on an older version while
another moves ahead.

There is no global switch. `iglootools workspace sync` moves every project of
the [workspace](setup-development-environment.md#the-iglootools-workspace)
together, along with the other plugins each enables: it adds the marketplace
on a machine that lacks it, installs the plugin in a project with no install
of its own, and updates it everywhere else, at project scope. It also brings
each checkout up to date with GitHub; to update the plugin alone, the loop
does it by hand:

```bash
claude plugin marketplace update iglootools-plugins
for repo in ~/Workspace/iglootools/*/; do
  grep -qs 'iglootools@iglootools-plugins' "$repo/.claude/settings.json" || continue
  (cd "$repo" && claude plugin update iglootools@iglootools-plugins --scope project)
done
```

The `grep` guard reads each repository's committed `.claude/settings.json`, so
the loop skips checkouts that do not enable the plugin and can be pointed at a
whole workspace. Every repository it does touch prints either
`updated from <old> to <new>` or `already at the latest version`, so the run is
its own check that nothing was left behind — the silent case, a repository
quietly left on an old version, is the one this loop exists to remove.

A `--scope user` install would update everywhere at once, but it also enables
the skills in every repository on the machine, which is what
[installing per project](#install-it-per-project-not-per-user) exists to avoid.

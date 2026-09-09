# common-guidelines

Shared coding guidelines for [iglootools](https://github.com/iglootools) projects.

## Contents

The rules themselves live in [**`guidelines/`**](guidelines/), one file per area a change can
reach. They split by how they are delivered rather than by subject — two govern every edit and
are in context from the start of a session, the rest are read only when a change reaches the
files they govern:

| Always on | |
|---|---|
| [`coding.md`](guidelines/coding.md) | language-agnostic coding principles |
| [`python.md`](guidelines/python.md) | Python-specific coding guidelines, wherever the project has a `pyproject.toml` |

| Read when a change reaches it | Triggered by |
|---|---|
| [`python-tooling.md`](guidelines/python-tooling.md) | uv, mise, hatchling, and the mise task set |
| [`project-setup/workflows.md`](guidelines/project-setup/workflows.md) | `.github/workflows/**` |
| [`project-setup/shared-workflows.md`](guidelines/project-setup/shared-workflows.md) | adding or changing a caller of a workflow this repository hosts |
| [`project-setup/dependency-automation.md`](guidelines/project-setup/dependency-automation.md) | `renovate.json`, `dependabot.yml`, and the repository settings both depend on |
| [`project-setup/repository.md`](guidelines/project-setup/repository.md) | `.gitignore`, setting up a new repository |
| [`project-setup/ide.md`](guidelines/project-setup/ide.md) | `.vscode/**`, `*.code-workspace`, `[tool.pyright]` |
| [`project-setup/claude-code.md`](guidelines/project-setup/claude-code.md) | `.claude/settings.json` |

`project-setup/` is one file per trigger deliberately: it was a single 501-line file, so a change
to a workflow pulled the Renovate rules and the editor settings into context along with it.

[Usage with Claude Code](#usage-with-claude-code) covers the two mechanisms that make that split
work. The rest of the repository supports the guidelines rather than stating any:

- [philosophy.md](philosophy.md) — the reasoning behind the guidelines
- [skills/](skills/) — the Claude Code skill that routes an agent to whichever guideline governs
  the edit it is about to make. It restates no guidance of its own.
- [hooks/](hooks/) — the `SessionStart` hook that loads the always-on guidelines into every
  session.
- [scripts/](scripts/) — reference implementations to copy into a project, for the few cases where
  a guideline is easier to ship as working code than to describe. The guideline that motivates each
  one links to it, and explains why every line is there.

## Applying these guidelines

These are defaults, not dogma. A project or module is free to deviate from any rule here, or to
add rules of its own, where there is good reason to — a performance constraint, an ecosystem
convention, a third-party library limitation, a platform or version still supported —
**provided the deviation and the reasoning behind it are documented**: project-wide ones in the
project's `docs/guidelines.md`, local ones in a comment at the point of deviation.

Divergence for a good, documented reason is fine. Drift without one is not.

**A major reason to write the rationale down is so the exception can be re-evaluated later.**
Almost every exception answers a condition that is true at the time: a library that lacks a
feature, a performance constraint, an ecosystem convention, a platform or version still
supported. Those conditions expire. When the library ships the feature, the bottleneck moves, or
the version is dropped, a documented exception can be revisited and removed — an undocumented
one silently becomes permanent, because nobody is left who remembers what it was working
around. Undocumented exceptions are how a codebase accumulates rules that everyone follows and
no one can explain.

So where the exception depends on a condition, **name the condition that would make it
unnecessary**, not just the reason it exists today. "Revisit when X supports Y" or "drop this
once we no longer support Z" gives the exception an expiry criterion someone can actually check,
instead of leaving a future reader to guess whether the justification still holds. The
[Python version policy](guidelines/python.md#python-version-policy) is the shape to copy: it records the
constraint, what it costs, and the specific event that would retire it.

**Where to document an exception** — put it where a reader will hit it, not in a separate log:

- **Project-wide deviations** go in the project's `docs/guidelines.md`, stated against the rule
  they override.
- **Local or config-level deviations** go in a comment at the point of deviation — a
  `[tool.ruff.lint] ignore` entry paired with the design decision that motivates it, a `# noqa`
  with its reason beside it, a comment above the constraint in `pyproject.toml`.

**The bar is a rationale a reviewer would accept**, not merely a note that the deviation exists.
"We ignore this rule" is drift. "We ignore this rule because X, and here is what we do instead"
is an exception. If the reason is "we have not gotten around to it", that is debt to track, not
an exception to document.

This applies to [philosophy.md](philosophy.md) as much as to the concrete rules, and is easier
to neglect there: nothing fails when a principle is quietly dropped, whereas a rule at least has
a file to be missing from. A project may reach a different conclusion about layering, error
handling or event sourcing than the one argued there — the same standard covers it.

The same standard applies between projects: two iglootools projects may legitimately differ, but
the difference should be traceable to a decision someone made, not to one of them having quietly
fallen behind.

## Usage with Claude Code

Everything here is delivered by a single plugin. **No clone of this repository is required**, and
no project needs to sit in a sibling directory.

The guidelines split into two kinds, and the plugin delivers each by the mechanism that fits.
`coding.md` and `python.md` govern every edit, so a `SessionStart` hook puts them in context from
the start. The other three are triggered by a specific file, so a skill reads them only when a
change reaches the files they govern.

### The plugin

This repository is also a Claude Code plugin. It ships one skill, `guidelines`, which restates
no guideline: its body says which file to read and when, so the guidelines stay in one place,
readable by humans and agents alike. It does three things — dispatches to the guideline file a
change reaches, carries the pass to make before calling the change done, and walks the procedure
for recording a documented exception where a rule does not fit.

Guideline files are read on demand where possible: the skill reads only the one a change
actually reaches, and an ordinary code change reads none of them.

It also enforces the philosophy the guidelines rest on: check the work against them before
calling it done, and document a deviation rather than drift from a rule silently. See
[Applying these guidelines](#applying-these-guidelines).

### Install it per project, not per user

These rules are for iglootools projects. Installing the plugin at **user scope** would surface
them in every repository on the machine, including ones this repository has no business
governing. Install at **project scope** instead, so a repository opts in by committing the
decision:

```bash
claude plugin marketplace add iglootools/common-guidelines
claude plugin install iglootools@iglootools-plugins --scope project
```

Both commands are needed on each machine. `marketplace add` registers the catalog in *your user*
settings, and the install writes `enabledPlugins` into the project's `.claude/settings.json`. A
project that declares the marketplace in `extraKnownMarketplaces` does not spare a collaborator
the `marketplace add`: without it the install fails with `Plugin "iglootools" not found in
marketplace "iglootools-plugins"`.

Commit `extraKnownMarketplaces` alongside `enabledPlugins` anyway, so the marketplace is declared
by the repository rather than only by whoever installed it first. Committing both is what scopes
the skills to this repository: membership in the `iglootools` GitHub org is not something Claude
Code can check, so the opt-in is explicit and committed.

```json
{
  "extraKnownMarketplaces": {
    "iglootools-plugins": {
      "source": { "source": "github", "repo": "iglootools/common-guidelines" }
    }
  },
  "enabledPlugins": {
    "iglootools@iglootools-plugins": true
  }
}
```

Committing those keys is enough to register the marketplace for a collaborator who trusts the
folder, but it does not install the plugin for them: a plugin from an external source that only
the project's settings enable stays uninstalled until each person runs the `claude plugin install`
line above. Claude Code reports it as not installed and prints that command, so the gap is visible
rather than silent.

### Pinned versions

`.claude-plugin/plugin.json` declares an explicit `version`, and a plugin with one is pinned to
that string: an install stays on the version it has until the string changes *and* someone runs
the update below. Nothing arrives on its own. Do not turn on auto-update for the marketplace —
the version pin is what makes a guideline change land deliberately rather than mid-task.

Because the pin is the version string, **a release that does not bump it reaches nobody**.
Claude Code sees the same version and keeps the cached copy, with no error. Use `claude plugin
tag` rather than tagging by hand, since it refuses to create a tag that already exists and so
turns a forgotten bump into a failure instead of silence.

### Releasing

From a clean working tree on `main`, with `version` already bumped in
`.claude-plugin/plugin.json`:

```bash
claude plugin validate .
claude plugin tag --push -m "Release %s"

# Mirror it as a plain version tag, for the reusable workflow's consumers.
version="$(python3 -c 'import json;print(json.load(open(".claude-plugin/plugin.json"))["version"])')"
git tag -a "v${version}" -m "Release ${version} (git ref tag mirroring iglootools--v${version})"
git push origin "refs/tags/v${version}"
```

The first command creates and pushes `iglootools--v<version>`, after checking that `plugin.json`
and the marketplace entry agree. `--dry-run` shows the tag without creating it. The marketplace
entry deliberately carries no `version` of its own: when both are set, `plugin.json` wins
silently and the entry becomes a place for a stale number to hide.

**Both tags, or the release is half-published.** The plugin is installed by version and needs
only the prefixed tag, but the other iglootools repositories pin
[the shared link checker](guidelines/project-setup/shared-workflows.md#call-the-shared-link-checker-instead-of-copying-it)
by commit SHA and read the plain `v<version>` tag to find it — Renovate resolves ordinary
version tags and not the prefixed spelling. Skipping the mirror does not break anything that is
already running, which is the problem: consumers simply never learn a new version exists, and
nothing fails to say so. The two tags must land on the same commit, so create them together
rather than remembering the second one later.

### Updating one project

```bash
claude plugin marketplace update iglootools-plugins
claude plugin update iglootools@iglootools-plugins --scope project
```

Then restart Claude Code, or run `/reload-plugins`, to apply it.

Both arguments matter. The bare plugin name is looked up at user scope and reports
`Plugin "iglootools" not found`.

### Updating every project

The download is shared: every project points at one
`~/.claude/plugins/cache/iglootools-plugins/iglootools/<version>`, and a version is fetched once
per machine. What is per project is the *pointer* to it, which is the pin doing its job — one
repository can sit on an older version while another moves ahead.

There is no global switch, so moving them together is a loop. Point it at wherever the iglootools
repositories are checked out:

```bash
claude plugin marketplace update iglootools-plugins
for repo in ~/Workspace/iglootools/*/; do
  grep -qs 'iglootools@iglootools-plugins' "$repo/.claude/settings.json" || continue
  (cd "$repo" && claude plugin update iglootools@iglootools-plugins --scope project)
done
```

The `grep` guard reads each repository's committed `.claude/settings.json`, so the loop skips
checkouts that do not enable the plugin and can be pointed at a whole workspace. Every repository
it does touch prints either `updated from <old> to <new>` or `already at the latest version`, so
the run is its own check that nothing was left behind — the silent case, a repository quietly
left on an old version, is the one this loop exists to remove.

A `--scope user` install would update everywhere at once, but it also enables the skills in every
repository on the machine, which is what
[installing per project](#install-it-per-project-not-per-user) exists to avoid.

### The ones that load in every session

Some guidelines govern every edit rather than one kind of file — `coding.md` and `python.md`
today. Those are not skills: a skill is model-invoked, which is right for a guideline triggered
by a file and wrong for one that applies to everything. They are delivered instead by
[hooks/load-always-on-guidelines.sh](hooks/load-always-on-guidelines.sh), which runs on
`SessionStart` and whose stdout becomes context the agent sees. Another such guideline is added
to that script.

The hook fires on `startup`, `clear` and `compact`, and deliberately not on `resume` or `fork`: a
resumed or forked session still carries the earlier injection in its transcript, while a compacted
one may have had it summarized away.

Emission can be conditional: `python.md` goes out only when the project has a `pyproject.toml`,
so a project with no Python does not pay for it. If a file cannot be read, the hook says so in
the injected text rather than emitting nothing, because a guideline that failed to load must not
be indistinguishable from one that does not apply.

### Working on the guidelines themselves

This repository does not consume its own plugin: `${CLAUDE_PLUGIN_ROOT}` would resolve to the
installed copy rather than the file being edited. Its [CLAUDE.md](CLAUDE.md) imports
`coding.md` and `python.md` directly instead, which needs no plugin at all.

To work on the plugin, load it from the working tree without installing it, which is what makes
`${CLAUDE_PLUGIN_ROOT}` resolve here:

```bash
claude --plugin-dir .
```

Edits to a `SKILL.md` take effect immediately; changes to `.claude-plugin/` need
`/reload-plugins`. Validate the manifests with:

```bash
claude plugin validate .
```

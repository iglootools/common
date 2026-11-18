# Contributing

This repository is the source of the shared iglootools guidelines, not a consumer of them, so its
documentation is shaped differently from a project's: there is no `docs/` directory, and the
guidelines themselves are the reference.

<!-- toc -->
**On this page**

- [Getting started](#getting-started)
- [Guidelines](#guidelines)
- [The `iglootools` command](#the-iglootools-command)
- [Working on what other repositories pin](#working-on-what-other-repositories-pin)
  - [The plugin](#the-plugin)
  - [The `iglootools` command](#the-iglootools-command-1)
  - [The shared workflows](#the-shared-workflows)
- [Understanding the repository](#understanding-the-repository)
- [Reference](#reference)
- [Repository settings](#repository-settings)
<!-- tocstop -->

## Getting started

Install [mise](https://mise.jdx.dev/), then run `mise install` in the repository. It installs
the pinned Python and uv, and the first `mise run` creates `.venv` with the dev dependencies.
`mise run check-all` runs every check and test, which is what the `test` workflow runs on each
pull request; `mise tasks` lists the rest.

- [Working on what other repositories pin](#working-on-what-other-repositories-pin) — loading the
  plugin from the working tree, validating it, and running the `SessionStart` hook by hand
- [README.md#usage-with-claude-code](README.md#usage-with-claude-code) — how the skill and the hook
  deliver the guidelines, and working on them

## Guidelines

Edits here follow [guidelines/coding/general.md](guidelines/coding/general.md),
[guidelines/coding/python.md](guidelines/coding/python.md) and
[guidelines/coding/git.md](guidelines/coding/git.md), like any other iglootools project.
[README.md#applying-these-guidelines](README.md#applying-these-guidelines) is the bar a documented
exception has to meet.

Each guideline file, `philosophy.md`, `README.md` and this file open with a table of contents
between `<!-- toc -->` and `<!-- tocstop -->`. Do not edit it by hand: after adding, renaming or
removing a `##` or `###` heading, run `mise run toc` to regenerate every list.
`mise run toc-check`, part of `check`, fails on a list that is out of date. To give a new file
one, run `mise run toc --add <file>`.

The script's tests are in `tests/` and run with `mise run test`. The expected anchors in them
come from [github-slugger](https://github.com/Flet/github-slugger), which reproduces GitHub's
rules: when a heading's anchor seems wrong, compare against it again rather than editing the
expected values.

## The `iglootools` command

The shared command lives in `src/iglootools/`, one package per domain (`docs`, `python`,
`demo`, `mise`, `shell`), each with a `cli` module that is the only place it prints. Its tests
are under `tests/`. How projects install, configure and pin it, and how to try a change against
one of them before releasing, is in
[guidelines/project-setup/iglootools-cli.md](guidelines/project-setup/iglootools-cli.md).

## Working on what other repositories pin

The plugin, the `iglootools` command and the shared workflows are consumed by every other
iglootools project, each pinned to a release. A change to one is a change to an interface.

### The plugin

This repository does not consume its own plugin: `${CLAUDE_PLUGIN_ROOT}` resolves to the
installed copy, so an agent here would be pointed at whatever commit was last installed rather
than at the files in front of it. Load it from the working tree instead, which is what makes
`${CLAUDE_PLUGIN_ROOT}` resolve here:

```bash
claude --plugin-dir .
claude plugin validate .
```

Keep it in step with the guidelines. Renaming or moving a guideline file, changing which files
trigger it, or adding a new one leaves `skills/guidelines/SKILL.md`,
`hooks/load-always-on-guidelines.sh`, `agents/auditor.md` or the audit skills pointing at
something that is no longer there — and a
dispatch table that fails to fire fails silently, which is the failure mode this repository
exists to prevent. All of them spell the paths out from the plugin root
(`${CLAUDE_PLUGIN_ROOT}/guidelines/project-setup/ide.md`, `$plugin_root/guidelines/coding/general.md`),
so no amount
of moving files is picked up for you. The hook is runnable, which is the cheapest check:

```bash
CLAUDE_PLUGIN_ROOT="$PWD" CLAUDE_PROJECT_DIR="$PWD" bash hooks/load-always-on-guidelines.sh
```

It prints a loud `ERROR:` line per file it cannot read rather than falling silent, so an empty
error count means every always-on path still resolves.

### The `iglootools` command

Like the shared workflows, it is an interface other repositories pin: its command and option
names, the `[tool.iglootools]` settings and their defaults, and the markers and headers it
writes into generated files. Renaming any of them breaks every project still on the old pin,
and a changed marker rewrites their generated documents. Change them deliberately, and document
the consumer side in `guidelines/project-setup/iglootools-cli.md` in the same change.

Core modules return data and raise errors with a kind; only the `cli` modules print, and the
import-linter contracts in `pyproject.toml` hold that. Before merging a change, run it against
a consumer from this checkout, as the guideline describes:

```bash
cd ../nbkp && uv run --no-sync --with-editable ../common iglootools docs depgraph --check
```

### The shared workflows

`.github/workflows/reusable-check-links.yml` is consumed by the other iglootools repositories,
which pin it by commit SHA. It is therefore an interface: changing its inputs, or what a caller
has to declare for it to work, breaks every caller that has not been updated. Document the
consumer side in `guidelines/project-setup/shared-workflows.md` in the same change, and remember
that consumers do not move
until someone repoints their pin.

`check-links.yml` here calls it through a local path ref, so this repository exercises the
workflow as changed rather than as last released. Use that: dispatch it on the branch
(`gh workflow run check-links.yml --ref <branch>`) before merging a change to it.

## Understanding the repository

- [README.md](README.md) — what is here, and which guideline is triggered by which file
- [philosophy.md](philosophy.md) — the reasoning behind the guidelines
- [guidelines/coding/README.md](guidelines/coding/README.md) and
  [guidelines/project-setup/README.md](guidelines/project-setup/README.md) — the index of each
  half of the guidelines

## Reference

- [guidelines/project-setup/shared-workflows.md](guidelines/project-setup/shared-workflows.md) —
  the reusable workflows this repository hosts, and what a caller must declare. Changing one is
  an interface change: see [The shared workflows](#the-shared-workflows).

## Repository settings

Configured as [repository.md](guidelines/project-setup/repository.md#protect-the-default-branch-and-release-tags)
describes. Two rulesets:

- **`main`** (default branch): no deletion or force-push, changes through a pull request merged
  with a merge commit, and the `test` check from `test.yml` must pass. `test` has to keep
  running on every pull request (no `paths` filter on its workflow), or a pull request it skips
  can never be merged. `integration_id` 15368 is GitHub Actions, which keeps a check with the
  same name from another app from satisfying the rule.
- **`release tags`** (`refs/tags/v*`, `refs/tags/iglootools--v*`): no deletion or update. Both
  prefixes are release tags — see [README.md#releasing](README.md#releasing).

Created with:

```bash
gh api --method POST repos/iglootools/common/rulesets --input - <<'JSON'
{
  "name": "main",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    { "type": "pull_request", "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": false,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false,
        "allowed_merge_methods": ["merge"] } },
    { "type": "required_status_checks", "parameters": {
        "strict_required_status_checks_policy": false,
        "do_not_enforce_on_create": false,
        "required_status_checks": [{ "context": "test", "integration_id": 15368 }] } }
  ]
}
JSON

gh api --method POST repos/iglootools/common/rulesets --input - <<'JSON'
{
  "name": "release tags",
  "target": "tag",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["refs/tags/v*", "refs/tags/iglootools--v*"], "exclude": [] } },
  "rules": [{ "type": "deletion" }, { "type": "update" }]
}
JSON
```

Verify with `gh api repos/iglootools/common/rules/branches/main -q '[.[].type]'`, which should
print `["deletion","non_fast_forward","pull_request","required_status_checks"]`.

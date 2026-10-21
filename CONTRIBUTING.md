# Contributing

This repository is the source of the shared iglootools guidelines, not a consumer of them, so its
documentation is shaped differently from a project's: there is no `docs/` directory, and the
guidelines themselves are the reference.

## Getting started

- [CLAUDE.md](CLAUDE.md) — loading the plugin from the working tree, validating it, and running
  the `SessionStart` hook by hand
- [README.md#usage-with-claude-code](README.md#usage-with-claude-code) — how the skill and the hook
  deliver the guidelines, and working on them

## Guidelines

Edits here follow [guidelines/coding/general.md](guidelines/coding/general.md) and
[guidelines/coding/python.md](guidelines/coding/python.md), like any other iglootools project.
[README.md#applying-these-guidelines](README.md#applying-these-guidelines) is the bar a documented
exception has to meet.

## Understanding the repository

- [README.md](README.md) — what is here, and which guideline is triggered by which file
- [philosophy.md](philosophy.md) — the reasoning behind the guidelines
- [guidelines/coding/README.md](guidelines/coding/README.md) and
  [guidelines/project-setup/README.md](guidelines/project-setup/README.md) — the index of each
  half of the guidelines

## Reference

- [guidelines/project-setup/shared-workflows.md](guidelines/project-setup/shared-workflows.md) —
  the reusable workflows this repository hosts, and what a caller must declare. Changing one is
  an interface change: see [CLAUDE.md](CLAUDE.md#working-on-the-shared-workflows).

## Repository settings

Configured as [repository.md](guidelines/project-setup/repository.md#protect-the-default-branch-and-release-tags)
describes. Two rulesets:

- **`main`** (default branch): no deletion or force-push, changes through a pull request merged
  with a merge commit. No `required_status_checks` rule: no workflow here runs on pull requests
  (`check-links.yml` is scheduled), so there is no check to require. Add one if a pull-request
  workflow is introduced.
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
        "allowed_merge_methods": ["merge"] } }
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
print `["deletion","non_fast_forward","pull_request"]`.

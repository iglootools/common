# Building and Testing

## Checks and tests

`mise run check-all` runs every check and test, which is what the `test`
workflow runs on each pull request; `mise tasks` lists the rest.

`mise run format` formats every file: ruff the Python, dprint the JSON, TOML and
YAML, rumdl the Markdown. `format-check` and `lint-markdown`, both part of
`check`, fail on a file it would change, so run it after editing anything. The
tools and their configuration are described in
[formatting.md](../guidelines/project-setup/formatting.md).

Each guideline file, `philosophy.md`, `README.md` and each file under `docs/`
open with a table of contents between `<!-- toc -->` and `<!-- tocstop -->`. Do
not edit it by hand: after adding, renaming or removing a `##` or `###` heading,
run `mise run toc` to regenerate every list. `mise run toc-check`, part of
`check`, fails on a list that is out of date. To give a new file one, run
`mise run toc --add <file>`.

The script's tests are in `tests/` and run with `mise run test`. The expected
anchors in them come from
[github-slugger](https://github.com/Flet/github-slugger), which reproduces
GitHub's rules: when a heading's anchor seems wrong, compare against it again
rather than editing the expected values.

## GitHub Config

Configured as
[repository.md](../guidelines/project-setup/repository.md#protect-the-default-branch-and-release-tags)
describes. Two rulesets:

- **`main`** (default branch): no deletion or force-push, changes through a pull
  request merged with a merge commit, and the `test` check from `test.yml` must
  pass. `test` has to keep running on every pull request (no `paths` filter on
  its workflow), or a pull request it skips can never be merged.
  `integration_id` 15368 is GitHub Actions, which keeps a check with the same
  name from another app from satisfying the rule.
- **`release tags`** (`refs/tags/v*`, `refs/tags/iglootools--v*`): no deletion
  or update. Both prefixes are release tags — see
  [releasing-and-publishing.md](releasing-and-publishing.md#releasing).

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

Verify with
`gh api repos/iglootools/common/rules/branches/main -q '[.[].type]'`, which
should print
`["deletion","non_fast_forward","pull_request","required_status_checks"]`.

# Repository Conventions

What every iglootools repository carries regardless of language, and where each project type
goes from here.

- Github build/test/release workflows — see [workflows.md](workflows.md)
- `git config user.email "<email>"` and `git config user.name "<name>"` in the project.
- A `CONTRIBUTING.md` indexing the project's documentation, and the rest of `docs/` — see [documentation.md](documentation.md)

### Ignore OS and editor cruft in the committed `.gitignore`

Not in `.git/info/exclude` or a personal `core.excludesfile`. Those are not shared on clone, so
they look like coverage to whoever set them up while giving none to anyone else. This is not
cosmetic: hatchling reads only `.gitignore` when selecting files to package, so a `.DS_Store`
inside the package directory that is ignored only locally gets published inside the wheel.

### Merge pull requests with a merge commit

Merge, do not squash or rebase, unless the project has a reason to do otherwise. A merge commit
keeps every commit of the branch and records where the branch joined `main`, so the history can
always be summarized later — `git log --first-parent` reads as one entry per pull request — while
a squash discards the individual steps for good (see "Preserve data, build tooling around it" in
[philosophy.md](../../philosophy.md#event-driven-append-only-replayable)). That only pays off if
the commits are worth keeping, which is what "one concern per commit" in
[Small, reviewable changes](../../philosophy.md#small-reviewable-changes) asks for.

The default-branch ruleset below enforces it (`allowed_merge_methods: ["merge"]`), so the choice
is made once per repository rather than per pull request. A project with a real reason to differ —
a branch whose commits are throwaway by design, say an automated update that lands as a
series of fix-ups — documents it in its `docs/guidelines.md` and adds the method to its
ruleset, rather than having maintainers pick per merge.

### Protect the default branch and release tags

Every repository carries two rulesets: one on the default branch, one on release tags. Branch
protection is the older mechanism; use rulesets, which cover tags as well and are readable
through the API.

**The default branch** — no deletion, no force-push, changes only through a pull request merged
with a merge commit, and the project's CI check green first:

```bash
gh api --method POST repos/<owner>/<repo>/rulesets --input - <<'EOF'
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
        "required_status_checks": [{ "context": "<check>", "integration_id": 15368 }] } }
  ]
}
EOF
```

- `~DEFAULT_BRANCH`, not `refs/heads/main`, so a rename does not leave the ruleset guarding a
  branch that no longer exists.
- `required_approving_review_count: 0`: the rule is that changes go through a pull request, where
  CI runs and the change is recorded — not that a second person approves, which a
  single-maintainer project cannot satisfy. Raise it when a project has more than one maintainer.
- `<check>` is the name of the CI job that runs on every pull request (`test` in the Python
  projects). It must run on *every* pull request: a workflow with `paths` filters never reports
  on a docs-only change, and the required check then blocks that pull request forever. A
  repository with no such job omits the `required_status_checks` rule and says so in its docs.
- `integration_id: 15368` is GitHub Actions, so a status reported under the same name by any other
  app does not satisfy the check.
- `strict_required_status_checks_policy: false`: requiring branches to be up to date with `main`
  makes every Renovate pull request rebase after each merge, for little safety in a repository
  where `main` is tested again on push.

**Release tags** — a published version must keep pointing at the commit it was published from:
the plugin installs by tag, consumers pin shared workflows by the commit a `v*` tag names, and
package versions are derived from tags.

```bash
gh api --method POST repos/<owner>/<repo>/rulesets --input - <<'EOF'
{
  "name": "release tags",
  "target": "tag",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["refs/tags/v*"], "exclude": [] } },
  "rules": [{ "type": "deletion" }, { "type": "update" }]
}
EOF
```

Creation stays allowed, which is what lets a release workflow push a new tag with
`GITHUB_TOKEN`. Add every tag prefix the project releases under (this repository also has
`refs/tags/iglootools--v*`).

**Verify the effect, not the configuration.** A ruleset can be `active` and govern nothing: an
empty `include` list matches no ref, and the UI shows it as enabled all the same. Ask GitHub which
rules actually apply:

```bash
gh api repos/<owner>/<repo>/rules/branches/main -q '[.[].type]'
# expect: ["deletion","non_fast_forward","pull_request","required_status_checks"]
```

For the tag ruleset there is no equivalent endpoint, so read its `conditions.ref_name.include`
back and check it is non-empty and names the project's tag prefixes.

**Record it in the project.** List the two rulesets, the project's `<check>`, and the commands
that created them with the project's other repository settings — see
[Record repository settings as commands in one place](documentation.md#record-repository-settings-as-commands-in-one-place) —
so the configuration can be re-applied and reviewed rather than living only in GitHub.

**Private repositories on a free plan cannot have rulesets.** GitHub offers them on private
repositories only with a paid plan. That is a documented exception in the project's
`docs/guidelines.md`, retired when the organization moves to a paid plan or the repository
becomes public.

### Inherit the code of conduct and security policy from the organization

The code of conduct and the security policy are the same for every iglootools repository, so they
live once, in the public [iglootools/.github](https://github.com/iglootools/.github) repository,
and GitHub applies them to every repository that has no file of its own:

- `CODE_OF_CONDUCT.md` — the [Contributor Covenant](https://www.contributor-covenant.org/) 3.0,
  with the reporting contact filled in and its recommended enforcement ladder adopted unchanged.
- `SECURITY.md` — report vulnerabilities privately, through GitHub's private vulnerability
  reporting.

Do not copy either file into a project. A copy overrides the organization's file for that
repository, so a later change to the shared one silently stops reaching it. Link to them instead
from the project's `CONTRIBUTING.md`.

`SECURITY.md` only promises a channel that has to be switched on per repository. Private
vulnerability reporting is off by default, so without this call the Security tab offers reporters
nothing to click, while the policy tells them to use it:

```bash
gh api --method PUT repos/<owner>/<repo>/private-vulnerability-reporting
gh api repos/<owner>/<repo>/private-vulnerability-reporting -q .enabled   # expect true
```

It is available on public repositories only; a private one falls back to the email address in
`SECURITY.md`. Check that a repository picks up the organization's files with
`gh api repos/<owner>/<repo>/community/profile -q .files.code_of_conduct_file.html_url`, which
should name `iglootools/.github`.

## Python Projects

See [python-tooling.md](python-tooling.md) for the build backend, the mise and uv configuration,
and the task set, and [pypi-publishing.md](pypi-publishing.md) for releasing to PyPI.

## CLI Projects

Consider providing:
- an asciinema demo: a scripted, seeded session recorded by mise tasks and CI and embedded in the
  README — see [cli-demo.md](cli-demo.md)
- a generated CLI reference with `clidocs`/`clidocs-check` tasks — see
  [Generate references from the code](documentation.md#generate-references-from-the-code-and-check-them)
- Provide preflight checks wherever applicable and troubleshooting instructions with the specific commands that need to be executed to fix the problem.

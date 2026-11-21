# Repository Conventions

What every iglootools repository carries regardless of language: the committed
`.gitignore`, the merge method, the rulesets on the default branch and release
tags, and the organization's code of conduct and security policy. Read it when
creating a repository, editing `.gitignore`, or changing a ruleset or a
repository setting. Each setting is recorded as a command in the project's docs,
as
[layout.md › Record repository settings as commands in one place](../documentation/layout.md#record-repository-settings-as-commands-in-one-place)
describes.

<!-- toc -->
**On this page**

- [Ignore OS and editor cruft, and generated iglootools output, in the committed `.gitignore`](#ignore-os-and-editor-cruft-and-generated-iglootools-output-in-the-committed-gitignore)
- [Merge pull requests with a merge commit](#merge-pull-requests-with-a-merge-commit)
- [Protect the default branch and release tags](#protect-the-default-branch-and-release-tags)
- [Inherit the code of conduct and security policy from the organization](#inherit-the-code-of-conduct-and-security-policy-from-the-organization)
<!-- tocstop -->

## Ignore OS and editor cruft, and generated iglootools output, in the committed `.gitignore`

List them in the committed `.gitignore`, not in `.git/info/exclude` or a
personal `core.excludesfile`.

**Why:** those are not shared on clone, so they cover whoever set them up and
nobody else. hatchling reads only `.gitignore` when selecting files to package,
so a `.DS_Store` ignored only locally gets published inside the wheel.

- List `.iglootools/` too. It is the one directory iglootools tools and the
  plugin write generated output to, such as the audit reports under
  `.iglootools/audits/` ([audit.md](../review/audit.md#the-report)). Ignored as
  a whole, it needs no new entry for a new kind of output.
- Nothing in `.iglootools/` is ever committed. A file a project should commit,
  such as a tool's settings, belongs somewhere else, so the directory never
  mixes generated and committed files.

## Merge pull requests with a merge commit

The default-branch ruleset allows only merge commits
(`allowed_merge_methods: ["merge"]`). The reasons are in
[git.md › Merge with a merge commit, not a squash or a rebase](../coding/git.md#merge-with-a-merge-commit-not-a-squash-or-a-rebase).

**Why:** set on the ruleset, the choice is made once per repository rather than
by whoever merges each pull request.

- A project with a real reason to differ, such as a branch whose commits are
  throwaway by design, documents it in its `docs/guidelines.md` and adds the
  method to its ruleset.

## Protect the default branch and release tags

Every repository carries two rulesets: one on the default branch, one on release
tags. Use rulesets, not branch protection.

**Why:** a change reaches `main` only through a green pull request, and a
published version keeps pointing at the commit it was published from: the plugin
installs by tag, consumers pin shared workflows by the commit a `v*` tag names,
and package versions are derived from tags. Rulesets cover tags as well as
branches and are readable through the API.

**The default branch**: no deletion, no force-push, changes only through a pull
request merged with a merge commit, and the `preflight` job green first.
Common's [GitHub Config](../../docs/building-and-testing.md#github-config)
applies it, and shows how to verify it.

- `~DEFAULT_BRANCH`, not `refs/heads/main`, so a rename does not leave the
  ruleset guarding a branch that no longer exists.
- `required_approving_review_count: 0`: the rule is that changes go through a
  pull request, where CI runs and the change is recorded, not that a second
  person approves, which a single-maintainer project cannot satisfy. Raise it
  when a project has more than one maintainer.
- `preflight` is the job that runs `ci-preflight`, named after its task
  ([workflows.md](workflows.md#name-each-job-after-the-task-it-runs-without-ci-)).
  It must run on every pull request: a workflow with `paths` filters never
  reports on a docs-only change, and the required check then blocks it forever.
  A repository with no such job omits the `required_status_checks` rule and says
  so in its docs.
- `integration_id: 15368` is GitHub Actions, so a status of the same name from
  any other app does not satisfy the check.
- `strict_required_status_checks_policy: false`: requiring branches to be up to
  date makes every Renovate pull request rebase after each merge, for little
  safety where `main` is tested again on push.
- **Rename a required job in this order**: open the pull request that renames
  it, let its CI pass under the new name, then point the ruleset at the new name
  and merge. Switched earlier, the ruleset waits on a check the renamed job
  never reports; switched later, `main` requires a check nothing reports. Other
  open pull requests wait until they are rebased. Update the ruleset's JSON in
  the project's docs in the same pull request, and switch the live ruleset with:

  ```bash
  id=$(gh api repos/<owner>/<repo>/rulesets -q '.[] | select(.name=="main") | .id')
  gh api "repos/<owner>/<repo>/rulesets/$id" \
    | jq '{name, target, enforcement, conditions, bypass_actors, rules: [.rules[]
          | if .type == "required_status_checks"
            then .parameters.required_status_checks[0].context = "<new check>"
            else . end]}' \
    | gh api --method PUT "repos/<owner>/<repo>/rulesets/$id" --input -
  ```

**Release tags**: no deletion and no update.

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

- Creation stays allowed, which is what lets a release workflow push a new tag
  with `GITHUB_TOKEN`.
- Add every tag prefix the project releases under (this repository also has
  `refs/tags/iglootools--v*`).

**Verify the effect, not the configuration.** A ruleset can be `active` and
govern nothing: an empty `include` list matches no ref, and the UI shows it as
enabled all the same. Ask GitHub which rules apply:

```bash
gh api repos/<owner>/<repo>/rules/branches/main -q '[.[].type]'
# expect: ["deletion","non_fast_forward","pull_request","required_status_checks"]
```

There is no equivalent endpoint for tags, so read the tag ruleset's
`conditions.ref_name.include` back and check it names the project's tag
prefixes.

**Private repositories on a free plan cannot have rulesets.** GitHub offers them
on private repositories only with a paid plan. Record that as a documented
exception in the project's `docs/guidelines.md`, retired when the organization
moves to a paid plan or the repository becomes public.

## Inherit the code of conduct and security policy from the organization

The code of conduct and the security policy live once, in the public
[iglootools/.github](https://github.com/iglootools/.github) repository, and
GitHub applies them to every repository with no file of its own. Do not copy
either into a project; link to them from its `CONTRIBUTING.md`.

**Why:** a copy overrides the organization's file for that repository, so a
later change to the shared one silently stops reaching it.

- `CODE_OF_CONDUCT.md` is the
  [Contributor Covenant](https://www.contributor-covenant.org/) 3.0, with the
  reporting contact filled in and its recommended enforcement ladder adopted
  unchanged.
- `SECURITY.md` asks for vulnerabilities to be reported privately, through
  GitHub's private vulnerability reporting.
- Turn that reporting on in every public repository. It is off by default, and
  without it the Security tab offers reporters nothing to click while the policy
  tells them to use it. A private repository cannot have it, and falls back to
  the email address in `SECURITY.md`:

  ```bash
  gh api --method PUT repos/<owner>/<repo>/private-vulnerability-reporting
  gh api repos/<owner>/<repo>/private-vulnerability-reporting -q .enabled   # expect true
  ```

- Check that a repository picks up the organization's files: this should name
  `iglootools/.github`:

  ```bash
  gh api repos/<owner>/<repo>/community/profile -q .files.code_of_conduct_file.html_url
  ```

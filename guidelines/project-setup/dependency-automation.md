# Dependency Automation Guidelines

How Renovate and Dependabot divide the work, and the repository settings both depend on.
The workflow that regenerates `mise.lock` on Renovate branches is in
[shared-workflows.md](shared-workflows.md).

- `renovate.json`: group all dependency updates into a single PR, delay
  updates by 14 days (`minimumReleaseAge`) to avoid adopting broken
  releases and limit risk of supply chain attacks

### Committing `renovate.json` does not turn Renovate on

The config is inert until the Renovate GitHub App is granted access to the repository, and
nothing in the repository can tell you whether that happened. There is no error, no failed check
and no log — the pins simply never move, which looks exactly like having nothing to update.

**The tell is the Dependency Dashboard issue.** With `dependencyDashboard: true`, Renovate opens
one on its first run, so its absence means it has never run:

```bash
gh issue list --repo <owner>/<repo> --state all --search "Dependency Dashboard in:title"
gh pr list --repo <owner>/<repo> --state all --author app/renovate --json number -q length
```

Check both after adding the config, not months later. A repository can carry a fully documented
`renovate.json`, a complete set of SHA-pinned actions and a pile of open Dependabot alerts while
Renovate has never looked at it once.

Validate the config itself with Renovate's own validator, and **pin the validator to a current
version** — `npx` resolves `renovate` to a very old release, which reports valid modern options
as errors and invites you to "fix" a working config:

```bash
npx --yes --package renovate@<current> -- renovate-config-validator
```

### Turn on the dependency graph, alerts and security updates

These are repository settings, not files, so a repository can carry a perfectly good
`dependabot.yml` and have none of it running. They form a chain, and each link is a
prerequisite for the next:

```
dependency graph  ->  Dependabot alerts  ->  Dependabot security updates
```

The split below hands Dependabot the security half of the workload. That only happens if the
whole chain is on. Enable it with two calls — the first turns on the dependency graph *and*
alerts together, which is why there is no separate graph command:

```bash
gh api --method PUT "repos/<owner>/<repo>/vulnerability-alerts"      # graph + alerts
gh api --method PUT "repos/<owner>/<repo>/automated-security-fixes"  # security updates
```

Both answer `204 No Content`, and both are idempotent, so running them against a repository that
already has the setting changes nothing. Do this when the repository is created, alongside
`git config user.email`.

A public repository gets the graph switched on and unremovable, which makes this look done when
it is not: alerts and security updates are still off until the calls above are made. A private
repository starts with none of the three.

Verify rather than assume, because the two endpoints disagree about how they report state:

```bash
gh api -i "repos/<owner>/<repo>/vulnerability-alerts" | head -1   # 204 = on, 404 = off
gh api "repos/<owner>/<repo>/automated-security-fixes"            # read .enabled
```

`automated-security-fixes` returns **`200` whether the feature is on or off** — the answer is
`{"enabled": false}` in the body. Checking status codes alone reports every repository as
healthy. `gh api repos/<owner>/<repo> --jq .security_and_analysis` gives the same answer for
security updates, plus the secret-scanning settings, and needs admin.

This is the same silent failure as
[Committing `renovate.json` does not turn Renovate on](#committing-renovatejson-does-not-turn-renovate-on),
and for a uv project it stacks with
[a graph that is empty until something submits it](shared-workflows.md#a-uv-project-must-submit-its-own-dependency-graph):
three independent switches, none of which reports anything when off, all of which have to be on
before a published advisory reaches a pull request.

### Split Renovate and Dependabot by job, not by ecosystem

The 14-day delay above is a supply-chain measure: it protects you from a release that turns out
to be broken or malicious, and it works by waiting. Waiting is exactly the wrong response to a
published advisory, where the fix is already known and every day of delay is another day of
exposure.

One tool cannot be both slow and immediate, so give the two tools opposite latencies:

| Tool | Handles | Latency |
|---|---|---|
| Renovate | routine version updates, grouped into one PR | delayed 14 days (`minimumReleaseAge`) |
| Dependabot | security updates only | immediate |

Renovate takes the routine half because it is also the only one of the two with managers for
`mise.toml` and `customManagers` regex entries. Dependabot takes the security half because its
advisory-driven updates are exempt from delay.

Do **not** let both do version updates. That produces duplicate PRs, and Dependabot's half
ignores the 14-day delay — quietly defeating the measure the delay exists for.

`open-pull-requests-limit: 0` is what implements the split. It is GitHub's documented way to
switch off *version* updates for an ecosystem, and security PRs are exempt from it (and from
`cooldown`), so setting it to zero leaves exactly the security half running:

```yaml
updates:
  - package-ecosystem: "uv"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 0
```

**`package-ecosystem` must track the build tool.** A stale value fails *silently*: `pip` reads
`poetry.lock` and understands neither `uv.lock` nor `[dependency-groups]`, so after a migration
it keeps running, finds nothing, and reports green — indistinguishable from working coverage.

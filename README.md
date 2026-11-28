# common

What [iglootools](https://github.com/iglootools) projects share: the
guidelines, the reusable GitHub workflows every repository calls, the
`iglootools` command for the guidelines that are easier to ship as code than to
describe, and the Claude Code plugin that delivers all of it.

<!-- toc -->
**On this page**

- [Contents](#contents)
- [Usage with Claude Code](#usage-with-claude-code)
<!-- tocstop -->

## Contents

The rules themselves live in [**`guidelines/`**](guidelines/), whose
[index](guidelines/README.md) says which file governs which change.

The rest of the repository supports the guidelines rather than stating any:

- [skills/](skills/), [audit/](audit/) and [agents/](agents/): find what the
  `audit-pr`, `audit-pr-stack` and `audit-full` skills, the runbooks they share
  and the `auditor` agent do.
- [.claude/](.claude/): find the `audit-consistency-*` skills, which check the
  projects' guidelines and build against common's and each other.
- [hooks/](hooks/): find the hook that loads the guideline indexes, and the
  one that reminds you to audit before a pull request.
- [src/iglootools/](src/iglootools/): find the `iglootools` command; how
  projects install and pin it is in
  [iglootools-cli.md](guidelines/project-setup/iglootools-cli.md).
- [.github/workflows/](.github/workflows/): find the reusable workflows; how
  projects call them is in
  [shared-workflows.md](guidelines/project-setup/shared-workflows.md).

To change any of it, start from [CONTRIBUTING.md](CONTRIBUTING.md).

## Usage with Claude Code

A single Claude Code plugin delivers everything here, installed per project; no
clone of this repository is needed.

- [docs/installation.md](docs/installation.md): follow to install the plugin in
  a project, and to move one project or all of them to a new release.
- [docs/usage.md](docs/usage.md): follow to audit a branch or a codebase, fix
  the findings, and check the projects against common.
- [docs/internals.md](docs/internals.md): understand how the indexes, the
  audits and the hooks decide what an agent reads, and when.

Common itself does not install the plugin. An installed plugin is the last
release, so here it would be behind the guidelines being edited.
[AGENTS.md](AGENTS.md) points agents at the working-tree files instead, as
[How common applies its own guidelines](docs/internals.md#how-common-applies-its-own-guidelines)
explains.

Licensed under the [Apache License 2.0](LICENSE).

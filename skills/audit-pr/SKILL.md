---
description: Audit the current branch's changes against its base — bugs, error handling, data integrity, security, performance, tests, architecture, dependencies, maintainability, operability, documentation, guideline conformance and commit history — with parallel auditor agents, and write a navigable Markdown report with an ID for every finding.
argument-hint: "[base-ref] [only:CAT,CAT | skip:CAT,CAT]"
disable-model-invocation: true
---

Audit the commits on this branch that are not on its base. Arguments: $ARGUMENTS

## 1. Establish the scope

1. The base is the ref given in the arguments. Otherwise it is the pull
   request's base (`gh pr view --json baseRefName -q .baseRefName`, as
   `origin/<name>`), and otherwise the default branch
   (`git symbolic-ref --short refs/remotes/origin/HEAD`). Run `git fetch` first,
   so the base is current.
2. The range runs from `git merge-base <base> HEAD` to `HEAD`. With no commits
   in it, say so and stop.

## 2. Audit the range

Follow `${CLAUDE_PLUGIN_ROOT}/audit/branch-range.md` with the
merge-base as `<base>`, `HEAD` as `<head>` and the repository root as the
directory that has it checked out.

---
description: Audit every pull request in a stack, each against the pull request below it, the way audit-pr audits one branch — bugs, error handling, data integrity, security, performance, tests, architecture, dependencies, maintainability, operability, documentation, guideline conformance and commit history — with parallel auditor agents, and write one navigable Markdown report per pull request.
argument-hint: "[pr-number | branch] [only:CAT,CAT | skip:CAT,CAT]"
disable-model-invocation: true
---

Audit each open pull request in a stack on its own: its commits against the
branch it is based on. Arguments: $ARGUMENTS

A stack is a chain of pull requests where each one's base branch is the head
branch of the one below it, as
`${CLAUDE_PLUGIN_ROOT}/guidelines/coding/git.md` › Give a pull request one
intent, and a commit one step describes.

## 1. Find the stack

1. Run `git fetch` first, so every branch is current. List the open pull
   requests once:
   `gh pr list --state open --limit 200 --json number,title,url,body,isDraft,headRefName,baseRefName`.
2. The starting pull request is the one given in the arguments, by number or
   by head branch, and otherwise the current branch's
   (`gh pr view --json number -q .number`). When there is none, say so, suggest
   `/iglootools:audit-pr`, and stop.
3. Walk down: while an open pull request's head branch is the current one's
   base, it is the next one below. The bottom pull request's base, usually the
   default branch, is the stack's base. Walk up: every open pull request whose
   base is the head branch of one already in the stack belongs to it, so a
   branch with two pull requests on top includes both.
4. Order the pull requests bottom first, depth first where the stack branches.
   With a single pull request, say that `/iglootools:audit-pr` covers it, and
   carry on.

## 2. Establish each pull request's scope

1. Resolve each head branch to a commit: the local branch when it exists,
   otherwise `origin/<branch>`. When both exist and differ, audit the local
   one, and record the commits `origin/<branch>` has that it lacks under that
   report's "Not audited". The bottom pull request's base is
   `origin/<base branch>`; every other one's base is the head commit just
   resolved for the pull request below it.
2. Check that each base is an ancestor of the head above it
   (`git merge-base --is-ancestor <base> <head>`). When one is not, the branch
   above still carries old copies of commits rewritten below it, and its audit
   would blame them on the wrong pull request. List those branches, suggest
   restacking them (`git rebase --update-refs` from the top branch, as git.md ›
   Fold rework into the commit it corrects shows), and stop.
3. Each range is `<base>..<head>`. List it with
   `git log --reverse --format='%h %s' <base>..<head>` and
   `git diff --stat <base>..<head>`. A pull request with no commits in its
   range is left out, and named in the reply.
4. Uncommitted changes are not audited: when `git status --porcelain` shows any,
   record them under "Not audited" in the report of the pull request checked
   out, if it is one of the stack.
5. Every pull request whose head is not the commit checked out gets a detached
   worktree, so its auditors read and check its files rather than the
   checkout's:
   `git worktree add --detach .iglootools/worktrees/pr-<number> <head>` from the
   repository root, after removing one an earlier run left there. The pull
   request checked out uses the repository root itself.

## 3. Choose the categories

All categories in `${CLAUDE_PLUGIN_ROOT}/guidelines/review/audit.md`, `HIST`
included, unless the arguments narrow them with `only:` or `skip:`, the same
for every pull request. A category left out on request goes under "Not audited"
as "not requested".

## 4. Audit the commit history yourself

For each pull request, check its range as `audit-pr` does: read
`${CLAUDE_PLUGIN_ROOT}/guidelines/coding/git.md` in full and check the range
against every rule in it, using its own commands with the pull request's base,
recording each problem as a `finding` block in the auditor's format with
`origin` set to the commit.

Then check what only a stack shows, as findings in the pull request concerned,
with `origin: n/a` and the pull request's URL as `location`:

- each pull request above the bottom says in its description that it is
  stacked on the one below (git.md › Give a pull request one intent, and a
  commit one step);
- a commit belongs in the pull request it is in, not in one below or above it:
  a preparatory step that a lower pull request needs, or work that depends on
  an upper one.

## 5. Split the work

For each pull request, split its remaining categories as `audit-pr` does:

- **Small range** (up to about 15 changed files and 500 changed lines): one
  auditor with every remaining category.
- **Larger range**: three auditors —
  functional `BUG, ERR, DATA`;
  risk `SEC, PERF, DEPS`;
  structure `TEST, ARCH, MAINT, OPS, DOC, GUIDE`.

Each auditor's scope is one pull request's range: its base and head SHAs, its
commit list and changed files, and its worktree as the repository root.

## 6. Run the auditors and write the reports

Follow `${CLAUDE_PLUGIN_ROOT}/skills/audit-pr/assemble-report.md` for every pull
request at once, with these changes:

- **Steps 1 and 4.** Start the auditors of every pull request in one message,
  and the verifiers likewise, at most ten agents at a time. When there are more,
  run the pull requests in batches, bottom first. Pass each pull request's base
  SHA and worktree, and keep each reply with the pull request it audited.
- **Before step 5, move findings to the pull request that introduced them.** An
  auditor reports as `pre-existing` a problem present at its base, which for
  every pull request above the bottom includes the commits of the ones below.
  For each such finding, check whether it is present at the stack's base
  (`git show <stack base>:<path>`). When it is not, find the commit that
  introduced it (`git log -L` or `git blame` on the lower head) and move the
  finding to that commit's pull request, with that commit as its origin; drop
  it instead when that pull request already has it, by location and root cause.
- **Steps 5 to 7** run per pull request, with your `HIST` findings for it added
  before "Merge duplicates", so each report has its own IDs. Each report's scope
  name is `pr-<branch>`, with `/` in the branch name replaced by `-`, as
  `audit-pr` names it, and its `Scope:` line gives the pull request's range.
  Locations still link as `../../<path>`, to the repository root, since the
  worktrees are removed. A location that is a pull request's URL links to that
  URL.
- **Step 8** is replaced by the reply below.

Then remove the worktrees: `git worktree remove --force` for each, then
`git worktree prune`.

## 7. Reply

Do not paste the reports. Reply with, for each pull request, bottom first:

- its number, title and head branch, and the report's path, as a link;
- the summary table;
- one line per `critical` and `high` finding: ID, title, location;
- anything under "Not audited".

Then name any pull request left out, with why, and how to continue: ask for
findings by pull request and ID, category or severity ("fix SEC-1 in #42", "fix
all high"). They will be fixed following the reports' "Fixing findings"
section; a fix in a lower pull request is rebased into every branch above it
with `git rebase --update-refs`, and each branch is pushed.

Do not start fixing anything until asked.

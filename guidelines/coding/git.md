# Git Guidelines

How commits and pull requests are shaped for review. Read it before committing,
rewriting a branch or opening a pull request. Every commit on a branch lands on
`main` as it is, so a branch reads as the clearest sequence of steps to the
final change, not as a record of how the author got there.

<!-- toc -->
**On this page**

- [Give a pull request one intent, and a commit one step](#give-a-pull-request-one-intent-and-a-commit-one-step)
- [Keep refactoring apart from behaviour changes](#keep-refactoring-apart-from-behaviour-changes)
- [Fold rework into the commit it corrects](#fold-rework-into-the-commit-it-corrects)
- [Merge with a merge commit, not a squash merge or a rebase merge](#merge-with-a-merge-commit-not-a-squash-merge-or-a-rebase-merge)
- [Write the subject as a Conventional Commit, and the body as the why](#write-the-subject-as-a-conventional-commit-and-the-body-as-the-why)
- [Rebase and clean up before asking for review](#rebase-and-clean-up-before-asking-for-review)
- [Work in the mode the person names](#work-in-the-mode-the-person-names)
  - [Exploratory: iterate in small steps, and publish only when asked](#exploratory-iterate-in-small-steps-and-publish-only-when-asked)
  - [PR-driven: one reviewed pull request at a time](#pr-driven-one-reviewed-pull-request-at-a-time)
  - [Autonomous: merge when green, and report afterwards](#autonomous-merge-when-green-and-report-afterwards)
<!-- tocstop -->

## Give a pull request one intent, and a commit one step

A reviewer approves or rejects a pull request as a whole; each commit is one
step towards it.

**Why:** a pull request with two intents cannot be approved for one of them.
See [Small, reviewable changes](../philosophy.md#small-reviewable-changes).

- **A commit on the branch** for whatever the pull request needs to be correct
  and complete: the preparatory refactoring, tests, docs, a fix for a problem
  the change exposes.
- **A pull request of its own** for work that could merge to `main` alone, or
  that a reviewer could approve while rejecting the rest: an unrelated bug fix,
  a dependency or tooling update, a rule change that needs its own discussion.
- **Split one intent** when its parts differ in risk
  ([general.md › Keep riskier changes structurally apart](general.md#keep-riskier-changes-structurally-apart)),
  touch an interface other repositories consume, or need to land at different
  times.
- **Split when it outgrows one review sitting**, roughly a few hundred
  hand-written lines; mechanical changes count for less. The preparatory
  refactoring can usually merge first.
- **Stack a pull request that depends on another**: base its branch on the
  other's, and say so in the description.
- **Decide about work found along the way when you find it**, since moving it
  later rewrites both branches. A small fix in code the branch touches is a
  commit before the change that needed it; anything else branches from `main`,
  with the current branch stacked on it if it depends on it.

## Keep refactoring apart from behaviour changes

A commit either changes behaviour or restructures code, never both.

**Why:** a refactoring is checked only for the absence of change, which the
unchanged tests confirm; a behaviour change is read line by line, and mixed in,
it hides among a hundred renamed lines.

- Mechanical changes (renames, moves, reformatting code the branch does not
  otherwise touch, regenerated files, lock updates) get their own commits, with
  the command in the message (`uv lock --upgrade-package httpx`), so the
  reviewer re-runs it.
- Format the code a commit adds or changes in that same commit: run `mise run
  fmt` before committing. A separate formatting commit is only for code the
  branch did not otherwise change, such as adopting a formatter or upgrading
  one; formatting a commit's own lines afterwards is rework to fold, not a
  mechanical change.
- Put the preparatory refactoring first, then the change it makes easy.
- Aim for every commit to build and pass the checks, so `git bisect` stops
  somewhere meaningful. Readability wins a conflict (an interface change, then
  its callers); say in the message that the build is broken until the next
  commit, so whoever bisects knows to `git bisect skip` it.
- Check each commit with `mise run preflight-quick`, and run `mise run
  preflight` every few commits and before asking for review
  ([mise.md](../project-setup/mise.md#name-tasks-by-family) says what each
  runs). Fold what the full run catches into the commits that caused it, then
  confirm every commit still passes with
  `git rebase --exec 'mise run preflight-quick' <base>`. In a linked worktree
  the command runs with `GIT_DIR` set, so a suite that runs git must clear it
  first
  ([general.md](general.md#patch-only-in-the-three-documented-cases-and-list-each-one)),
  or its fixtures write into the repository being rebased.

## Fold rework into the commit it corrects

A bug fixed later in the branch, a decision reversed, a name improved: each is
folded into the commit that introduced the code. Until the branch is merged, its
history is a draft.

**Why:** the reviewer never reads code a later commit deletes.

- Fold feedback the same way, from a linter, type checker, test, CI or reviewer:
  no `fix lint`, `fix tests` or `address review` commits for problems the branch
  introduced. Feedback that asks for a genuinely new step ("also handle the
  empty case") becomes its own commit, placed where it belongs.
- Fold a fix only into the commit that introduced the problem. A move, rename
  or extraction carries existing problems along (a lint finding where the
  linter now looks, a type error on a re-indented line); fixing them inside it
  makes a re-runnable commit one to read line by line. Give the cleanup its own
  commit (`style:`, `refactor:`), preferably before the move, or right after it
  if the problem only shows there. Run the same check at the base, or
  `git blame <base>` the line, to tell which.
- Mechanics: `git commit --fixup=<sha>`, then `git rebase --autosquash <base>`.
  `git commit --amend --no-edit` for the latest commit; `--fixup=amend:<sha>`
  when the correction also changes the target's message. With stacked branches,
  add `--update-refs` so every branch above moves too, and push each one.
- Push with `git push --force-with-lease`, which refuses to overwrite commits
  you have not seen. Rewrite only branches you own; coordinate with anyone who
  built on yours. Check the rewrite with `git range-diff @{upstream}...HEAD`
  before pushing (GitHub links each force-push to a comparison too), and after
  pushing in answer to a review, say on the pull request what changed.

## Merge with a merge commit, not a squash merge or a rebase merge

Land a pull request with GitHub's *Create a merge commit*, never *Squash and
merge* or *Rebase and merge*. This is about how the pull request lands, not how
the branch is kept: the branch is rebased onto `main` before review
([below](#rebase-and-clean-up-before-asking-for-review)), then merged with a
merge commit. The repository ruleset enforces the merge method.

**Why:** squash and rebase merges write new commits, so the reviewed ones never
reach `main`. A rebase merge copies each commit onto `main` with a new SHA, even
when the branch is already up to date. See
[Event-driven, append-only, replayable](../philosophy.md#event-driven-append-only-replayable).

- **History.** A merge keeps every reviewed commit for `blame` and `bisect`, and
  `git log --first-parent` still reads as one entry per pull request.
- **Safe branch deletion.** `git branch -d` and `--merged` see a merged branch;
  a squashed one needs `git branch -D`, which deletes unmerged work as readily.
- **Stacked pull requests.** The lower commits reach `main` under the same
  hashes, so the upper diff is unchanged; after a squash it shows the lower
  change again, and rebasing it conflicts with the copy.
- A messy branch is cleaned up before review
  ([below](#rebase-and-clean-up-before-asking-for-review)), not hidden by a
  squash.

## Write the subject as a Conventional Commit, and the body as the why

The subject starts with a
[Conventional Commits](https://www.conventionalcommits.org/) type (`feat:`,
`fix:`, `refactor:`, `perf:`, `test:`, `docs:`, `build:`, `ci:`, `chore:`) and
says what the commit does, in the imperative. The body explains *why*, as
[code comments](general.md#comment-why-never-what) do: the rejected
alternative, the constraint that forced the approach, the command behind a
mechanical change.

**Why:** the type tells the reviewer what to expect (`refactor:` promises no
change in behaviour), and the release workflow reads it to choose the version
bump
([pypi-publishing.md](../project-setup/pypi-publishing.md#let-the-release-workflow-pick-the-bump-from-conventional-commits)).

- The message describes the commit as it finally is: when a fold changes what a
  commit does, update the message too.

## Rebase and clean up before asking for review

While you work, commit however is useful: checkpoints, experiments, `wip`.
Before opening the pull request or marking a draft ready, turn them into the
sequence described above.

**Why:** the reviewer reads the branch one commit at a time, and every commit
reaches `main`.

- Rebase onto the current `main` (`git fetch && git rebase origin/main`), so the
  change is reviewed against what it merges into and its author resolves the
  conflicts; never merge `main` into the branch.
- Reorder, split, fold and reword until each commit is one step with a fitting
  message: `git rebase -i origin/main`, or without an interactive editor,
  `git reset origin/main` and commit again step by step, staging by path.
- Read the branch as the reviewer will (`git log --reverse --stat <base>..`,
  then each diff): one concern per commit, messages that match their diffs, no
  commit undoing part of an earlier one.
- `git log --format=%s <base>.. | grep -E '^(fixup|squash|amend)! '` must print
  nothing: an unfolded fixup looks finished until someone reads its subject.
- Commits added to a pull request already open go through the same pass before
  they are pushed: fold the ones that rework an earlier commit into it, and read
  the branch again. A branch under review is still a draft.

## Work in the mode the person names

Agree on one of three modes before starting, and say which one is in use. Each
sets where the work happens, when it is committed, when a pull request opens,
and who merges it. The person can switch modes at any point. When none is named,
propose one and wait for agreement.

**Why:** how much review a change needs varies more than the change's size
suggests. Naming the mode up front settles what may be published without asking,
instead of leaving it to be guessed change by change.

- In every mode, the rest of this file still applies: the history reaching
  review is clean, and nothing bypasses a check, a ruleset or a permission
  prompt.
- Once a pull request is merged, delete its branch, locally and on the remote,
  and remove its worktree (`git worktree remove <path>`). A merged branch left
  behind looks like work in progress. `iglootools github prune-branches`
  deletes every one left over.
- When the modes apply is refined as they are used.

### Exploratory: iterate in small steps, and publish only when asked

For discovery, design and anything with many judgment calls: small steps, lots
of feedback, lots of rework. Work in the main checkout of each repository
involved. Leave a change uncommitted, or make one or several commits, depending
on how settled it is. Rework stays uncommitted until the person has reviewed it,
then folds into the commit it belongs in. Open the pull request at the end, once
the person explicitly approves.

**Why:** most of the work is reworked before it is right, and every commit or
pull request made too early is one more thing to rewrite. In the main checkout,
the person reads, runs and edits each change as it is made, in the editor and
terminal they already have open.

### PR-driven: one reviewed pull request at a time

For lower-risk changes with few judgment calls, such as fixing audit findings:
shape the commits, open one pull request, and wait. The person reviews it and
merges it, or approves the merge. Work in a separate worktree of each repository
involved, started from `origin/main`, or from the branch a stacked pull request
builds on (`git worktree add -b <branch> <path> origin/main`), never in the main
checkout.

**Why:** the change is clear enough to finish without discussion, but still
deserves a human reading it before it lands. The main checkout is where
exploratory work happens, and a branch switched or a file changed under it
disrupts that work.

### Autonomous: merge when green, and report afterwards

For mechanical changes, such as carrying a change across the iglootools
projects, realigning a project with the guidelines, or bumping dependencies:
work in a separate worktree of each repository, as
[PR-driven](#pr-driven-one-reviewed-pull-request-at-a-time) work does, open each
pull request, merge it once its checks pass with
`iglootools github merge-when-green <pr>`, and carry on. Stop and
ask when a check fails for a reason that is not mechanical, or when a judgment
call appears. At the end, list what was merged in each project, with links, so
the person can review after the merge.

**Why:** reviewing a mechanical change before merging costs the person's time
and catches little that the checks do not. The summary keeps that review
possible after the merge.

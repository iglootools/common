# Git Guidelines

Pull requests merge with a merge commit
([repository.md](../project-setup/repository.md#merge-pull-requests-with-a-merge-commit)), so
every commit on a branch lands on `main` as it is, for `git log`, `git blame` and `git bisect`.
A branch is therefore reviewed and kept one commit at a time, and should read as the clearest
sequence of steps to the final change, not as a record of how the author got there. See
[Small, reviewable changes](../../philosophy.md#small-reviewable-changes) for the reasoning.

## A new commit or a new pull request

A pull request has one intent, which a reviewer approves or rejects as a whole. A commit is one
step towards it.

- **A commit on the branch** for whatever the pull request needs to be correct and complete:
  the preparatory refactoring, tests, docs, a fix for a problem the change exposes.
- **A pull request of its own** for work that could merge to `main` alone, or that a reviewer
  could approve while rejecting the rest: an unrelated bug fix, a dependency or tooling update,
  a rule change that needs its own discussion.
- **Split one intent** when its parts differ in risk (an event schema next to a read model, a
  destructive operation next to a safe one —
  [People and AI Agents](general.md#people-and-ai-agents)), touch an interface other
  repositories consume, or need to land at different times.
- **Split when it outgrows one review sitting**, roughly a few hundred hand-written lines.
  Mechanical changes count for less. The preparatory refactoring is usually the part that can
  merge first.
- **Stack a pull request that depends on another**: base its branch on the other's, and say so
  in the description ([merge commits](#merge-with-a-merge-commit-not-a-squash-or-a-rebase) keep
  the stack intact).
- **Decide about work found along the way when you find it.** A small fix in code the branch
  touches is a commit before the change that needed it. Anything else branches from `main`,
  with the current branch stacked on it if it depends on it. Moving it later means rewriting
  both branches.

## Keep refactoring apart from behaviour changes

- A commit either changes behaviour or restructures code, never both. A refactoring is checked
  only for the absence of change, which the unchanged tests confirm. A behaviour change is read
  line by line. Mixed together, the behaviour change hides among a hundred renamed lines.
- Mechanical changes (renames, moves, formatting, regenerated files, lock file updates) get
  their own commits, with the command that produced them in the message (`ruff format`,
  `uv lock --upgrade-package httpx`) so the reviewer can re-run it instead of reading the diff.
- Put the preparatory refactoring first, then the change it makes easy.
- Aim for every commit to build and pass the checks, so `git bisect` stops somewhere
  meaningful. Readability wins when the two conflict: an interface change in one commit and its
  callers in the next can be clearer than both together. Say in the message that the build is
  broken until the next commit, so whoever bisects knows to `git bisect skip` it.
- A fix made along the way gets its own commit, or its own pull request when it is an intent of
  its own ([above](#a-new-commit-or-a-new-pull-request)).

## Fold rework into the commit it corrects

- A bug fixed later in the branch, a decision reversed, a name improved: each is folded into
  the commit that introduced the code, so the reviewer never reads code a later commit deletes.
  Until the branch is merged, its history is a draft. This overrides the habit of adding a new
  commit for every change, for agents as much as for people.
- Feedback is folded the same way, from a linter, type checker, test, CI or reviewer: no
  `fix lint`, `fix tests` or `address review` commits for problems the branch introduced.
  Feedback that asks for a genuinely new step ("also handle the empty case") becomes its own
  commit, placed where it belongs in the sequence.
- Fold a fix only into the commit that introduced the problem. A move, rename or extraction
  carries existing problems along: a lint finding that appears because the file now sits where
  the linter looks, a type error on a re-indented line. Fixing them inside it turns a commit
  the reviewer could check by re-running a command into one they must read line by line. Give
  the cleanup its own commit (`style:`, `refactor:`), preferably *before* the move, done in
  place, or right after it if the problem only shows up there. To tell which case it is, run
  the same check at the base, or `git blame <base>` the line.
- Mechanics: `git commit --fixup=<sha>`, then `git rebase --autosquash <base>` (no `-i` needed
  since Git 2.44). `git commit --amend --no-edit` for the latest commit; `--fixup=amend:<sha>`
  when the correction also changes the target's message. With stacked branches, add
  `--update-refs` (Git 2.38+) so every branch above moves too, and push each one.
- Push with `git push --force-with-lease`, which refuses to overwrite commits you have not
  seen. Rewrite only branches you own; coordinate with anyone who built on yours. The reviewer
  keeps their view of what changed: GitHub links each force-push to a comparison, and
  `git range-diff @{upstream}...HEAD` shows it commit by commit before you push. After pushing
  in answer to a review, say on the pull request what changed.

## Merge with a merge commit, not a squash or a rebase

The repository ruleset enforces merge commits
([repository.md](../project-setup/repository.md#merge-pull-requests-with-a-merge-commit)).
Squash and rebase merges write new commits, so the reviewed ones never reach `main`, which
breaks three things:

- **History.** A merge keeps every reviewed commit, and `git log --first-parent` still reads as
  one entry per pull request. A squash leaves `blame` and `bisect` one large commit for good.
- **Safe branch deletion.** After a merge, `git branch -d` and `git branch --merged` see the
  branch as merged. After a squash, only `git branch -D` deletes it, and that deletes a branch
  with real unmerged work just as readily.
- **Stacked pull requests.** After a merge, the lower commits are in `main` under the same
  hashes, so the upper pull request's diff is unchanged. After a squash, the upper branch still
  carries the originals, its diff shows the lower change again, and rebasing it conflicts with
  the copy.

Squash merging often hides a messy branch; this guideline cleans the branch up before review
instead. A project that wants another merge method records why in its `docs/guidelines.md`.

## Commit messages

- The subject starts with a [Conventional Commits](https://www.conventionalcommits.org/) type
  (`feat:`, `fix:`, `refactor:`, `perf:`, `test:`, `docs:`, `build:`, `ci:`, `chore:`) and says
  what the commit does, in the imperative. The type tells the reviewer what to expect
  (`refactor:` promises no change in behaviour), and the release workflow reads it to choose
  the version bump
  ([pypi-publishing.md](../project-setup/pypi-publishing.md#let-the-release-workflow-pick-the-bump-from-conventional-commits)).
- The body explains *why*, as [code comments](general.md#code-comments) do: the rejected
  alternative, the constraint that forced the approach, the command behind a mechanical change.
- The message describes the commit as it finally is: when a fold changes what a commit does,
  update the message too.

## Rebase and clean up before asking for review

- While you work, commit however is useful: checkpoints, experiments, `wip`. Before opening the
  pull request or marking a draft ready, turn them into the sequence described above.
- Rebase onto the current `main` (`git fetch && git rebase origin/main`), so the change is
  reviewed against what it will merge into and its author resolves the conflicts. Bring in
  later `main` commits the same way, never by merging `main` into the branch.
- Reorder, split, fold and reword until each commit is one step with a fitting message:
  `git rebase -i origin/main`, or without an interactive editor, `git reset origin/main` and
  commit again step by step, staging by path.
- Read the branch as the reviewer will (`git log --reverse --stat <base>..`, then each diff):
  one concern per commit, messages that match their diffs, no commit undoing part of an earlier
  one.
- `git log --format=%s <base>.. | grep -E '^(fixup|squash|amend)! '` must print nothing: an
  unfolded fixup looks finished until someone reads its subject.

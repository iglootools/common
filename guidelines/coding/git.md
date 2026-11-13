# Git Guidelines

A branch's commits are written for the person reviewing them, and after that for whoever reads
the history. Pull requests merge with a merge commit
([repository.md](../project-setup/repository.md#merge-pull-requests-with-a-merge-commit)), so
every commit on the branch lands on `main` as it is and stays there for `git log`, `git blame`
and `git bisect`. That means the branch is reviewed, and kept, one commit at a time. It should
read as the clearest sequence of steps to the final change, not as a record of how the author
got there. See [Small, reviewable changes](../../philosophy.md#small-reviewable-changes) for the
reasoning.

## Keep refactoring apart from behaviour changes

- A commit either changes behaviour or restructures code without changing it. It never does
  both. A reviewer checks a refactoring for one thing: that nothing changed, which the
  unchanged tests confirm. A reviewer reads a behaviour change line by line, so it has to be
  small. Mix the two and the behaviour change is hidden among a hundred renamed lines.
- Mechanical changes go in their own commits: renames, moves, formatting, regenerated files,
  lock file updates. Put the command that produced the change in the message (`ruff format`,
  `uv lock --upgrade-package httpx`), so the reviewer can run it again instead of reading the
  diff.
- Put the preparatory refactoring first, then the change it makes easy.
- Ideally each commit builds and passes the checks on its own, so that `git bisect` stops on a
  commit that means something. That is a goal, not a hard rule, and readability wins when the
  two conflict. Sometimes a commit that leaves the build broken makes the change easier to
  follow. For example, one commit changes an interface and the next updates its callers, where
  combining them would bury the interface change under the call sites. In that case keep the
  split, and say in the message that the build is broken until the next commit, so whoever
  bisects knows to `git bisect skip` it.
- If you fix something unrelated to the pull request's intent along the way, give the fix its
  own commit. If it needs its own discussion, give it its own pull request.

## Fold rework into the commit it corrects

- The branch shows each step as it finally is, not the way you got there. A bug fixed later in
  the branch, a decision reversed, a name improved after the fact: each one is folded into the
  commit that introduced the code. Otherwise the reviewer, reading commit by commit, reviews
  code that a later commit deletes.
- Feedback goes through the same process, whether it comes from a tool or a person: the
  linter, the type checker, a failing test, CI, a review comment. A branch has no
  `fix lint`, `fix tests` or `address review` commits for problems the branch introduced. The
  exception is feedback that asks for a genuinely new step ("also handle the empty case"). That
  becomes a commit of its own, placed where it belongs in the sequence.
- Fold a fix only into a commit that owns the problem, meaning the commit introduced it. A move,
  rename or extraction carries existing code along, and the problems come with it: a lint
  finding that appears because the file now sits where the linter looks, a type error on a line
  the diff touched only to re-indent it. The commit did not create these. Fixing them inside it
  turns a mechanical commit the reviewer could check by re-running a command into one they
  have to read line by line. Give the cleanup a commit of its own (`style:`, `refactor:`), with
  the moved code untouched in the move commit. The test is whether the problem already exists
  at the base: run the same check there, or look at the line with `git blame <base>`.
- Prefer to put that cleanup *before* the move, done in place. Then the move stays purely
  mechanical, and each commit still passes the checks that the moved location triggers. If the
  problem only becomes visible after the move, put the cleanup right after it.
- This overrides the default of adding a new commit for every change, including when an agent
  is the one committing. Until the branch is merged, its history is a draft.
- Mechanics: `git commit --fixup=<sha>` records the correction, and
  `git rebase --autosquash <base>` folds it into its target. Since Git 2.44 this works without
  `-i`, so it also runs where no interactive editor is available. For the latest commit,
  `git commit --amend --no-edit` does the same in one step. `--fixup=amend:<sha>` also rewrites
  the target's message, for when the correction changes what the commit does.
- Push the rewritten branch with `git push --force-with-lease`, which refuses to overwrite
  commits you have not seen. Rewriting a feature branch is expected, and the default-branch
  ruleset keeps `main` itself out of reach. Rewrite only branches you own. If someone else has
  built on the branch, coordinate with them first.
- Rewriting does not take away the reviewer's view of what changed since their last look:
  GitHub links each force-push in the timeline to a comparison. Before you push,
  `git range-diff @{upstream}...HEAD` shows the same thing commit by commit. When you push in
  answer to a review, reply on the pull request with what changed.
- Bring in new commits from `main` by rebasing onto it, not by merging `main` into the branch.
  A merge from `main` puts a commit in the branch that is not a step of the change.
- When branches are stacked, rebase with `--update-refs` (Git 2.38+), so a fold into a lower
  branch also moves every branch stacked on it. Push each branch that moved.

## Merge with a merge commit, not a squash or a rebase


By default a pull request lands with a merge commit. The repository ruleset enforces this
([repository.md](../project-setup/repository.md#merge-pull-requests-with-a-merge-commit)). A
squash merge or a rebase merge writes new commits, so the commits that were reviewed never
reach `main`, and three things break:
- **History.** A merge keeps every reviewed commit and records where the branch joined.
  `git log --first-parent` still reads as one entry per pull request, so the summary is always
  available. A squash throws away the individual steps for good, and every `blame` and `bisect`
  after that lands on one large commit.
- **Deleting branches safely.** After a merge, the branch's commits are part of `main`, so
  `git branch -d` deletes the branch and `git branch --merged` lists it. After a squash or
  rebase merge, Git sees the branch as unmerged. Cleaning up then takes `git branch -D`, which
  deletes just as readily a branch that really does hold unmerged work.
- **Stacked pull requests.** Suppose a pull request is based on another branch. Once the lower
  branch is merged, the upper pull request's base moves to `main` and its diff stays the same:
  the lower commits are already in `main`, under the same hashes. After a squash merge, those
  commits exist in `main` only as one copy with a new hash, so the upper branch still carries
  the originals. Its diff then shows the lower change a second time, and rebasing it brings
  conflicts with the copy.

Squash merging is often a way to hide a messy branch. This guideline cleans the branch up
before review instead, so the merge has something worth keeping. A project that wants a
different merge method records the reason in its `docs/guidelines.md`.

## Commit messages

- Start the subject with a [Conventional Commits](https://www.conventionalcommits.org/) type
  (`feat:`, `fix:`, `refactor:`, `perf:`, `test:`, `docs:`, `build:`, `ci:`, `chore:`), followed
  by what the commit does, in the imperative. The type tells the reviewer what kind of commit to
  expect. `refactor:` promises no change in behaviour. The release workflow reads the types to
  choose the version bump
  ([pypi-publishing.md](../project-setup/pypi-publishing.md#let-the-release-workflow-pick-the-bump-from-conventional-commits)).
- The body explains *why*, under the same rule as [code comments](general.md): the diff already
  shows what changed. Include the alternative you rejected, the constraint that forced the
  approach, and the command that produced a mechanical change.
- The message describes the commit as it finally is. When a fold changes what a commit does,
  update its message too.

## Rebase and clean up before asking for review

- While you work, commit however is useful: checkpoints, experiments, `wip`. Before you open
  the pull request, or before you mark a draft ready, turn those commits into the sequence
  described above. That is the moment the branch stops being yours alone.
- First rebase onto the current `main` (`git fetch && git rebase origin/main`), so the
  reviewer reads the change against the code it will actually merge into, and any conflicts
  are resolved by the person who knows the change.
- Then restructure: reorder, split, fold and reword until each commit is one step with a
  message that fits it. `git rebase -i origin/main` is the usual tool. Without an interactive
  editor, `git reset origin/main` keeps the final tree in the working directory, and you can
  commit it again step by step, staging by path.
- Read the branch the way the reviewer will: `git log --reverse --stat <base>..`, then each
  commit's diff. Check each commit for one concern, whether its message matches its diff, and
  whether a later commit undoes part of an earlier one.
- `git log --format=%s <base>.. | grep -E '^(fixup|squash|amend)! '` must print nothing. A
  fixup that was never folded in looks like a finished commit until someone reads the subject.

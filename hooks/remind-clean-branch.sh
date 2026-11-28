#!/usr/bin/env bash
#
# PreToolUse hook on Bash. When Claude is about to push a branch other than the default
# one (`git push`), remind it to read the branch as its reviewer will and fold any
# rework first, as guidelines/coding/git.md › Rebase and clean up before asking for
# review says. That pass is easy to skip when adding commits to a pull request already
# open, since nothing else marks the moment. It never blocks: whether the branch is
# clean is a judgment the reminder only prompts.
#
# Common wires it in its own .claude/settings.json too, since it does not load its own
# plugin; the guideline is then found under the project rather than the plugin.
#
# Try it:
#     echo '{"tool_input":{"command":"git push -u origin feat/x"}}' \
#       | CLAUDE_PROJECT_DIR="$PWD" bash hooks/remind-clean-branch.sh
#
# Written for bash 3.2, and without jq: the check only needs a match on the raw JSON, and
# a false match costs one extra reminder.
set -euo pipefail

push_command='(^|[^[:alnum:]_-])git[[:space:]]+push([^[:alnum:]_-]|$)'

event="$(cat)"
grep -qE "$push_command" <<<"$event" || exit 0

project_dir="${CLAUDE_PROJECT_DIR:-$PWD}"
branch="$(git -C "$project_dir" branch --show-current 2>/dev/null)" || exit 0
base="$(git -C "$project_dir" symbolic-ref -q --short refs/remotes/origin/HEAD 2>/dev/null || echo origin/main)"
[[ -z "$branch" || "$branch" == "${base#origin/}" ]] && exit 0

# A branch name or a path may hold a quote or a backslash, which would end the JSON
# string below early.
json_escape() { sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' <<<"$1"; }
branch="$(json_escape "$branch")"
base="$(json_escape "$base")"
guideline="$(json_escape "${CLAUDE_PLUGIN_ROOT:-$project_dir}/guidelines/coding/git.md")"
cat <<JSON
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": "Before pushing ${branch}, read it as its reviewer will: \`git log --reverse --stat ${base}..\`, then each diff. Fold any commit that reworks an earlier one into it (code, names or docs a later commit rewrites), and check each message still matches its diff, as ${guideline} › Rebase and clean up before asking for review says. This applies to commits added to a pull request already open too. If you have just done that pass, go ahead."
  }
}
JSON

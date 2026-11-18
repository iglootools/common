#!/usr/bin/env bash
#
# PreToolUse hook on Bash. When Claude is about to open a pull request, mark one ready for
# review or merge one (`gh pr create`, `gh pr ready`, `gh pr merge`), remind the user that
# /iglootools:audit-pr has not been run on the commit being submitted. It never blocks: the
# audit is a judgment call made at strategic points, not a gate.
#
# Stays quiet when a report under .iglootools/audits/ already covers HEAD, read from the
# report's "Scope: <n> commits, <base>..<head>" line. The check uses the current checkout,
# so `gh pr merge <number>` for another branch still gets the reminder.
#
# Pull requests opened from a terminal or from GitHub never pass through here; the reminder
# only covers the ones Claude handles.
#
# Try it:
#     echo '{"tool_input":{"command":"gh pr create --fill"}}' \
#       | CLAUDE_PROJECT_DIR="$PWD" bash hooks/remind-audit-pr.sh
#
# hooks.json already narrows the calls with `if` rules, but the docs call that matching
# best-effort, so the script checks the command again. Written for bash 3.2, and without jq:
# the check only needs a match on the raw JSON, and a false match costs one extra reminder.
set -euo pipefail

pr_command='(^|[^[:alnum:]_-])gh[[:space:]]+pr[[:space:]]+(create|ready|merge)([^[:alnum:]_-]|$)'

event="$(cat)"
grep -qE "$pr_command" <<<"$event" || exit 0

project_dir="${CLAUDE_PROJECT_DIR:-$PWD}"
head="$(git -C "$project_dir" rev-parse HEAD 2>/dev/null)" || exit 0

report_covers_head() {
  local audited
  # Every report's Scope line, reduced to the head SHA after "..".
  while IFS= read -r audited; do
    [[ -n "$audited" && "$head" == "$audited"* ]] && return 0
  done < <(
    cat "$project_dir"/.iglootools/audits/*.md 2>/dev/null \
      | sed -nE 's/^Scope: .*\.\.([0-9a-f]{7,40}).*/\1/p'
  )
  return 1
}

report_covers_head && exit 0

short="$(git -C "$project_dir" rev-parse --short HEAD)"
cat <<EOF
{
  "systemMessage": "iglootools: no /iglootools:audit-pr report covers ${short}. Consider running it before this pull request is reviewed or merged.",
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": "No /iglootools:audit-pr report under .iglootools/audits/ covers HEAD (${short}). Go ahead with the command, but tell the user, in your reply, that the branch has not been audited at this commit and that they can run /iglootools:audit-pr. Do not run the audit yourself unless they ask."
  }
}
EOF

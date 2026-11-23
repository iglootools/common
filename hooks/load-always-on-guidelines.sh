#!/usr/bin/env bash
#
# SessionStart hook. Its stdout is added to the session as context Claude can see, which is
# how the always-on guidelines reach a project without a clone of this repository: the
# `@../common/guidelines/coding/general.md` import this replaces resolved through a sibling
# directory, and ${CLAUDE_PLUGIN_ROOT} does not.
#
# Matched on startup|clear|compact, not resume or fork. A resumed or forked session still
# carries the earlier injection in its transcript, so re-emitting would only duplicate it; a
# compacted one may have had it summarized away, which is the case worth paying for.
set -euo pipefail

plugin_root="${CLAUDE_PLUGIN_ROOT:?this script only runs as a Claude Code plugin hook}"
project_dir="${CLAUDE_PROJECT_DIR:-$PWD}"

emit() {
  local path="$1"
  if [[ -r "$path" ]]; then
    cat -- "$path"
    printf '\n'
  else
    # Loud, not silent. A guideline that failed to load must not be indistinguishable from a
    # guideline that does not apply.
    printf 'ERROR: the iglootools plugin could not read %s.\n' "$path"
    printf 'Tell the user this guideline is missing rather than proceeding as though it does not apply.\n\n'
  fi
}

printf '# iglootools common guidelines\n\n'
printf 'Shared across iglootools projects and delivered by the iglootools plugin. These govern\n'
printf 'every edit. Each rule is a default: the terms for departing from one are in\n'
printf 'applying-the-guidelines.md, Documented Exceptions, below. The project'"'"'s own guidelines\n'
printf '(docs/guidelines.md or docs/guidelines/README.md) follow at the end when it has them.\n\n'
# The guideline files do not repeat, one per file, that they are defaults and where the
# reasoning lives: stating it once here reaches every session.
printf 'The reasoning behind these rules is in %s/guidelines/philosophy.md.\n\n' "$plugin_root"
# The paths matter: a relative link such as general.md's ../philosophy.md only resolves if you
# know which directory the file sits in.
printf 'applying-the-guidelines.md lives in %s/guidelines/, and the coding files below it in\n' "$plugin_root"
printf '%s/guidelines/coding/, where the relative links inside them resolve.\n\n' "$plugin_root"

emit "$plugin_root/guidelines/applying-the-guidelines.md"
emit "$plugin_root/guidelines/coding/general.md"
emit "$plugin_root/guidelines/coding/git.md"

# python.md is dead weight in a project with no Python code, and two of the iglootools
# projects have none. pyproject.toml no longer tells them apart: every project has one, to
# install the iglootools command (ADR-004). A tracked .py file does, and git answers before the
# session has understood anything about the task. Outside a git repository, pyproject.toml is
# the best guess left.
if python_files=$(git -C "$project_dir" ls-files -- '*.py' 2>/dev/null); then
  if [[ -n "$python_files" ]]; then
    emit "$plugin_root/guidelines/coding/python.md"
  fi
elif [[ -f "$project_dir/pyproject.toml" ]]; then
  emit "$plugin_root/guidelines/coding/python.md"
fi

# The project's own rules come last, because they override everything above. Naming the file
# was not enough: the shared rules were in context while code was being written and the
# override was not, so a project deviation was only noticed if the agent happened to go and
# read it. A missing file is not an error — it means the project documents no deviations.
#
# Only the entry file goes out in full: docs/guidelines.md, or docs/guidelines/README.md when
# the project splits its guidelines into a directory. Every line of it is paid for in every
# session, so anything long lives in another guidelines file, which is listed by path below
# and read when a change reaches what it governs.
project_guidelines=""
for candidate in docs/guidelines.md docs/guidelines/README.md; do
  if [[ -e "$project_dir/$candidate" ]]; then
    project_guidelines="$candidate"
    break
  fi
done

if [[ -n "$project_guidelines" ]]; then
  printf '# Project guidelines (%s)\n\n' "$project_guidelines"
  printf 'This project'"'"'s own rules, documented exceptions and checklists. Where they conflict with\n'
  printf 'the shared guidelines above, these win; a divergence they do not document is drift, not an\n'
  printf 'override. Read any document they link for an area in full before changing files there.\n\n'
  emit "$project_dir/$project_guidelines"
fi

# What a guidelines file governs follows from where it is: <dir>/guidelines.md and
# <dir>/guidelines/**/*.md cover everything under <dir>. Files under docs/guidelines/ cover what
# the entry file lists beside them, since docs/ is not the code they are about.
scope() {
  local path="$1"
  case "$path" in
    docs/guidelines/*) printf 'the paths %s lists beside it' "$project_guidelines" ;;
    guidelines.md | guidelines/*) printf 'the whole repository' ;;
    */guidelines.md) printf '%s/' "${path%/guidelines.md}" ;;
    *) printf '%s/' "${path%%/guidelines/*}" ;;
  esac
}

# Tracked files only: git already leaves out node_modules, build output and vendored trees, and a
# project that is not a git repository simply gets no list.
others=()
while IFS= read -r -d '' path; do
  case "$path" in
    "$project_guidelines") ;;
    guidelines.md | */guidelines.md | guidelines/*.md | */guidelines/*.md) others+=("$path") ;;
  esac
done < <(git -C "$project_dir" ls-files -z -- '*.md' 2>/dev/null || true)

if ((${#others[@]} > 0)); then
  printf '# Other project guidelines\n\n'
  printf 'Read each in full before changing anything it governs:\n\n'
  for path in "${others[@]}"; do
    # shellcheck disable=SC2016 # the backticks are Markdown code spans, not a substitution
    printf -- '- `%s`: %s\n' "$path" "$(scope "$path")"
  done
  printf '\n'
fi

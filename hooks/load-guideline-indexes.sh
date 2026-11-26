#!/usr/bin/env bash
#
# SessionStart hook. Its stdout is added to the session as context Claude can see, which is
# how the guidelines reach a project without a clone of this repository: ${CLAUDE_PLUGIN_ROOT}
# resolves only here, not in a project's CLAUDE.md or AGENTS.md.
#
# Only the indexes go out: guidelines/README.md and every directory's README.md, each a table
# of which file to read for which change. The guidelines themselves are read when a change
# reaches them, so a session pays for the map and for the files its work needs, not for every
# rule (ADR-005 in docs/architecture-decision-record.md).
#
# Matched on startup|clear|compact, not resume or fork. A resumed or forked session still
# carries the earlier injection in its transcript, so re-emitting would only duplicate it; a
# compacted one may have had it summarized away, which is the case worth paying for.
set -euo pipefail

plugin_root="${CLAUDE_PLUGIN_ROOT:?this script only runs as a Claude Code plugin hook}"
project_dir="${CLAUDE_PROJECT_DIR:-$PWD}"
guidelines="$plugin_root/guidelines"

emit() {
  local path="$1"
  if [[ -r "$path" ]]; then
    cat -- "$path"
    printf '\n'
  else
    # Loud, not silent. An index that failed to load must not be indistinguishable from
    # guidelines that do not apply.
    printf 'ERROR: the iglootools plugin could not read %s.\n' "$path"
    printf 'Tell the user this index is missing rather than proceeding as though it does not apply.\n\n'
  fi
}

# Each index's links are relative to its own directory, so it goes out under that directory's
# absolute path: otherwise a link such as general.md resolves against nothing.
emit_index() {
  local dir="$1"
  printf '## Index of %s/\n\n' "$dir"
  emit "$dir/README.md"
}

printf '# iglootools common guidelines\n\n'
printf 'Shared across iglootools projects and delivered by the iglootools plugin. Below are\n'
printf 'their indexes, not the rules: each row names the file to read for a kind of change.\n'
printf 'Before making a change, read in full every file its rows send you to, such as\n'
printf 'coding/general.md for any code change and coding/git.md before committing. Read the\n'
printf 'whole file, not the section that looks relevant: the guidelines are largely about\n'
printf 'silent failures, and the part that looks skippable is usually the one that names one.\n\n'
printf 'Each rule is a default. The project'"'"'s own guidelines, when it has them, follow at the\n'
printf 'end and override the shared ones, as applying-the-guidelines.md, Precedence, describes;\n'
printf 'departing from a rule is its Documented Exceptions section. The project'"'"'s own\n'
printf 'documents, from setup to its architecture, are indexed in its CONTRIBUTING.md.\n\n'

emit_index "$guidelines"
for dir in "$guidelines"/*/; do
  emit_index "${dir%/}"
done

# The project's own rules come last, because they override everything above. Naming the file
# was not enough: an override the agent only reads on demand is one it does not have in front
# of it while writing the code it overrides. A missing file is not an error — it means the
# project documents no deviations.
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
  printf 'This project'"'"'s own rules, documented exceptions and checklists. They take precedence\n'
  printf 'over the shared guidelines above. Read any document they link for an area in full before\n'
  printf 'changing files there.\n\n'
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

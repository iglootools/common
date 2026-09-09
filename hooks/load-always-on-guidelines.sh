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
printf 'Shared across iglootools projects and delivered by the iglootools plugin. These\n'
printf 'govern every edit. Where the project documents a deviation in its own docs/guidelines.md,\n'
printf 'the project wins; undocumented divergence is drift, not an override.\n\n'
# The guideline files no longer repeat, one per file, that they are defaults and where the
# reasoning lives. Stating it here is the always-on equivalent of stating it once in the
# README, which a consumer session never sees.
printf 'The reasoning behind these rules is in %s/philosophy.md, and the terms for departing\n' "$plugin_root"
printf 'from one are in %s/README.md#applying-these-guidelines.\n\n' "$plugin_root"
# guidelines/, not the plugin root: these files sit one directory down, and a relative link such
# as general.md's ../../README.md only resolves if you know that.
printf 'These files live in %s/guidelines/coding/, where the relative links inside them resolve.\n\n' "$plugin_root"

emit "$plugin_root/guidelines/coding/general.md"

# python.md is dead weight in a project with no Python, and two of the iglootools projects
# have none. The presence of pyproject.toml is a check the session can make before it has
# understood anything about the task.
if [[ -f "$project_dir/pyproject.toml" ]]; then
  emit "$plugin_root/guidelines/coding/python.md"
fi

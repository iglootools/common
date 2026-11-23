# Auditing the consistency of an area across the iglootools repositories

Shared by every `audit-consistency-*` skill under `.claude/skills/`. Each skill
names its area, the files on common's side and on a project's, and how to split
the passes, then follows these steps. A new area is a new skill that does the
same. The categories, severities and the format the auditors
return are in `.claude/agents/consistency-auditor.md`: read it before step 3.

The audit reports and changes nothing. Fixing is a separate step, asked for by
finding ID.

## 1. Find the repositories

1. Run from common's checkout: `git remote get-url origin` names
   `iglootools/common`. Otherwise say so and stop.
2. The workspace is the directory common's checkout sits in. The projects are
   every direct subdirectory, dot-directories included (a `*/` glob misses
   `.github`), that is a git checkout whose `origin` is a
   repository of the iglootools organization (`github.com:iglootools/` or
   `github.com/iglootools/`), other than common, which is a project too when
   the skill says its own files follow the area's guidelines like any other.
   Narrow them to the names given in the arguments, if any, and say which names
   matched nothing.
3. For common and each project, record: the short `HEAD` SHA, the branch, and
   whether `git status --porcelain` shows changes to a file in scope. For each
   project, also record the release of common it pins (the
   `iglootools @ git+https://github.com/iglootools/common@v<version>` dependency
   in `pyproject.toml`), or `none`.
4. Files are audited as they are in the working tree. A repository on a branch
   other than its default, or with uncommitted changes to a file in scope, is
   flagged in the report's header, since its findings may not hold on `main`.
5. List each repository's files in scope with `git ls-files`, using the globs
   the skill gives. A project with none is listed under "Not audited" as "no
   files in scope", not passed over.

## 2. Choose the categories

All five in `consistency-auditor.md` (`CONFLICT`, `STALE`, `DUP`, `PROMOTE`,
`DIVERGE`), unless the arguments narrow them with `only:` or `skip:`. A
category left out on request goes under "Not audited" as "not requested".

## 3. Start the auditors

Start every pass the skill defines in one message, so they run in parallel, with
the Agent tool and `subagent_type: "consistency-auditor"`. Keep the total at ten
or fewer: with more projects than that allows, give one auditor several
projects. Each prompt carries only the assignment:

```text
Mode: audit
Area: <the area, and the area notes from the skill>
Pass: <common | project <name> | cross-project>
Categories: <the IDs this pass owns, among those chosen>
Repositories:
- <name>: <absolute path>, pins common v<version>, files: <the files in scope>
```

Give every pass common's line, since every pass compares against it.

## 4. Check every reply

Each reply must hold zero or more ```` ```finding ```` blocks and exactly one
```` ```coverage ```` block, with every field the format requires. When one is
malformed, send that auditor one message (SendMessage) asking it to resend in
the required format. If the second reply is still unusable, list its pass under
"Not audited" with the reason. Never drop it silently.

Then turn each `outside-pass` note into a finding when it falls in a category
this audit runs and no pass reported it: read the passages it points at, and
write the finding in the auditor's format, `plausible` unless the text settles
it. Keep the rest for "Outside the scope".

## 5. Verify the high findings

Send every `high` finding to a fresh auditor in `verify` mode, all in one
message, grouped by the pass that reported them, with the same `Area` and
`Repositories` lines and the finding blocks verbatim. Drop each finding that
comes back `rejected`, and count it for the header. Set each `upheld` finding's
confidence to the verifier's. A finding whose verifier failed is set to
`plausible` and marked unverified in the header, as `guidelines/review/audit.md`
› Mark confidence asks.

When a verifier rejects a finding because the real problem is elsewhere, such
as a contradiction between two shared guidelines rather than a project's
departure from one, write that problem as a finding of its own, where it lies:
`plausible` unless the verifier's reading settles it. Say in the header which
rejected finding it came from.

## 6. Merge duplicates

Two findings are one when they name the same passages and the same problem,
which happens where passes meet: a project pass's `DUP` and the cross-project
pass's `PROMOTE` on one rule. Decide by what common holds: present in common is
a `DUP`, absent is a `PROMOTE`. Keep the higher severity, and fold the other's
locations and detail in.

## 7. Assign IDs

Order the categories as the table in `consistency-auditor.md` does. Within a
category, sort by severity, then `confirmed` before `plausible`, then the first
repository in `fix-in`, then location, and number from 1: `CONFLICT-1`,
`DUP-3`.

## 8. Write the report

Write it to `.iglootools/audits/<timestamp>-consistency-<area>.md` in common's
checkout, with the timestamp from `date -u +%Y%m%dT%H%M%SZ`. Add `-2`, `-3`, …
when the file exists. Then check it is ignored:
`git check-ignore -q <file>`, and say so in the reply if it is not.

Write no line starting with `Scope:`: the plugin's audit-pr reminder hook reads
such a line in any report under `.iglootools/audits/` as a branch audit of that
commit.

Lay it out as `guidelines/review/audit.md` › Lay the report out for navigating
says, for IDs, explicit anchors (`<a id="DUP-3">`) and statuses, with these
parts:

- **Header**: the area; the date; common's short SHA and plugin version (from
  `.claude-plugin/plugin.json`); a table of the projects with their SHA,
  branch, pinned release and any flag from step 1; the categories; the number
  of auditors; and the verification counts (upheld, rejected, unverified).
- **Summary**: a table of counts by category and severity, then "No findings
  in" and "Not audited".
- **By repository**: each repository, and the IDs whose `fix-in` names it, so
  the fixes for one checkout can be asked for together.
- **Index**, then **one section per category** with findings. Each finding has
  its severity, confidence, every location, the detail, the rule, the fix,
  `Fix in`, and `Status: open`.
- **Outside the scope**, when notes remain from step 4: a location and one line
  each, with no ID.

Links:

- A location links relative to the report: `../../<path>#L<line>` in common,
  `../../../<project>/<path>#L<line>` in a project (`#L<start>-L<end>` for a
  range).
- A rule links to
  `https://github.com/iglootools/common/blob/main/guidelines/<file>#<anchor>`,
  with the anchor derived from the heading as the auditor's format says. Check
  the heading exists in common's checkout; when it does not, link the file
  alone.
- Passages, titles and paths are text, not Markdown: escape `|` in table cells,
  and put code, paths and identifiers in backticks.

## 9. Reply

Do not paste the report. Reply with:

- the report's path, as a link;
- the summary table and the "By repository" table;
- one line per `high` finding: ID, title, repositories;
- anything under "Not audited";
- how to continue: ask for findings by ID, category or repository ("fix
  CONFLICT-1", "fix all DUP in nbkp"). Each repository's fixes are made in its
  own checkout, on its own branch and pull request. A `PROMOTE` lands in common
  first, is released and adopted, and only then is each project's copy
  removed, so no project is left without the rule.

Do not start fixing anything until asked. When a fix lands, update the
finding's status as `guidelines/review/audit.md` › Update the finding's status
with the fix says; a finding answered by a documented exception or
`won't fix: <reason>` stays in the report.

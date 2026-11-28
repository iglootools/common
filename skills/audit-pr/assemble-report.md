# Running the auditors and assembling the report

Shared by `audit-pr`, `audit-pr-stack` and `audit-full`. Each skill decides the
scope and how to split the categories across auditors, then follows these steps.
The categories, severities, report layout and fixing rules are in
`${CLAUDE_PLUGIN_ROOT}/guidelines/review/audit.md` — read it in full before step
1 if it is not already in context.

## 1. Start the auditors

Start every auditor in one message, so they run in parallel, with the Agent tool
and `subagent_type: "iglootools:auditor"`. The auditor knows how to audit and
what to return; its prompt carries only the assignment:

```text
Mode: audit
Scope: <the branch range with its commit list and changed files, or the paths to cover>
Base: <base SHA, for a branch range>
Categories: <the IDs this auditor owns>
Repository root: <absolute path>
```

## 2. Check every reply

Each reply must hold zero or more ```` ```finding ```` blocks and exactly one
```` ```coverage ```` block, with every field the auditor's format requires.
When a reply is malformed or has no coverage block, send that auditor one
message (SendMessage) asking it to resend its findings in the required format.
If the second reply is still unusable, list its categories under "Not audited"
with the reason. Never drop them silently.

Collect each coverage block's `not-audited`, `checks-run` and `outside-scope`
entries.

## 3. Turn in-scope notes into findings

An auditor's `outside-scope` notes are problems it noticed but did not own. A
note about code inside this audit's scope, in a category the audit runs, was
outside only that auditor's categories, and the auditor that owned the category
did not report it. Promote it to a finding, or it would be left without an ID
and could not be fixed by ID:

- Skip it when it duplicates a finding already reported, by location and root
  cause.
- Otherwise, read the code it points at and write a finding block for it in the
  category the note names, or the one that fits if the note named none. Use
  `confidence: plausible`, unless reading the code settled it, and choose the
  severity as `audit.md` defines it.
- A promoted `critical` or `high` finding goes through the next step with the
  others.

Keep in "Outside the scope" only the notes about code this audit did not cover:
another repository, paths outside the scope, or a category the audit did not
run.

## 4. Verify critical and high findings

Send every `critical` and `high` finding to a fresh auditor in `verify` mode,
grouped by the auditor that reported them, all in one message:

```text
Mode: verify
Repository root: <absolute path>
Base: <base SHA, for a branch range>
Findings:
<the finding blocks, verbatim>
```

Drop each finding that comes back `rejected`, and count it for the report
header. Set the confidence of each `upheld` finding to the one the verifier
gives. A finding whose verifier failed is set to `plausible`, as `audit.md` ›
Mark confidence asks of a finding that was not proven, and is noted in the
header as unverified.

## 5. Merge duplicates

Two findings are one when their locations overlap and they describe the same
root cause, which happens where categories meet (an unescaped shell argument is
both `SEC` and `ERR`). Keep one: the higher severity, and that finding's
category. Fold the other's scenario into it.

## 6. Assign IDs

Order the categories as the table in `audit.md` does. Within a category, sort by
severity, then `confirmed` before `plausible`, then location, and number from 1:
`SEC-1`, `SEC-2`, …

## 7. Write the report

Write it to `.iglootools/audits/<timestamp>-<scope>.md` at the repository root,
with the timestamp from `date -u +%Y%m%dT%H%M%SZ`, as `audit.md` names it, and
the scope the skill names. Add `-2`, `-3`, … when the file exists. Follow the
layout in `audit.md` exactly:

- Header: what was audited (range and commit count, or the paths at a SHA), the
  categories, the number of auditors, the plugin version, and the verification
  counts (upheld, rejected, unverified). Then the line pointing to `audit.md`'s
  "Fixing findings" section, linked as
  `https://github.com/iglootools/common/blob/iglootools--v<version>/guidelines/review/audit.md#fixing-findings`.
- Summary table with counts, "No findings in" and "Not audited", then the index,
  then one section per category that has findings, then "Outside the scope" when
  notes remain there after step 3.
- Locations link as `../../<path>#L<line>` (`#L<start>-L<end>` for a range).
- A shared rule links to
  `https://github.com/iglootools/common/blob/iglootools--v<version>/guidelines/<file>#<anchor>`,
  and a project rule to `../../<project guidelines file>#<anchor>`, the file the
  finding cites. The anchor is the cited heading as GitHub derives it: lower
  case, punctuation other than `-` removed, spaces replaced by `-`, so
  `Fold rework into the commit it corrects` becomes
  `fold-rework-into-the-commit-it-corrects`. Check that the heading exists in
  the file, which is in the plugin directory for a shared rule. When it does
  not, link the file without an anchor rather than to an anchor that leads
  nowhere.
- Titles, scenarios and paths are text from the code, not Markdown. Escape `|`
  in table cells, and put code, paths and identifiers in backticks, so a name
  like `a|b` or `<tag>` does not break the table or disappear.
- `Origin` is `introduced in <sha>` or `pre-existing` for `audit-pr` and
  `audit-pr-stack`. Leave it out for `audit-full`.
- Every finding's status starts as `open`.

Then check that the report is ignored by git:
`git check-ignore -q .iglootools/audits/<file>`. If it is not, say so in your
reply and suggest adding `.iglootools/` to the committed `.gitignore`. Do not
edit `.gitignore` yourself, as `audit.md` › Report problems; fix them only
when asked says.

## 8. Reply

Do not paste the report. Reply with:

- the report's path, as a link;
- the summary table;
- one line per `critical` and `high` finding: ID, title, location;
- anything under "Not audited";
- how to continue: ask for findings by ID, category or severity ("fix SEC-1
  ERR-2", "fix all high"), and they will be fixed following the report's "Fixing
  findings" section.

Do not start fixing anything until asked.

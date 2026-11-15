# Running the auditors and assembling the report

Shared by `audit-pr` and `audit-full`. Each skill decides the scope and how to split the
categories across auditors, then follows these steps. The categories, severities, report layout
and fixing rules are in `${CLAUDE_PLUGIN_ROOT}/guidelines/review/audit.md` — read it in full
before step 1 if it is not already in context.

## 1. Start the auditors

Start every auditor in one message, so they run in parallel, with the Agent tool and
`subagent_type: "iglootools:auditor"`. The auditor knows how to audit and what to return; its
prompt carries only the assignment:

```
Mode: audit
Scope: <the branch range with its commit list and changed files, or the paths to cover>
Base: <base SHA, for a branch range>
Categories: <the IDs this auditor owns>
Repository root: <absolute path>
```

## 2. Check every reply

Each reply must hold zero or more ```` ```finding ```` blocks and exactly one
```` ```coverage ```` block, with every field the auditor's format requires. When a reply is
malformed or has no coverage block, send that auditor one message (SendMessage) asking it to
resend its findings in the required format. If the second reply is still unusable, list its
categories under "Not audited" with the reason. Never drop them silently.

Collect each coverage block's `not-audited`, `checks-run` and `outside-scope` entries for the
report.

## 3. Verify critical and high findings

Send every `critical` and `high` finding to a fresh auditor in `verify` mode, grouped by the
auditor that reported them, all in one message:

```
Mode: verify
Repository root: <absolute path>
Base: <base SHA, for a branch range>
Findings:
<the finding blocks, verbatim>
```

Drop each finding that comes back `rejected`, and count it for the report header. Set the
confidence of each `upheld` finding to the one the verifier gives. A finding whose verifier
failed keeps its original confidence and is noted in the header as unverified.

## 4. Merge duplicates

Two findings are one when their locations overlap and they describe the same root cause, which
happens where categories meet (an unescaped shell argument is both `SEC` and `ERR`). Keep one: the
higher severity, and that finding's category. Fold the other's scenario into it.

## 5. Assign IDs

Order the categories as the table in `audit.md` does. Within a category, sort by severity,
then `confirmed` before `plausible`, then location, and number from 1: `SEC-1`, `SEC-2`, …

## 6. Write the report

Write it to `.iglootools/audits/<date>-<scope>.md` at the repository root, with the date from
`date -u +%F` and the scope the skill names. Add `-2`, `-3`, … when the file exists. Follow the
layout in `audit.md` exactly:

- Header: what was audited (range and commit count, or the paths at a SHA), the categories, the
  number of auditors, the plugin version, and the verification counts (upheld, rejected,
  unverified). Then the line pointing to `audit.md`'s "Fixing findings" section, linked as
  `https://github.com/iglootools/common/blob/iglootools--v<version>/guidelines/review/audit.md#fixing-findings`.
- Summary table with counts, "No findings in" and "Not audited", then the index, then one
  section per category that has findings, then "Outside the scope" when any auditor listed
  something there.
- Locations link as `../../<path>#L<line>` (`#L<start>-L<end>` for a range).
- A shared rule links to
  `https://github.com/iglootools/common/blob/iglootools--v<version>/guidelines/<file>`; a
  project rule links to `../../docs/guidelines.md`.
- Titles, scenarios and paths are text from the code, not Markdown. Escape `|` in table cells,
  and put code, paths and identifiers in backticks, so a name like `a|b` or `<tag>` does not
  break the table or disappear.
- `Origin` is `introduced in <sha>` or `pre-existing` for `audit-pr`. Leave it out for
  `audit-full`.
- Every finding's status starts as `open`.

Then check that the report is ignored by git:
`git check-ignore -q .iglootools/audits/<file>`. If it is not, say so in your reply and suggest
adding `.iglootools/` to the committed `.gitignore`. Do not edit
`.gitignore` yourself: an audit reports, it does not change the project.

## 7. Reply

Do not paste the report. Reply with:

- the report's path, as a link;
- the summary table;
- one line per `critical` and `high` finding: ID, title, location;
- anything under "Not audited";
- how to continue: ask for findings by ID, category or severity ("fix SEC-1 ERR-2",
  "fix all high"), and they will be fixed following the report's "Fixing findings" section.

Do not start fixing anything until asked.

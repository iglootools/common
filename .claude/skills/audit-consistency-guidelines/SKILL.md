---
description: Audit the shared guidelines in this repository against every iglootools project's own (AGENTS.md, CONTRIBUTING.md, docs/guidelines.md and every other guidelines file) for contradictions, stale exceptions and links, rules restated instead of cited, rules several projects carry that common lacks, and questions the projects answer differently, with parallel auditors, and write a report with an ID for every finding.
argument-hint: "[project ...] [only:CAT,CAT | skip:CAT,CAT]"
disable-model-invocation: true
---

Audit the consistency of the guidelines across the iglootools repositories.
Arguments: $ARGUMENTS

Follow `.claude/audit-consistency/procedure.md` with what this file sets out.
The area is `guidelines`, and common is not audited as a project: its
guidelines are the shared side.

## Files in scope

- **Common's side**: `guidelines/**/*.md`; the plugin's prompts that route to
  them, `skills/**/*.md`, `agents/*.md` and `hooks/*.sh`, which must cite the
  guidelines rather than restate them; and common's own `AGENTS.md` and
  `CONTRIBUTING.md`.
- **A project's side**: `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`,
  `docs/guidelines.md`, `docs/guidelines/**/*.md`, every other `guidelines.md`
  and `guidelines/**/*.md`, `.claude/skills/**/SKILL.md` and
  `.claude/agents/*.md`.

Config-level exceptions, such as a `# noqa` with its reason or a commented ruff
ignore, are out of scope here: `audit-consistency-build` covers the build files,
and `/iglootools:audit-full` the code.

## Area notes

Pass these to every auditor as the `Area` line:

```text
guidelines. Read guidelines/documentation/layout.md (where a project keeps its
guidelines, and Keep AGENTS.md a short map) and guidelines/documentation/types.md
(Give each fact one home, and link to it). A project cites a shared rule with a
one-line link into github.com/iglootools/common/blob/main/guidelines/.
The plugin's skills, agents and hooks route to guideline files and must
restate no rule. A project's AGENTS.md is a map: any rule in it is a DUP of the
guideline that owns it, or a rule in the wrong place.
```

## Passes

Start these, each with the categories chosen in the procedure's step 2 that it
owns:

| Pass | Categories | Repositories |
|---|---|---|
| `common` | `CONFLICT`, `DUP` | common |
| `project <name>`, one per project with files in scope | `CONFLICT`, `STALE`, `DUP` | common and that project |
| `cross-project` | `PROMOTE`, `DIVERGE` | common and every project |

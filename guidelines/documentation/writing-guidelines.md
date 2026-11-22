# Writing Guidelines

How to write a rule: in the shared guidelines, and in a project's guidelines
files at the paths
[layout.md](layout.md#keep-the-projects-guidelines-at-conventional-paths-and-the-entry-file-lean)
names. Read it before adding or reworking a rule. Rules are one of the
[documentation types](types.md), so the rules for
[every kind](types.md#every-kind) apply too. `philosophy.md` is an
[explanation](types.md#explanation), and these rules do not apply to it.

<!-- toc -->
**On this page**

- [Shape](#shape)
  - [Name the files or changes the guideline governs in its opening](#name-the-files-or-changes-the-guideline-governs-in-its-opening)
  - [Head each rule with the rule itself](#head-each-rule-with-the-rule-itself)
  - [Write one idea per sentence](#write-one-idea-per-sentence)
- [Reasons](#reasons)
  - [State the rule, then why, then the details](#state-the-rule-then-why-then-the-details)
  - [Say how firmly a rule holds](#say-how-firmly-a-rule-holds)
  - [Move a long why out of the rule](#move-a-long-why-out-of-the-rule)
- [Ownership](#ownership)
  - [Own each rule in one file, and cite it everywhere else](#own-each-rule-in-one-file-and-cite-it-everywhere-else)
  - [Let a check hold what a check can enforce](#let-a-check-hold-what-a-check-can-enforce)
  - [Register a new or renamed guideline in every index that routes to it](#register-a-new-or-renamed-guideline-in-every-index-that-routes-to-it)
  - [Keep the always-on guidelines to what every change needs](#keep-the-always-on-guidelines-to-what-every-change-needs)
  - [Leave out what is not a rule](#leave-out-what-is-not-a-rule)
<!-- tocstop -->

## Shape

### Name the files or changes the guideline governs in its opening

For a guideline,
[Open with who it is for and what it answers](types.md#open-with-who-it-is-for-and-what-it-answers)
means that the first paragraph names the files or changes it governs and the
moment to read it. The table of contents follows.

**Why:** a person deciding whether the guideline applies to their change, and
the `guidelines` skill deciding when to load it, both read that paragraph first.
A vague one sends them past a guideline they needed, or into one they did not.

### Head each rule with the rule itself

Each `###` heading is the rule, stated in the imperative: "Name tasks by
family", not "Task naming".

**Why:** the table of contents becomes the full list of rules, readable without
opening a section, and a link to the rule tells the reader what the rule says.

### Write one idea per sentence

Use bullets for parallel cases and tables for mappings.

**Why:** a sentence carrying two ideas hides the second, and a list of cases in
prose cannot be scanned.

## Reasons

### State the rule, then why, then the details

Each rule follows the same shape:

```markdown
### Pin every action to a commit SHA

One to three sentences stating the rule precisely enough to follow it.

**Why:** what breaks, or what is lost, when it is not followed, in one or two
sentences. [Rationale](#pin-every-action-to-a-commit-sha-1) when it needs more.

- The specifics: the cases, the commands, the exceptions already known.
```

**Why:** a reader who wants only what to do reads the statement and the details.
One who is weighing an exception reads the labelled line. Neither has to dig the
other out of a paragraph. Why every rule carries a reason at all is in
[A rule carries its reason](../philosophy.md#a-rule-carries-its-reason).

### Say how firmly a rule holds

Every shared rule is a default, departed from as
[Documented Exceptions](../coding/general.md#documented-exceptions) describes.
Do not repeat that in each file. The **Why:** line already calibrates the rule.
Where breaking it is never acceptable, for instance because the failure is
silent or a security risk, say so. Where an exception is already known, list
it with the rule.

**Why:** a reason that names a silent failure reads as firm, and one that names
consistency reads as negotiable. A reader can only weigh an exception against a
reason they can see, as
[A rule carries its reason](../philosophy.md#a-rule-carries-its-reason) argues.

### Move a long why out of the rule

When the reason needs more than two sentences, give it a `###` of the same name
under a `## Rationale` section at the end of the file, and link to it from the
rule's **Why:** line. Reasoning that more than one guideline rests on goes in
[philosophy.md](../philosophy.md) instead, and each guideline links to it.

**Why:** the rules stay compact enough to scan, and the argument is still one
click away for the reader who needs it.

## Ownership

### Own each rule in one file, and cite it everywhere else

This is
[Give each fact one home](types.md#give-each-fact-one-home-and-link-to-it)
applied to rules. State a rule in the guideline whose trigger covers it. Any
other guideline that touches the subject cites it in one line, linking to the
section: "Name the task as
[mise.md › Name tasks by family](../project-setup/mise.md#name-tasks-by-family)
describes." Do not summarize it. If the other file's readers need the rule in
front of them, route them to both files from the `guidelines` skill rather than
copying the rule.

**Why:** a summary is a copy, and copies drift without anything failing. The
reader cannot tell which version wins.

### Let a check hold what a check can enforce

When a tool, a test or a `lint-*` task enforces a rule, the guideline states the
rule, names the check and the task that fixes it, and stops. The check's
configuration is the specification. When nothing enforces it yet, look for a way
to add a check before settling for prose: a linter rule or its configuration, an
import contract, a test, a `lint-*` task, or a small `iglootools` command such
as `common check-pins`.

**Why:** prose that spells out what a check enforces is a second copy of the
check. When the check changes, the prose quietly goes wrong. A rule held only in
prose is applied unevenly and drifts without anything failing, while a check
corrects every contributor on every change, as
[Invest in the harness](../philosophy.md#invest-in-the-harness-not-in-the-instructions)
argues.

- When a check is out of reach (it would need judgement, or cost more than the
  mistakes it catches), keep the rule in prose.

### Register a new or renamed guideline in every index that routes to it

Give it one line in its directory's `README.md`, written as
[maps](types.md#say-when-to-go-there-not-what-is-inside) are: the change that
should send a reader there. Then register it where agents are routed to it: the
`guidelines` skill's routing table for a file under `project-setup/` or
`documentation/`, the `SessionStart` hook for a file under `coding/`, the
auditor agent for one under `review/`. A new directory, or a file at the top of
`guidelines/`, also gets a line in `guidelines/README.md`. Update every one when
the file is renamed or its trigger changes. `mise run test` fails on a guideline
missing from any of them (`tests/test_guideline_indexes.py`).

**Why:** the skill reads only the files its table lists, and readers find the
rest through the indexes, so an unregistered guideline exists without ever being
read.

### Keep the always-on guidelines to what every change needs

The shared `coding/general.md`, `coding/git.md` and `coding/python.md`, and each
project's entry file (`docs/guidelines.md`, or `docs/guidelines/README.md`), go
into every agent session. A rule there must apply to every change in its scope.
A rule about particular files belongs in the guideline those files trigger, and
anything long moves to a file of its own, linked from the entry file.

**Why:** a line in an always-on file is read in every session, by readers who do
not need it.

### Leave out what is not a rule

- **No history.** What changed, and when, belongs in the commit or the
  decision record. Keep a line about the old way only when it prevents a
  return to it, and then write it as the reason.
- **No hedging, and no addressing an agent.** Write the rule for a person
  ([Documentation for people first](../philosophy.md#documentation-for-people-first-agent-configuration-for-the-gaps)).
  Which file an agent reads, and when, is for the skill and the hooks to
  decide.
- **Move what is not a rule to where it belongs**: an argument to the
  `## Rationale` section or `philosophy.md`, a procedure or a reference to the
  project's `docs/`, and a description of how a tool works to its code.

**Why:** length hides the rule. The always-on guidelines are paid for in every
session, and the others each time they are read.

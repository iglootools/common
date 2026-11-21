# Documentation Types

The kinds of document an iglootools project writes, and what makes each one
good. Read it before writing a document or reworking one. Where each document
lives and what it is named is in [layout.md](layout.md); how a guideline is
written is in [writing-guidelines.md](writing-guidelines.md).

<!-- toc -->
**On this page**

- [The kinds](#the-kinds)
- [Every kind](#every-kind)
  - [Write one kind per document](#write-one-kind-per-document)
  - [Open with who it is for and what it answers](#open-with-who-it-is-for-and-what-it-answers)
  - [Give each fact one home, and link to it](#give-each-fact-one-home-and-link-to-it)
  - [Use real examples](#use-real-examples)
- [Map](#map)
  - [Say when to go there, not what is inside](#say-when-to-go-there-not-what-is-inside)
  - [Start each link's description with its kind's verb](#start-each-links-description-with-its-kinds-verb)
- [Tutorial](#tutorial)
  - [Follow one realistic path, end to end](#follow-one-realistic-path-end-to-end)
- [How-to guide](#how-to-guide)
  - [Get a reader who knows the goal through one task](#get-a-reader-who-knows-the-goal-through-one-task)
- [Reference](#reference)
  - [Describe everything, the same way for each entry](#describe-everything-the-same-way-for-each-entry)
- [Explanation](#explanation)
  - [Answer one question, with the reasoning beside it](#answer-one-question-with-the-reasoning-beside-it)
- [Rules](#rules)
- [Record](#record)
  - [Keep what was decided or done, as it was at the time](#keep-what-was-decided-or-done-as-it-was-at-the-time)
<!-- tocstop -->

## The kinds

A document's kind is set by what its reader came to do:

| Kind | The reader wants to | In iglootools projects |
|---|---|---|
| [Map](#map) | find where something is | `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, each `guidelines/*/README.md` |
| [Tutorial](#tutorial) | learn by doing, start to finish | nbkp's `tutorial.md` |
| [How-to guide](#how-to-guide) | follow the steps of a known task | `installation.md`, `usage.md`, `setup-development-environment.md`, `releasing-and-publishing.md`, network-infra's `operations.md` |
| [Reference](#reference) | look up an exact fact | `cli-reference.md`, `config-reference.md`, `features.md` |
| [Explanation](#explanation) | understand what something is and why it works that way | `domain.md`, `architecture.md`, `internals.md`, `philosophy.md` |
| [Rules](#rules) | know what a change must respect | the shared guidelines, `docs/guidelines.md` or `docs/guidelines/`, a subsystem's `guidelines.md` |
| [Record](#record) | find out what was decided or done, and why | `architecture-decision-record.md`, `divergence-from-the-template.md`, network-infra's host log |

The first five are [Diátaxis](https://diataxis.fr/)'s four kinds plus the maps
that link them; rules and records are what a codebase adds. Posts written for
an outside venue, such as nbkp's `marketing/`, follow the venue rather than this
file.

**Why:** each intent wants a different shape, and a document serving two serves
both badly. The full argument is in
[Write for one reader with one intent](../philosophy.md#write-for-one-reader-with-one-intent).

## Every kind

### Write one kind per document

Give each document one kind. A short section of another kind can stay. When it
grows, move it into a document of its own and link to it.

**Why:** a section of another kind grows unnoticed until the document has two
readers and serves neither. nbkp's `usage.md` grew an installation section,
which then duplicated `installation.md`.

### Open with who it is for and what it answers

The first sentence names the reader and the question. The next ones link to the
neighbouring documents for what this one leaves out.

**Why:** the reader learns in two lines whether they are in the right place,
rather than three screens in.

### Give each fact one home, and link to it

Exhaustive lists live in the reference, the domain's concepts in `domain.md`,
and a rule in the one guideline that owns it. Every other document links there
instead of restating it.

**Why:** a copy drifts, and nothing fails when it does. See
[State each fact once](../philosophy.md#state-each-fact-once).

### Use real examples

Take each example from a working setup or command: short, copyable, and shown
with its real output. Link to the live file when it is long.

**Why:** a real example has been run, so it is correct the day it is written,
and wrong in a way someone will notice later.

## Map

### Say when to go there, not what is inside

A map lists where each thing is, one line per destination, saying when to go
there rather than what is inside. It fits on a screen, and holds no content of
its own. The README is the one exception: it also makes the case for the
project, which
[layout.md](layout.md#make-the-readme-a-pitch-that-links-out) spells
out. A map groups its links by the reader's journey, not by kind; which maps a
project has is set by [layout.md](layout.md).

**Why:** everyone reads a map first, so every line in it costs every reader, and
any content it holds is a second copy of something else.

### Start each link's description with its kind's verb

Each line says when to go there with the verb of the destination's kind, from
[the table](#the-kinds): *learn* for a tutorial, *follow* for a how-to guide,
*look up* for a reference, *understand* for an explanation,
*know what … must respect* for rules, *find out* for a record, and *find* for
another map. The `CONTRIBUTING.md` scaffold in
[layout.md](layout.md#split-readmemd-contributingmd-and-docs-by-reader) shows
it:

```markdown
- [docs/domain.md](docs/domain.md) — understand the domain concepts and how they relate
- [docs/config-reference.md](docs/config-reference.md) — look up every configuration field
```

**Why:** the reader learns what the document will do for them without knowing
the kinds' names, and the verb matches the document's own
[opening sentence](#open-with-who-it-is-for-and-what-it-answers).

## Tutorial

### Follow one realistic path, end to end

- **It does not branch.** Alternatives and options belong in the how-to guides,
  linked at the end.
- **Every step shows what the reader should see**, so a learner knows the step
  worked before moving on.
- **It explains just enough to continue**, and links to the explanation for the
  rest.
- **It is rerun end to end** whenever the commands it uses change.

**Why:** a learner cannot choose between alternatives yet, and a tutorial that
breaks at step seven loses them for good.

## How-to guide

### Get a reader who knows the goal through one task

- **Title each section by its task**: "Release a version", "Initializing a
  drive".
- **State the prerequisites first, then the steps as commands to copy, then how
  to check the result.**
- **Mark every step that writes or destroys**, and say how to recover from it,
  as network-infra's `operations.md` does with `# writes` and its ⚠️ callouts.
- **Record the dead ends.** For what does not work, give the command that would
  show it has changed: alberta-hiking-resources'
  [StackBlitz section](https://github.com/iglootools/alberta-hiking-resources/blob/main/docs/setup-development-environment.md#stackblitz-does-not-currently-work).

**Why:** the reader is mid-task and copying commands, so an ambiguous step costs
a mistake, not just time.

## Reference

### Describe everything, the same way for each entry

- **Complete, and generated from the code wherever it can be**, as
  [layout.md](layout.md#generate-references-from-the-code-and-check-them)
  describes.
- **One structure per entry**: name, type, default, allowed values, an example.
- **It describes, and does not instruct or argue.** It links to the how-to
  guides for tasks and to the explanation for reasons.

**Why:** a reader trusts a reference only while it is complete. One missing
option sends them to the code, and then for every option after that.

## Explanation

### Answer one question, with the reasoning beside it

An explanation answers *what* the project models (`domain.md`), *where* its code
lives (`architecture.md`), or *how* and *why* it behaves as it does
(`internals.md`):

- **It uses the domain's vocabulary**, defined once in `domain.md`'s glossary.
- **It puts the reasoning next to what it explains**, as `Why …` subsections. A
  decision that spans components goes in the [record](#record) instead.
- **It draws a diagram where the structure matters more than the sequence.**

**Why:** the explanation is what keeps the next change consistent with the
design. Without it, every contributor re-derives the design from the code, and
some derive a different one.

## Rules

Rules say what a change must respect: the shared guidelines, a project's
`docs/guidelines.md`, its area conventions and its checklists. They are written
as [writing-guidelines.md](writing-guidelines.md) describes.

## Record

### Keep what was decided or done, as it was at the time

- **Append, never rewrite.** Add new entries at the end, dated. A changed
  decision is a new entry that supersedes the old one.
- **Each entry gives the context, the decision, the reason and the
  consequences**, and names what would retire it. The ADR format is in
  [layout.md](layout.md#record-architectural-decisions-in-an-append-only-log).
- **Log what was done, not what was meant**: a host log lists the commands as
  they were run.

**Why:** a record is worth keeping for what was believed when the decision was
made. An edited record turns into an explanation that has lost its history.

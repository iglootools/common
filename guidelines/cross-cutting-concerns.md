# Cross-Cutting Concerns

The concerns that reach every part of a system, whichever files a change
touches, and where the guidelines stand on each: the principle in
[philosophy.md](philosophy.md), and the rules that put it into practice so far.

**This is a work in progress.** Several concerns have a principle and no rules
yet, and some have neither. We build on this document as we identify better
practices: a concern gains rules in the guideline that owns them, and this index
gains a link.

| Concern | Understand why | Know the rules so far |
|---|---|---|
| Error handling | [Errors as first-class values](philosophy.md#errors-as-first-class-values) | [general.md › Surface every error](coding/general.md#surface-every-error-never-fail-silently), [python.md › Errors](coding/python.md#errors) |
| Presentation and escaping | [Presentation at the edges](philosophy.md#presentation-at-the-edges) | [general.md › Presentation at the Edges](coding/general.md#presentation-at-the-edges), [python.md › Console Output](coding/python.md#console-output) |
| Testing | [Test behavior, not implementation](philosophy.md#test-behavior-not-implementation) | [general.md › Testability](coding/general.md#testability), [general.md › Patch only in the three documented cases](coding/general.md#patch-only-in-the-three-documented-cases-and-list-each-one), [python.md › Tests](coding/python.md#tests) |
| Time and ambient state | [Explicit over implicit](philosophy.md#explicit-over-implicit) | [general.md › Use UTF-8 and UTC everywhere](coding/general.md#use-utf-8-and-utc-everywhere-and-pass-the-current-time-in) |
| Security | [Security as a default, not a phase](philosophy.md#security-as-a-default-not-a-phase) | CI and publishing only: [workflows.md](project-setup/workflows.md) (least-privilege `permissions`, actions pinned by SHA), [pypi-publishing.md › Publish with trusted publishing](project-setup/pypi-publishing.md#publish-with-trusted-publishing-never-an-api-token), [repository.md › Protect the default branch and release tags](project-setup/repository.md#protect-the-default-branch-and-release-tags) |
| Dependencies and supply chain | [Reproducible environments](philosophy.md#reproducible-environments) | [general.md › Version Management](coding/general.md#version-management), [dependency-automation.md](project-setup/dependency-automation.md), [python-tooling.md › Target only the latest stable Python](project-setup/python-tooling.md#target-only-the-latest-stable-python) |
| Observability and logging | [Observability is not optional](philosophy.md#observability-is-not-optional), [Make everything inspectable](philosophy.md#make-everything-inspectable) | none yet |
| Operations: running, changing and recovering a system | [Observability is not optional](philosophy.md#observability-is-not-optional), [Automate the toil](philosophy.md#automate-the-toil) | runbooks as [types.md › How-to guide](documentation/types.md#how-to-guide) (destructive steps marked, recovery given), settings kept as commands in [layout.md › Record repository settings as commands](documentation/layout.md#record-repository-settings-as-commands-in-one-place), recovering a release in [pypi-publishing.md › When a publish fails](project-setup/pypi-publishing.md#when-a-publish-fails) |
| Destructive operations and dry-run | [Correctness over convenience](philosophy.md#correctness-over-convenience) | destructive operations behind explicit opt-in: [general.md › Keep riskier changes structurally apart](coding/general.md#keep-riskier-changes-structurally-apart) |
| Failure of external calls: timeouts, retries | [Assume failure in distributed systems](philosophy.md#assume-failure-in-distributed-systems) | none yet; [general.md › Naming](coding/general.md#naming) only asks for the unit in a timeout's name |
| Idempotency and recovery | [Event-driven, append-only, replayable](philosophy.md#event-driven-append-only-replayable) | none yet |
| Interfaces and the CLI | [Task-driven interfaces, not CRUD](philosophy.md#task-driven-interfaces-not-crud) | [general.md › Command Line](coding/general.md#command-line) |
| Architecture and boundaries | [High cohesion, low coupling](philosophy.md#high-cohesion-low-coupling--at-every-boundary) | [general.md › Keep cohesion high and coupling low](coding/general.md#keep-cohesion-high-and-coupling-low-at-every-level), [python.md › Module Boundaries](coding/python.md#module-boundaries) |
| Performance | none yet | none yet |
| Configuration: format, validation, precedence | none yet | none yet |

Not covered at all yet: accessibility, internationalization, privacy and
personal data, concurrency.

The audit already checks several of these concerns, under the categories in
[review/audit.md](review/audit.md#categories), including where no rule exists
yet: `SEC`, `PERF` and `OPS`. Writing those rules down is the next step for
this document.

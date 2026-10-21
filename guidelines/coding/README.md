# Coding Guidelines

How these projects write code. Both files here are **always on**: the plugin's `SessionStart`
hook puts them in context at the start of every session, so they are the guidelines an agent
applies without being asked. They are layered rather than parallel — `general.md` states a rule
for any language, `python.md` states the Python-specific form of it where there is one.

| File | What is in it |
|---|---|
| [general.md](general.md) | Language-agnostic principles: functional style, function size, high cohesion and low coupling, people and AI agents (docs for people first, agent configuration for the gaps, tool-enforced rules, risk-graded structure), comments, UTC timestamps, avoiding mocks by passing values in, presentation at the edges (rendering, indentation and escaping outside the core), structured errors, no silent failures, dependency pinning, and the CLI conventions that hold regardless of language. Carries the defaults-not-dogma clause. |
| [python.md](python.md) | The Python layer: functional style in Python terms, `dedent` for structured strings, typing, frozen dataclasses, plain exception classes and structured errors, module-level and `lazy` imports, 88-character formatting, control flow, console output through Rich (indentation and markup escaping), module boundaries as import-linter contracts — and the [Python Version Policy](python.md#python-version-policy), the latest stable release as the only supported version, the four knobs that name it, and what to do when a dependency lags. |

Configuration rather than code — how a project is built, its workflows, its editor — is in
[../project-setup/](../project-setup/).

# Coding Guidelines

How these projects write code. Both files here are **always on**: the plugin's `SessionStart`
hook puts them in context at the start of every session, so they are the guidelines an agent
applies without being asked. They are layered rather than parallel — `general.md` states a rule
for any language, `python.md` states the Python-specific form of it where there is one.

| File | What is in it |
|---|---|
| [general.md](general.md) | Language-agnostic principles: functional style, function size, comments, UTC timestamps, avoiding mocks by passing values in, structured errors, no silent failures, dependency pinning, and the CLI conventions that hold regardless of language. Carries the defaults-not-dogma clause. |
| [python.md](python.md) | The Python layer: functional style in Python terms, `dedent` for structured strings, typing, frozen dataclasses, 88-character formatting, control flow, console output through Rich — and the [Python Version Policy](python.md#python-version-policy), the 3.12 floor with the five knobs that enforce it. |

Configuration rather than code — how a project is built, its workflows, its editor — is in
[../project-setup/](../project-setup/).

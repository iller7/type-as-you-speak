# Roadmap

[GitHub Issues](https://github.com/iller7/type-as-you-speak/issues) is the source of truth for tasks, acceptance criteria, live status and verification evidence. New ideas and follow-ups belong there. This file provides navigation, not a second status database.

| Priority | Focus                                                                                 | Live tasks                                                                                                                   |
| -------- | ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| P0       | Test suite, known-audio fixtures, desktop/GPU QA, release rehearsal and licensing     | [Release blockers](https://github.com/iller7/type-as-you-speak/issues?q=is%3Aissue+is%3Aopen+label%3Apriority%3AP0)          |
| P1       | Security, simpler builds, packaging, installation, documentation and automation       | [Next work](https://github.com/iller7/type-as-you-speak/issues?q=is%3Aissue+is%3Aopen+label%3Apriority%3AP1)                 |
| P2       | Structure, Python/Rust and UI decisions, macOS/Windows, Flatpak and offline lifecycle | [Platform and architecture](https://github.com/iller7/type-as-you-speak/issues?q=is%3Aissue+is%3Aopen+label%3Apriority%3AP2) |
| P3       | Accessibility, localisation and optional metrics                                      | [Later work](https://github.com/iller7/type-as-you-speak/issues?q=is%3Aissue+is%3Aopen+label%3Apriority%3AP3)                |

Start with [the comprehensive test suite](https://github.com/iller7/type-as-you-speak/issues/4), [known-audio tests](https://github.com/iller7/type-as-you-speak/issues/5) and [the environment matrix](https://github.com/iller7/type-as-you-speak/issues/6). Work needing a maintainer choice is labelled [status:needs-decision](https://github.com/iller7/type-as-you-speak/issues?q=is%3Aissue+is%3Aopen+label%3Astatus%3Aneeds-decision); started work is labelled [status:in-progress](https://github.com/iller7/type-as-you-speak/issues?q=is%3Aissue+is%3Aopen+label%3Astatus%3Ain-progress).

Every PR references an issue. `Refs #123` records partial work; `Closes #123` closes a completed task when merged into master. Keep unresolved desktop, hardware and release checks in the issue rather than closing it after a build pass. Merged and released are different states.

Completion history is in merged PRs and [closed issues](https://github.com/iller7/type-as-you-speak/issues?q=is%3Aissue+is%3Aclosed). Keep development local-LLM friendly, Markdown naturally wrapped, and automation suitable for GitHub Free.

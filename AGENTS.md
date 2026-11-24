# Project guidance

Read `TODO.md` before substantial work. It is the shared product backlog, not temporary agent execution state. Use `CONTRIBUTING.md` for verification and `.agents/guides/python-desktop.md` when working on Python, Qt, audio or Linux integration.

## Working principles

- Prefer established, maintainable practices that fit a local desktop dictation app. Record evidence and trade-offs in the backlog before introducing a new framework, language, packaging channel or service.
- The maintainer develops on Kubuntu with a local LLM. Keep instructions usable through ordinary files and CLI tools. Do not require a cloud LLM provider, API key, paid assistant or proprietary agent harness. GitHub CI and initial dependency/model downloads are separate from local inference.
- Python is the current implementation, not a permanent decision. Keep the Python/Rust/hybrid and desktop-shell decisions in TODO.md open until measured evidence and the maintainer's preference settle them.
- Use the main checkout and short-lived branches. Never create, enter or use Git worktrees. Preserve unrelated changes.
- Keep temporary agent plans, specifications, transcripts and execution logs outside the repository. The user explicitly requested TODO.md as a durable product backlog; maintain it in version control.

## Backlog upkeep

- Add new bugs, ideas, risks and follow-up suggestions to TODO.md as they arise. Give each task a stable ID, priority, status and completion condition. Avoid duplicate tasks.
- Order active tasks by importance. Update the existing row when work progresses and link its PR or verification evidence.
- Mark Done only when the completion condition is met. Distinguish proposed, implemented, CI-verified, desktop-tested, merged and released work. A build pass does not prove microphone, focus, input permissions or GPU compatibility.
- Preserve completed-task evidence and unresolved verification gaps. Record scope changes rather than silently dropping work.

## Pull requests and merging

- Start from current master, implement on a feature branch and open a PR for completed work. Do not report delivery complete while leaving changes only on a branch with no PR.
- Use a Conventional Commit PR title and the repository PR template. Include purpose, checks, remaining gaps and rollback. This personal GitHub project does not require an Orgvue/Azure DevOps ticket.
- Complete relevant tests, package checks and available CI before requesting review. Use an independent code review for substantial changes when the available local tooling permits it; do not require a cloud agent to do so.
- When the user authorises merging, use normal PR merge or auto-merge after required checks pass. GitHub does not allow authors to approve their own PRs. Never fabricate approval, switch identities to self-approve, bypass checks or weaken protection to force a merge.
- Confirm the PR's merged state and sync master before starting the next piece of work. A merge is not a release; publishing packages, changing the licence or performing a major migration needs the corresponding explicit decision.
- Put proposed review comments in the conversation first. Publish PR comments/reviews only when explicitly requested. Never post directly to Microsoft Teams.

## Formatting

- Write each Markdown paragraph and list item on one source line. Let the editor/viewer wrap visually; do not hard-wrap prose at 72, 79, 80 or 100 columns. Preserve deliberate line breaks in code, tables, HTML and other structured content.
- Prettier uses `proseWrap: never`; EditorConfig disables a Markdown line-width target. Shared VS Code settings enable visual Markdown wrapping. Keep documentation concise and link to the authoritative guide instead of duplicating it.
- Use two-space indentation by default. Python keeps the PEP 8 four-space convention; Makefiles keep tabs. Use Ruff for Python formatting, not a Markdown formatter.

## Verification and privacy

- Use the pinned tools and uv.lock. Run `make check` for code changes and `make build` for packaging or source-distribution changes. Consult official documentation and tool help; use connected documentation tools when available without making them a prerequisite for local development.
- Exercise the smallest relevant check during development, then the required full checks once. Re-run broader checks when a new change, failure or unresolved concern warrants it.
- For audio tests, use local generation or reviewed, redistributable fixtures with known transcripts. Ordinary tests must not require a microphone, cloud TTS/LLM, user credentials or permission to type into the desktop.
- Keep speech, hotwords, credentials and real user data out of logs, fixtures, issues and CI artifacts. Respect input-device permissions; do not grant world-write access or silently add input-group membership.
- Keep CI and hosting suitable for GitHub Free. Prefer fast checks for small changes and scoped slower checks where justified. Record storage, runner and hardware limitations without claiming GPU QA from CPU-only hosted runners.

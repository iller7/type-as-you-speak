# Project guidance

Read `TODO.md` before substantial work. It is a concise roadmap to GitHub Issues, the source of truth for tasks and status. Use `CONTRIBUTING.md` for verification and `.agents/guides/python-desktop.md` when working on Python, Qt, audio or Linux integration.

## Working principles

- Prefer established, maintainable practices that fit a local desktop dictation app. Record evidence and trade-offs in the backlog before introducing a new framework, language, packaging channel or service.
- The maintainer develops on Kubuntu with a local LLM. Keep instructions usable through ordinary files and CLI tools. Do not require a cloud LLM provider, API key, paid assistant or proprietary agent harness. GitHub CI and initial dependency/model downloads are separate from local inference.
- Python is the current implementation, not a permanent decision. Keep the Python/Rust/hybrid and desktop-shell decisions in GitHub Issues open until measured evidence and the maintainer's preference settle them.
- Use the main checkout and short-lived branches. Never create, enter or use Git worktrees. Preserve unrelated changes.
- Keep temporary agent plans, specifications, transcripts and execution logs outside the repository. Keep TODO.md as a short, stable roadmap linking to issue queries; do not duplicate live issue status.

## Backlog upkeep

- GitHub Issues owns tasks, priority, acceptance criteria, progress and verification evidence. Add discoveries and follow-ups there, checking for duplicates first. Retain migrated Txxx IDs for historical references; new issues can use their GitHub number directly.
- Use priority:P0 through priority:P3 labels. Use status:in-progress or status:needs-decision where applicable; unlabelled open issues are queued. Remove obsolete status labels when a decision is made, work stops or the task closes.
- Every PR must reference an issue: use `Refs #123` for partial progress and `Closes #123` only when all acceptance criteria are met. Automated dependency PRs also need a linked tracking issue before merging; create/link one rather than bypassing the convention.
- Preserve unresolved verification gaps in the issue. Distinguish implementation, CI verification, desktop QA, merging and release publication. A build does not prove microphone, focus, input or GPU compatibility.
- Keep TODO.md concise and use query links rather than a manually synchronised status table. Completion history is in closed issues, PRs and Git history.

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

## Strict offline policy

- Keep telemetry disabled in all modes. Treat `strict_offline = true` as a mandatory denial of cloud/network-dependent dictation features, including any future post-processing or provider SDK. Unchecking it does not independently opt users into a cloud service.
- Keep explicit model downloads outside the restricted dictation process. Apply the Linux process guard before helpers, inference imports and microphone capture; fail closed if unavailable. Report active enforcement separately from saved preferences. Preserve Unix desktop IPC and test thread/child-process inheritance.
- Keep known-audio/native-network regression checks anonymous and public-fixture-only. No test should send private speech, credentials or hotwords. Preserve verification limits across hardware and platform ports.

## Licensing

The public core is AGPL-3.0-only. COMMERCIAL.md describes enquiries for separate written terms, not a blanket licence or an existing contract. Preserve legacy MIT and third-party notices; old releases keep their terms. Do not add a proprietary exception, claim contributor relicensing rights or include external code in a commercial edition without documented permission. Issue #10 retains the component/model/contributor-rights audit.

## Change

Describe the problem and resulting behaviour. Use a Conventional Commit title.

## Validation

List commands and results, including distro, Python version, desktop and Wayland/X11 where relevant. State checks that remain unverified. For dependency changes, include the packaged dependency audit.

## Compatibility and rollback

Describe changes to user configuration, models, packages or permissions, and how to revert. State whether old versions can read any changed persistent data.

## Privacy

Confirm diagnostics contain no dictated text, audio, hotwords, secrets or personal file contents. Use synthetic fixtures for tests.

## Linked issue

Refs #<!-- issue number; use Closes only when all acceptance criteria are met -->

Link the GitHub issue, record verification evidence and remaining follow-ups there. Distinguish implementation, CI verification, desktop QA and release publication. Use the normal PR/auto-merge workflow when merging is authorised; no self-approval or protection bypass.

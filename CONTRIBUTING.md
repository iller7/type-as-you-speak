# Contributing

Read [AGENTS.md](AGENTS.md) for project-wide guidance and [TODO.md](TODO.md) for the roadmap to GitHub Issues, which owns priorities, acceptance criteria and live status. Record completion evidence and remaining verification gaps in the linked issue. Local agents can use the [Python desktop guide](.agents/guides/python-desktop.md) without a cloud LLM provider. If the local harness does not load AGENTS.md automatically, include it in the initial project context.

Use Python 3.14 for development. We test Python 3.11–3.14 for Linux distro compatibility. Python 3.15 awaits compatible ONNX Runtime wheels. `mise install` supplies pinned developer tools; alternatively install the versions in `mise.toml` yourself.

```sh
make setup
make check
make build
make package-deb
make package-rpm
```

`uv.lock` records exact dependency versions and hashes across supported interpreters and platforms. Use `uv lock --upgrade` for a deliberate refresh, then run the tests and native package checks. Do not hand-edit it. The release build backend is installed from the lockfile; builds run without fetching another backend in an isolated environment.

The K8s repository's practices are adapted here as pinned tools, dependency automation, ownership and explicit validation/rollback notes. Dependabot maintains uv, Actions and container dependencies without requiring a separate Renovate installation. Desktop release checks also need real installed packages, AppStream/desktop metadata, a GUI launch and microphone/input testing.

Use small pull requests with a Conventional Commit title and an associated GitHub issue. Use `Refs #123` for partial progress and `Closes #123` only when all acceptance criteria are met. Labels organise the automatically generated release notes; unlabelled PRs remain in the catch-all category. Add regression tests for behaviour changes. Describe test results, compatibility, privacy implications and rollback in the PR template. Do not create agent plans or workflow state in the repository. Do not add transcript/audio fixtures from real users.

## Verification boundaries

Unit tests use synthetic audio arrays and stub the model and input boundary; they never download speech models or type into the desktop. macOS/Windows jobs test portable Python code, dependency installation and package metadata. They do not imply working desktop dictation on those platforms. Linux container jobs test native package build, installation, imports and an offscreen Qt launch. Arch currently has a package-build check; distro/AUR inference dependencies must be available before desktop validation.

Before a release, test on a real Linux desktop: KDE Plasma and GNOME; Wayland and X11; CPU inference; NVIDIA when GPU support changes. Check first-run download and offline restart, start/stop/toggle, focus changes, clipboard fallback, user shortcuts, volume restoration after failure, settings persistence and package removal. Use synthetic speech and a disposable text editor. Keep checks and gaps in the release/PR record.

## Platform direction

Keep transcription and configuration independent of desktop integrations. Future macOS/Windows support needs separate adapters for audio capture, input injection, permissions, shortcuts, application data paths and packaging/signing. Use the current PySide6 UI while T019 evaluates desktop-shell alternatives; the framework choice remains open. Do not reuse Linux shell tools as a cross-platform abstraction. Introduce these adapters with behaviour tests when implementing the ports; a full Rust rewrite is not required for this boundary.

## PR workflow and documentation

Create a PR for completed work rather than leaving it only on a feature branch. When merging is authorised, use normal merge or auto-merge after required checks pass; authors cannot approve their own PRs. Confirm the merged state and sync master before starting the next piece of work. Do not bypass protections or fabricate an approval.

Write Markdown paragraphs and list items on single source lines, with visual wrapping in the editor. The repository configures Prettier to avoid hard wrapping. Indent two spaces by default, four for Python, and use tabs in Makefiles. Focused user guides live in docs/; the README should remain a short entry point.

# Contributing

Read [AGENTS.md](AGENTS.md) for project-wide guidance and [TODO.md](TODO.md) for the roadmap to GitHub Issues, which owns priorities, acceptance criteria and live status. Record completion evidence and remaining verification gaps in the linked issue. Local agents can use the [Python desktop guide](.agents/guides/python-desktop.md) without a cloud LLM provider. If the local harness does not load AGENTS.md automatically, include it in the initial project context.

Use Python 3.14 for development. We test Python 3.11–3.14 in the shared CI matrix and Python 3.15 in the Fedora 45 RPM lane using Fedora's native ONNX Runtime. Standard PyPI-only environments still need Python 3.11–3.14 because ONNX Runtime has no cp315 wheels. `mise install` supplies pinned developer tools; alternatively install the versions in `mise.toml` yourself.

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

See the [testing matrix](docs/testing.md) for Linux desktop families, Windows/macOS targets, automated coverage and hardware-dependent gaps. The product target spans all three operating systems; current desktop support and future targets are different claims.

## Verification boundaries

Unit tests use synthetic audio arrays and stub the model and input boundary; they never download speech models or type into the desktop. macOS/Windows jobs test portable Python code, dependency installation and package metadata. They do not imply working desktop dictation on those platforms. Linux container jobs test native package build, installation, imports and an offscreen Qt launch. Arch currently has a package-build check; distro/AUR inference dependencies must be available before desktop validation.

Before a release, test on a real Linux desktop: KDE Plasma and GNOME; Wayland and X11; CPU inference; NVIDIA when GPU support changes. Check first-run download and offline restart, start/stop/toggle, focus changes, clipboard fallback, user shortcuts, volume restoration after failure, settings persistence and package removal. Use synthetic speech and a disposable text editor. Keep checks and gaps in the release/PR record.

## Platform direction

Keep transcription and configuration independent of desktop integrations. Future macOS/Windows support needs separate adapters for audio capture, input injection, permissions, shortcuts, application data paths and packaging/signing. Use the current PySide6 UI while T019 evaluates desktop-shell alternatives; the framework choice remains open. Do not reuse Linux shell tools as a cross-platform abstraction. Introduce these adapters with behaviour tests when implementing the ports; a full Rust rewrite is not required for this boundary.

## PR workflow and documentation

Create a PR for completed work rather than leaving it only on a feature branch. When merging is authorised, use normal merge or auto-merge after required checks pass; authors cannot approve their own PRs. Confirm the merged state and sync master before starting the next piece of work. Do not bypass protections or fabricate an approval.

Write Markdown paragraphs and list items on single source lines, with visual wrapping in the editor. The repository configures Prettier to avoid hard wrapping. Indent two spaces by default, four for Python, and use tabs in Makefiles. Focused user guides live in docs/; the README should remain a short entry point.

## Licensing contributions

The public core is AGPL-3.0-only; see [licensing scope](docs/licensing.md). Contributions under that licence do not automatically grant alternative commercial-licensing rights. Do not claim a CLA exists or include outside contributions in a proprietary edition without the copyright-holder permissions required for that use. The contributor-rights process remains part of issue #10.

## Community and triage

Follow the [Code of Conduct](CODE_OF_CONDUCT.md) and [support guidance](SUPPORT.md). GitHub Pages is the documentation home; the wiki is not a second source of truth. Issue forms assign a type label. Maintainers add one priority (`priority:P0`–`priority:P3`) and relevant `area:*` labels; use status labels only while active or awaiting a decision. PR labels are automated from branch names and changed paths, with manual corrections where needed. Release notes are generated from labelled PRs.

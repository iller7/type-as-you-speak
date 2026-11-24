# Contributing

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

Use small pull requests with a Conventional Commit title. Add regression tests for behaviour changes. Describe test results, compatibility, privacy implications and rollback in the PR template. Do not create agent plans or workflow state in the repository. Do not add transcript/audio fixtures from real users.

## Verification boundaries

Unit tests use synthetic audio arrays and stub the model and input boundary; they never download speech models or type into the desktop. macOS/Windows jobs test portable Python code, dependency installation and package metadata. They do not imply working desktop dictation on those platforms. Linux container jobs test native package build, installation, imports and an offscreen Qt launch. Arch currently has a package-build check; distro/AUR inference dependencies must be available before desktop validation.

Before a release, test on a real Linux desktop: KDE Plasma and GNOME; Wayland and X11; CPU inference; NVIDIA when GPU support changes. Check first-run download and offline restart, start/stop/toggle, focus changes, clipboard fallback, user shortcuts, volume restoration after failure, settings persistence and package removal. Use synthetic speech and a disposable text editor. Keep checks and gaps in the release/PR record.

## Platform direction

Keep transcription and configuration independent of desktop integrations. Future macOS/Windows support needs separate adapters for audio capture, input injection, permissions, shortcuts, application data paths and packaging/signing. Retain PySide6 for a shared settings UI. Do not reuse Linux shell tools as a cross-platform abstraction. Introduce these adapters with behaviour tests when implementing the ports; a full Rust rewrite is not required for this boundary.

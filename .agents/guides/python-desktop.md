# Python desktop development

This guide works with a local model and ordinary CLI tools. Read AGENTS.md and TODO.md first. It describes the current Python app; it does not decide the future language or UI framework.

## Start with the relevant boundary

| Area                      | Current location                  | Read alongside it                                                    |
| ------------------------- | --------------------------------- | -------------------------------------------------------------------- |
| CLI and session lifecycle | `src/type_as_you_speak/cli.py`    | Configuration, state/log files, daemon and audio restoration tests   |
| Recognition and streaming | `src/type_as_you_speak/engine.py` | Audio readers, VAD, commit logic, model fallback and typing boundary |
| User configuration        | `src/type_as_you_speak/config.py` | `config/default.toml`, GUI load/save and precedence tests            |
| Settings UI               | `src/type_as_you_speak/gui.py`    | CLI JSON contract, model download lifecycle and Qt event loop        |
| Distribution              | `packaging/`, `scripts/`          | Lockfile, installed-artifact tests and release workflow              |

Keep meaningful boundaries visible. Split large modules when a concrete change needs a smaller responsibility; preserve behaviour first. Do not create a web API or copy FastAPI/database patterns into this desktop app without an actual requirement.

## Local workflow

```sh
make setup
uv run --locked pytest tests/test_config.py
make check
make build
```

Development uses Python 3.14; shipped code must remain compatible with the supported 3.11–3.14 range. `uv.lock` pins dependencies across platforms. A missing local wheel, credential or tool is a verification limit to resolve or report, not permission to claim a pass. Use the distro container targets when changing native packages.

Use four spaces for Python. Prefer clear functions and names, explicit lifecycle/ownership and type hints at interfaces. Avoid broad abstractions, configurable frameworks and shell subprocesses for work the standard library can do clearly. Keep subprocess argument arrays explicit, check failures, and bound blocking operations with timeouts.

## Desktop and audio safety

- Keep model downloads, inference, device discovery and blocking subprocess calls off Qt's UI thread. Use Qt signals to return results to widgets; do not update widgets from worker threads.
- Keep capture, recognition, commit decisions and input injection separately testable. Treat the focused window, microphone and input-device privileges as real external boundaries.
- Test cancellation, duplicate starts, stale state, model failure, GPU/CPU fallback, silence, long pauses, interrupted capture and restoration of the previous audio state.
- Keep operating-system integration explicit. Linux tools and XDG paths do not establish macOS/Windows support. Portability CI is narrower than working desktop dictation.
- Run known-audio tests with a pinned model/configuration and documented transcript normalisation/tolerances. Compare accuracy and timing; exact text equality alone is too brittle across backends.

## Tests and local models

Use synthetic arrays and stubs for fast unit tests. Add a small set of licensed WAV fixtures and expected transcripts for real recognition tests under T002; larger datasets and GPU runs belong in separate jobs. Include silence and failure cases, and ensure dry runs cannot inject input.

Use a local TTS generator such as eSpeak NG when generating fixtures, or review the licence of recorded samples before adding them. The legacy gTTS extra uses an online service, so it must not become a requirement for the local-only workflow or offline tests. Record fixture provenance, model version/revision, configuration and expected thresholds.

No cloud LLM is required to develop or run the current app. Do not add remote post-processing or a provider SDK just because an example project uses one. If optional LLM integration is proposed, record it in GitHub Issues and design around the maintainer's local setup first.

## Review

Check observable behaviour, failures, privacy and installed-package operation before style. Add a regression test for a real bug, avoid tests that merely repeat implementation, and state what remains unverified. Use the PR workflow in AGENTS.md and update the linked GitHub issue with evidence.

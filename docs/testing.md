---
title: Testing and platform targets
---

# Testing and platform targets

The product target is Linux across distributions and desktops, plus Windows and macOS. Current working desktop integration is Linux-specific; Windows/macOS desktop ports remain tracked in [#23](https://github.com/iller7/type-as-you-speak/issues/23) and [#24](https://github.com/iller7/type-as-you-speak/issues/24). A portable-code CI pass does not mean desktop dictation or installers work on that operating system.

## Automated layers

| Layer                        | Environments                                                                                            | What it establishes                                                                                                                                 |
| ---------------------------- | ------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| Shared behaviour             | Ubuntu 24.04 with Python 3.11–3.14; macOS 15 and Windows Server 2025 runners with Python 3.11 and 3.14  | Configuration, audio-buffer boundaries, streaming commits, fallback/error handling, cleanup and transcript privacy using deterministic test inputs  |
| Installed wheel              | The same eight OS/Python combinations                                                                   | The installed command imports, reports help/version and imports inference/GUI dependencies                                                          |
| Native Linux packages        | Debian 12/13, Ubuntu 24.04/26.04, Fedora 44/45; Arch package-build check                                | Distro/ABI-specific packaging; clean installation/audit/offscreen GUI checks where implemented in packaging CI                                      |
| Known-audio inference        | Python 3.14 on Ubuntu, macOS and Windows CI; [#5](https://github.com/iller7/type-as-you-speak/issues/5) | Pinned tiny.en CPU inference through the EOF-commit path for a CC-BY recording, a noisy derivative and silence; separate from stubbed decoder tests |
| Desktop, permissions and GPU | Target hardware or disposable graphical machines                                                        | Microphone capture, focused-window input, shortcuts, clipboard, device permissions, acceleration, signing and installation behaviour                |

CI logs the actual host, interpreter and architecture. The macOS runner is one OS/image/architecture at a time; Windows Server CI is not a substitute for Windows desktop testing. CPU-hosted tests do not certify NVIDIA, AMD/ROCm or Apple acceleration. ARM64/native installer support needs explicit verification before advertising it.

## Desktop acceptance matrix

| Platform target  | Coverage to establish before claiming support                                                                                                                                         |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Linux on Wayland | KDE Plasma, GNOME and representative wlroots compositors such as Sway; verify input/clipboard tools and permission paths independently                                                |
| Linux on X11     | KDE Plasma, GNOME and representative desktops such as Xfce, Cinnamon, MATE or LXQt; verify display-protocol behaviour rather than assuming a desktop name implies compatibility       |
| Windows desktop  | Supported Windows versions and architectures must be selected; test microphone permission, input injection, shortcuts, focus, clipboard, installer/update and signing                 |
| macOS desktop    | Supported macOS versions and Intel/Apple Silicon coverage must be selected; test microphone/accessibility permissions, input, shortcuts, focus, clipboard, packaging and notarisation |

Use a risk-based matrix rather than every distro × desktop × GPU × Python combination. Start with each distinct platform API, display protocol and package ABI; add regressions for reported combinations. Record versions and actual evidence in [#6](https://github.com/iller7/type-as-you-speak/issues/6), Linux desktop QA in [#7](https://github.com/iller7/type-as-you-speak/issues/7), and hardware inference in [#8](https://github.com/iller7/type-as-you-speak/issues/8).

## Running the fast suite

```sh
uv sync --locked --extra gui
uv run --locked pytest
```

Use `make check` for the complete local code/workflow checks. On Windows without Make or the POSIX linters, run the pytest command directly; the hosted quality job supplies those tools. No local cloud LLM account is required.

Tests exercise the real configuration and session code. Decoder, audio-source, clock, notification and OS-command boundaries are controlled where real execution would download models, require hardware or type into the desktop. Synthetic sample arrays test control flow, not speech accuracy. Fast tests must not use a microphone, launch input tools, download models or consume private audio. New inference fixtures need reviewed provenance, pinned model settings and documented accuracy/latency tolerances.

## Current gaps

Automated coverage is not a full platform certification. GUI interaction/save/download behaviour, real subprocess/audio capture, concurrent lifecycle races, model cache failures, broader recording/accuracy coverage, platform adapters and real desktop/GPU acceptance remain in [#4](https://github.com/iller7/type-as-you-speak/issues/4) and the linked issues. Keep these open until their acceptance criteria are met; do not close a cross-platform issue because one hosted runner passes.

## Real CPU recognition baseline

The Python 3.14 matrix jobs explicitly download a pinned public tiny.en model, verify every model-file hash, then run the recognition marker with offline loading and Python socket guards. The four Linux Python versions plus the Windows/macOS minimum/latest matrix retain fast checks; the model is prepared only on three latest-Python jobs, without adding runners or uploading weights/audio as artifacts. Public model downloads need no token or cloud inference account.

Run the same two stages locally on Linux, Windows or macOS, using a writable model directory:

```sh
uv run --locked python scripts/prepare-test-model.py --output PATH_TO_MODEL_DIRECTORY
uv run --locked pytest -m recognition tests/test_recognition.py --recognition-model PATH_TO_MODEL_DIRECTORY -q -s
```

The first command deliberately uses the network to obtain and verify model files. The second requires those local files, blocks Python network connections and desktop commands, and does not use a microphone. Normal pytest runs exclude recognition tests and never download models. A missing or corrupt model fails an explicitly requested recognition run; it is not silently skipped.

The [fixture provenance and thresholds](https://github.com/iller7/type-as-you-speak/blob/master/tests/fixtures/audio/README.md) record the original transcript, CC-BY-4.0 attribution, WAV conversion, corpus ID and hashes. WER/CER normalize case/punctuation; the baseline permits the documented Concord/Concorde homophone, and logs elapsed time without a hosted-runner speed gate. Silence must commit no text. The decoder and Silero VAD are real; only input, notifications and the audio source boundary are controlled.

This first integration baseline deliberately flushes the full pending recording at EOF. Live streaming cadence, long speech, diverse speakers/accents, real background noise, GPU inference and OS-level network isolation remain open. The Python network guard is not a substitute for an OS firewall or a complete privacy audit. A discovered faster-whisper/PyAV file-helper incompatibility is tracked separately in [#42](https://github.com/iller7/type-as-you-speak/issues/42); the app and these PCM tests use float32 arrays rather than that helper.

## Fedora 45 and Python 3.15

The Fedora matrix retains Fedora 44 and adds Fedora 45. Fedora 45 uses its system Python 3.15 and `python3-onnxruntime` RPM rather than a nonexistent cp315 PyPI wheel. The ONNX Runtime API floor is 1.26; ordinary wheel bundles remain locked to 1.32. A Fedora build records its native ONNX provider NEVRA, validates the combined environment, and audits the actual provider plus its installed Python dependency closure. It rejects a bundled ONNX copy shadowing the declared native provider.

Both RPM lanes build and install into a clean runtime image, launch Qt offscreen, and run the three known-audio cases against code copied from the installed RPM, with an assertion that the app is imported from that installed path. Model download and inference remain separate. This verifies packaged CPU inference rather than a microphone, compositor or GPU. Fedora 45 therefore adds Python 3.15 evidence without claiming that PyPI-only Python 3.15 installs on other platforms work.

The CI lane using the default image checks its expected Fedora version, so a future Dependabot major-image change cannot silently test or label a different distro. Fedora 44 is retained explicitly. Native OS libraries are serviced by Fedora; the Python advisory scan is not a complete OS vulnerability scan.

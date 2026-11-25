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

## CI validation scope

| Change or event                                                                   | Validation                                                                                                                                        |
| --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Pull request containing only recognized static documentation                      | Quality/security lint, CI policy regressions and wheel/source metadata checks; no platform matrix, recognition downloads or native package builds |
| Other pull requests, including runtime, dependency, packaging or workflow changes | Full quality, platform/recognition and native-package validation                                                                                  |
| Master pushes, manual/scheduled CI and release workflows                          | Full validation                                                                                                                                   |

The [selection policy](https://github.com/iller7/type-as-you-speak/blob/master/scripts/ci-policy.py) checks the actual PR merge against the event's base/head commits and considers both sides of a rename. Unknown paths, executable files, symlinks or ambiguous metadata select full validation. Failed selection, failed/cancelled jobs and unexpected skips cannot satisfy the required `passed` gate. Release checks default to full validation when called without selection inputs.

CodeQL retains its separate PR, master and weekly triggers. The optimization changes which application/package checks a documentation PR needs; it does not change supported platforms or their full test coverage for runtime changes.

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

## Explicit GPU recognition

Hardware validation uses the same hash-verified recording, noisy derivative, silence case and accuracy thresholds as the CPU baseline. Run it manually on a Linux machine with a supported GPU and a compatible installed backend; standard hosted CI continues to run CPU tests. This does not require a GitHub self-hosted runner or expose a personal machine to public PR jobs.

Prepare the public model once, then select the GPU explicitly:

```sh
uv run --locked python scripts/prepare-test-model.py --output PATH_TO_MODEL_DIRECTORY
uv run --locked pytest -m recognition tests/test_recognition.py --recognition-model PATH_TO_MODEL_DIRECTORY --recognition-device cuda -q -s
```

The test requests float16 inference and checks the loaded CTranslate2 model's actual device and compute type before recognition. Unsupported hardware, missing GPU libraries, a CPU/precision fallback or any attempt to load a session fallback model fails the run; none is treated as a skip or a GPU pass. Without `--recognition-device cuda`, the existing default remains CPU int8. An int8 CPU model may report its resolved type as `int8_float32`.

For NVIDIA, check the [faster-whisper GPU prerequisites](https://github.com/SYSTRAN/faster-whisper#gpu) and the [pinned CTranslate2 4.9.1 hardware guidance](https://github.com/OpenNMT/CTranslate2/blob/v4.9.1/docs/hardware_support.md). A detected graphics card or a successful `nvidia-smi` command alone does not prove inference works. No GPU drivers, alternate wheels or system libraries are installed by the recognition command.

AMD acceleration remains experimental and unverified for this app. It requires a separate ROCm-enabled CTranslate2 build; the normal PyPI CUDA/CPU wheel does not establish AMD support. Upstream exposes both NVIDIA CUDA and AMD HIP through `device="cuda"`, so the reported device string cannot identify the GPU vendor. Validate the origin/version of any alternate build separately, and record the actual hardware alongside results; do not treat an ordinary locked-environment CPU pass as ROCm evidence. See [upstream backend support](https://github.com/OpenNMT/CTranslate2/blob/v4.9.1/docs/hardware_support.md). Apple GPU acceleration is outside this app's current device selection; Apple Silicon CI is a CPU baseline.

The JSON output records the actual backend/precision, OS family, architecture, Python and inference-library versions, pinned model revision, WER/CER and elapsed inference time. It contains no hostname, GPU serial number, personal audio or dictated transcript. For [#8](https://github.com/iller7/type-as-you-speak/issues/8), attach these public-fixture metrics with the tested commit, distro/version, GPU model, driver/runtime versions, backend package origin and installation channel. Record failures too. NVIDIA, AMD and packaged GPU results remain pending until run on their respective hardware; no hardware validation is inferred from unit tests.

This recognition harness controls capture/input/notification boundaries and blocks Python network connections. It does not certify microphone capture, desktop input, strict Linux kernel enforcement on GPU drivers, GPU out-of-memory recovery or concurrent GPU workloads. Those require separate target-hardware runs under #7/#8/#45. Do not add a strict GPU speed threshold from a CPU-only baseline.

## Fedora 45 and Python 3.15

The Fedora matrix retains Fedora 44 and adds Fedora 45. Fedora 45 uses its system Python 3.15 and `python3-onnxruntime` RPM rather than a nonexistent cp315 PyPI wheel. The ONNX Runtime API floor is 1.26; ordinary wheel bundles remain locked to 1.32. A Fedora build records its native ONNX provider NEVRA, validates the combined environment, and audits the actual provider plus its installed Python dependency closure. It rejects a bundled ONNX copy shadowing the declared native provider.

Both RPM lanes build and install into a clean runtime image, launch Qt offscreen, and run the three known-audio cases against code copied from the installed RPM, with an assertion that the app is imported from that installed path. Model download and inference remain separate. This verifies packaged CPU inference rather than a microphone, compositor or GPU. Fedora 45 therefore adds Python 3.15 evidence without claiming that PyPI-only Python 3.15 installs on other platforms work.

The CI lane using the default image checks its expected Fedora version, so a future Dependabot major-image change cannot silently test or label a different distro. Fedora 44 is retained explicitly. Native OS libraries are serviced by Fedora; the Python advisory scan is not a complete OS vulnerability scan.

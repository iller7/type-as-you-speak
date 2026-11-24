---
title: Testing and platform targets
---

# Testing and platform targets

The product target is Linux across distributions and desktops, plus Windows and macOS. Current working desktop integration is Linux-specific; Windows/macOS desktop ports remain tracked in [#23](https://github.com/iller7/type-as-you-speak/issues/23) and [#24](https://github.com/iller7/type-as-you-speak/issues/24). A portable-code CI pass does not mean desktop dictation or installers work on that operating system.

## Automated layers

| Layer                        | Environments                                                                                           | What it establishes                                                                                                                                |
| ---------------------------- | ------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| Shared behaviour             | Ubuntu 24.04 with Python 3.11–3.14; macOS 15 and Windows Server 2025 runners with Python 3.11 and 3.14 | Configuration, audio-buffer boundaries, streaming commits, fallback/error handling, cleanup and transcript privacy using deterministic test inputs |
| Installed wheel              | The same eight OS/Python combinations                                                                  | The installed command imports, reports help/version and imports inference/GUI dependencies                                                         |
| Native Linux packages        | Debian 12/13, Ubuntu 24.04/26.04, Fedora 44; Arch package-build check                                  | Distro/ABI-specific packaging; clean installation/audit/offscreen GUI checks where implemented in packaging CI                                     |
| Known-audio inference        | Planned in [#5](https://github.com/iller7/type-as-you-speak/issues/5)                                  | Actual model output against licensed recordings and expected transcripts; this is separate from stubbed decoder tests                              |
| Desktop, permissions and GPU | Target hardware or disposable graphical machines                                                       | Microphone capture, focused-window input, shortcuts, clipboard, device permissions, acceleration, signing and installation behaviour               |

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

This is the first suite expansion, not a full certification. GUI interaction/save/download behaviour, real subprocess/audio capture, concurrent lifecycle races, model cache failures, known-recording inference, platform adapters and real desktop/GPU acceptance remain in [#4](https://github.com/iller7/type-as-you-speak/issues/4) and the linked issues. Keep these open until their acceptance criteria are met; do not close a cross-platform issue because one hosted runner passes.

---
title: Local dictation for Linux
---

# Speak. See your words appear.

**Local dictation for your Linux desktop.** Press a shortcut, speak, and type into the focused window as speech is recognised. type-as-you-speak combines faster-whisper recognition with Linux input integration.

[Get started](install.md) · [Download a release](https://github.com/iller7/type-as-you-speak/releases) · [Read the user guide](usage.md)

## Your speech stays on your machine

Recognition runs locally after the initial model download. No cloud LLM provider or account is required. Read [privacy and network access](privacy.md) for telemetry controls and verification limits. Review the [configuration guide](configuration.md) for CPU/GPU choices and the [security guide](https://github.com/iller7/type-as-you-speak/blob/master/SECURITY.md) for input-device permissions. This site adds no analytics or tracking pixels.

## Start here

| I want to…                                        | Guide                                                                                                                                                    |
| ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Install, upgrade or choose a distro package       | [Installation](install.md)                                                                                                                               |
| Set shortcuts, dictate or use the settings window | [Usage](usage.md)                                                                                                                                        |
| Select models, language or compute device         | [Configuration](configuration.md)                                                                                                                        |
| Diagnose microphone, input or startup failures    | [Troubleshooting](troubleshooting.md)                                                                                                                    |
| Check automated coverage and platform targets     | [Testing matrix](testing.md)                                                                                                                             |
| Understand the engine                             | [Architecture](architecture.md)                                                                                                                          |
| Contribute or see what is next                    | [Contributing](https://github.com/iller7/type-as-you-speak/blob/master/CONTRIBUTING.md) and [Issues](https://github.com/iller7/type-as-you-speak/issues) |

## Linux first, with honest support boundaries

KDE Plasma/GNOME and Wayland/X11 are the integration targets. CI builds and checks Debian 12/13, Ubuntu 24.04/26.04 and Fedora 44/45 packages; Arch has a package-build check. Real microphone, focus, input and GPU QA remains [tracked separately](https://github.com/iller7/type-as-you-speak/issues/7). Select a release asset matching your distro and architecture; a CI build does not mean that asset has been published.

Flatpak remains experimental. macOS and Windows currently have portable-code CI checks; desktop dictation ports and installers are not available. See the [distribution guide](https://github.com/iller7/type-as-you-speak/blob/master/packaging/README.md) for details.

## Free, open development

First-party source uses [AGPL-3.0-only](licensing.md), with a separate commercial-licensing enquiry path; dependencies, model weights and bundled input tools retain their own licences. Follow the [licensing review](https://github.com/iller7/type-as-you-speak/issues/10), [project direction](project-direction.md) and [automatically generated release changelog](https://github.com/iller7/type-as-you-speak/releases).

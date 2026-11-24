# type-as-you-speak

[![CI](https://github.com/iller7/type-as-you-speak/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/iller7/type-as-you-speak/actions/workflows/ci.yml) [![Release](https://img.shields.io/github/v/release/iller7/type-as-you-speak)](https://github.com/iller7/type-as-you-speak/releases/latest) [![License](https://img.shields.io/github/license/iller7/type-as-you-speak)](LICENSE) [![Downloads](https://img.shields.io/github/downloads/iller7/type-as-you-speak/total)](https://github.com/iller7/type-as-you-speak/releases) ![Python](https://img.shields.io/badge/Python-3.11%E2%80%933.14-blue) ![Platform](https://img.shields.io/badge/platform-Linux-blue)

Local dictation for Linux. Press a shortcut, speak, and type into the focused window as speech is recognised. The app uses faster-whisper for recognition and ydotool for input, with a clipboard fallback.

Audio stays on your machine. The first model download needs network access; recognition then runs locally. No cloud LLM provider or account is required.

## Get started

Download a matching distro package from [Releases](https://github.com/iller7/type-as-you-speak/releases), or install from source on Linux:

```sh
git clone https://github.com/iller7/type-as-you-speak.git
cd type-as-you-speak
./install.sh
tays setup
tays keybind
```

Bind `tays toggle` to a spare key. Press it to start dictation and press it again to stop. The source installer uses a user-owned Python environment and reports missing OS prerequisites. See the [installation guide](docs/install.md) for package versions, optional GUI setup, requirements and updates.

## Support and verification

| Area            | Current position                                                                                                           |
| --------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Linux           | KDE/GNOME, Wayland/X11 integration targets; real-desktop QA remains tracked in the backlog                                 |
| Native packages | CI builds and checks Debian 12/13, Ubuntu 24.04/26.04 and Fedora 44; select the asset matching the distro and architecture |
| Arch            | PKGBUILD build check; package-manager publication and full runtime validation are separate                                 |
| Flatpak         | Experimental; excluded from release publishing                                                                             |
| macOS / Windows | Portable-code CI only; desktop dictation ports remain open                                                                 |
| Inference       | CPU or compatible GPU; driver/backend compatibility and hardware QA matter                                                 |

CI results and published releases can represent different commits. The [distribution guide](packaging/README.md) records the ABI constraints, tested scope and channel limitations.

## Guides

- [Installation and updates](docs/install.md)
- [Usage, settings and KDE panel applet](docs/usage.md)
- [Configuration and GPU/CPU selection](docs/configuration.md)
- [Troubleshooting](docs/troubleshooting.md)
- [How the engine works](docs/architecture.md)
- [Development and verification](CONTRIBUTING.md)
- [Security and input-device permissions](SECURITY.md)
- [Release process](RELEASES.md)
- [Prioritised backlog and status](TODO.md)
- [Project direction and researched options](docs/project-direction.md)

## Contributing

Use Python 3.14 for development, install the pinned tools, then run `make setup`, `make check` and `make build`. Read [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md) before making changes. Keep the backlog current and deliver completed work through a PR.

## Licence

The first-party source uses [AGPL-3.0-only](LICENSE). Third-party components retain their own licences.

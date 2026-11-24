# type-as-you-speak

[![CI](https://github.com/iller7/type-as-you-speak/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/iller7/type-as-you-speak/actions/workflows/ci.yml) [![Release](https://img.shields.io/github/v/release/iller7/type-as-you-speak)](https://github.com/iller7/type-as-you-speak/releases/latest) [![License](https://img.shields.io/github/license/iller7/type-as-you-speak)](LICENSE) [![Downloads](https://img.shields.io/github/downloads/iller7/type-as-you-speak/total)](https://github.com/iller7/type-as-you-speak/releases) [![Python](https://img.shields.io/badge/Python-3.11%E2%80%933.15-blue)](docs/testing.md) ![Platform](https://img.shields.io/badge/platform-Linux-blue)

Real-time dictation with privacy built in. Speak into the app you are using: text is typed into its focused input field, subject to desktop permissions and application compatibility. Strict offline dictation is enabled by default.

The privacy hardening described here is on `master`; existing v0.5.1 binaries predate these protections.

Linux desktop integration is available today. macOS, Windows and an optional cloud service are planned; they are not current desktop/service features.

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

## Documentation and support

[Documentation website](https://iller7.github.io/type-as-you-speak/) · [Installation](docs/install.md) · [Usage](docs/usage.md) · [Troubleshooting](docs/troubleshooting.md)

Linux is the current target. Fedora 45 has a native-RPM Python 3.15 profile; ordinary PyPI-only installs use Python 3.11–3.14. Native-package CI and real-desktop verification have different scopes; see the [distribution guide](packaging/README.md). Flatpak is experimental, and macOS/Windows desktop ports remain open.

[GitHub Issues](https://github.com/iller7/type-as-you-speak/issues) owns tasks and status; [TODO.md](TODO.md) is the concise roadmap. [GitHub Releases](https://github.com/iller7/type-as-you-speak/releases) contains downloads and the automatic changelog.

## Contributing

Use Python 3.14 for development, install the pinned tools, then run `make setup`, `make check` and `make build`. Read [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md) before making changes. Keep the backlog current and deliver completed work through a PR.

## Licence

The public first-party source uses [AGPL-3.0-only](LICENSE), with [separate commercial licensing enquiries](COMMERCIAL.md) for code the maintainer controls. Earlier MIT releases retain their permissions. Dependencies, model weights and bundled tools retain their own terms; see the [licensing guide](docs/licensing.md).

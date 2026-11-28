---
title: "Installation"
---

# Installation

This guide describes the current source checkout. [v0.5.3](https://github.com/iller7/type-as-you-speak/releases/tag/v0.5.3) is published with strict offline controls; later source changes may not be included in that release. Desktop/GPU acceptance remains in progress.

## Requirements

| What                                                 | Why                                             | Install                                          |
| ---------------------------------------------------- | ----------------------------------------------- | ------------------------------------------------ |
| **Wayland or X11** (KDE, GNOME, Niri, Hyprland, …)   | keystrokes are injected into the focused window | your compositor / window manager — either works  |
| **NVIDIA GPU** _(optional, recommended)_             | fast, low-CPU transcription                     | your driver — otherwise it runs on CPU (slower)  |
| **Python 3.11–3.14**                                 | the engine                                      | `python3`                                        |
| **ffmpeg**                                           | mic capture                                     | `apt install ffmpeg` / `dnf install ffmpeg`      |
| **PulseAudio/PipeWire** (`pactl`)                    | mute output while the mic is live               | usually present with any DE                      |
| **Compatible ydotool** + its daemon                  | type into the focused window                    | `apt install ydotool` / `dnf install ydotool`    |
| **Clipboard** (`wl-copy` on Wayland, `xclip` on X11) | clipboard fallback if typing fails              | `apt install wl-clipboard` / `apt install xclip` |
| **libnotify** (`notify-send`)                        | desktop notifications                           | usually present                                  |

For source installs, verify the client/daemon version and current distro availability. Debian 12 supplies an older ydotool, while Debian 13 may require backports or a reviewed source build. The new Debian/Ubuntu packages include private compatible tools. Source-installer validation is tracked under [#18](https://github.com/iller7/type-as-you-speak/issues/18).

Download your selected Whisper model before the first strict-offline session with `tays download` or the GUI Download button. Models are cached under the configured Hugging Face cache (by default `~/.cache/huggingface`); model size depends on your selection.

## Install

### Option A — clone + `install.sh` (recommended)

```bash
git clone https://github.com/iller7/type-as-you-speak.git
cd type-as-you-speak
./install.sh
```

`install.sh` is idempotent and does all the safe, user-owned setup: creates a venv, installs the Python package **in editable mode** (so this repo stays the single source of truth — `git pull` updates the tool with no reinstall), puts `tays` on your PATH, makes sure the ydotool daemon (a systemd **user** service) is running, and drops a sample config. It never uses `sudo` — any OS package you're missing is printed with the exact install command.

### Option B — `pipx` / `pip`

```bash
pipx install "git+https://github.com/iller7/type-as-you-speak.git"
# or, into your own venv:
python3 -m venv .venv && .venv/bin/pip install "git+https://github.com/iller7/type-as-you-speak.git"
```

This gets you the `tays` command. You still need the OS prerequisites above (especially **ydotool + its daemon**) — `pip` can't set those up, so prefer `install.sh` if you want it all handled.

### Option C — ready-made Linux packages (CPU-validated)

[v0.5.3](https://github.com/iller7/type-as-you-speak/releases/tag/v0.5.3) provides distro-specific Debian 12/13, Ubuntu 24.04/26.04 and Fedora 44/45 packages, plus a wheel and source archive. Choose the asset matching your distro, version and x86-64 architecture. These packages passed clean-install/CPU checks; real desktop/GPU acceptance remains open. GitHub release downloads are separate from AUR/Copr/Flathub/PyPI publication.

Download the selected package and `SHA256SUMS` from the same release. Verify its checksum before installing; the following commands use the Ubuntu 24.04 asset as an example:

```sh
gh release verify v0.5.3 --repo iller7/type-as-you-speak
gh release download v0.5.3 --repo iller7/type-as-you-speak --pattern SHA256SUMS --pattern 'type-as-you-speak_0.5.3_ubuntu24.04_amd64.deb'
sha256sum --check --ignore-missing SHA256SUMS
gh attestation verify type-as-you-speak_0.5.3_ubuntu24.04_amd64.deb --repo iller7/type-as-you-speak --signer-workflow iller7/type-as-you-speak/.github/workflows/release.yml --source-ref refs/tags/v0.5.3 --deny-self-hosted-runners
sudo apt install ./type-as-you-speak_0.5.3_ubuntu24.04_amd64.deb
```

For a matching Fedora RPM, verify the selected file the same way and install it with `sudo dnf install ./SELECTED_PACKAGE.rpm`. Run commands separately and stop on any verification failure. Note the `--signer-workflow` path: this v0.5.3 example was signed by `.github/workflows/release.yml`; from v0.5.4 on the publish workflow is `.github/workflows/publish.yml`, so use that path when verifying newer releases. GitHub CLI verification requires a current `gh`; a checksum confirms matching bytes, while attestation verification also checks the producing repository/workflow. Neither replaces desktop compatibility testing.

Package-channel builds are currently **validated for CPU inference**. Building without a GPU does not establish whether the installed backend can accelerate on a target machine; packaged GPU operation remains unverified. Source installs allow you to supply compatible GPU runtime libraries, but still need the [explicit hardware recognition check](testing.md#explicit-gpu-recognition).

Other channels have recipes in the repository. Submission/publication status needs confirmation under [#15](https://github.com/iller7/type-as-you-speak/issues/15); a recipe alone is not proof that a channel is published:

- **Arch / AUR:** the `packaging/aur/PKGBUILD.in` template (not a published AUR package)
- **Fedora / Copr:** `packaging/fedora/type-as-you-speak.spec`
- **Flatpak / Flathub:** `packaging/flatpak/…json` (experimental; desktop/sandbox validation remains open)

To build a matching distro package, use the container targets in the [packaging guide](https://github.com/iller7/type-as-you-speak/blob/master/packaging/README.md). These provide the required build tools and avoid mixing Python ABIs.

See [`packaging/README.md`](https://github.com/iller7/type-as-you-speak/blob/master/packaging/README.md) for the full per-channel notes.

### Verify

```bash
tays setup     # re-checks requirements and reports anything missing
tays status    # is a session running? on which model?
```

### Update

Because `install.sh` installs in editable mode, updating is just:

```bash
cd type-as-you-speak && git pull
```

New code applies immediately. Re-run `./install.sh` only if you also want to refresh the Python dependencies.

Package installs (`.deb`, and later AUR/Flatpak/Copr) update with their channel instead — e.g. `sudo apt install --only-upgrade ./tays.deb` when a newer release ships.

## Fedora 45 RPM profile

Fedora 45 uses Python 3.15 with Fedora's native ONNX Runtime package. Choose an RPM built for Fedora 45; installing it pulls in the native runtime dependency. Older releases may not provide this asset yet. To build the current checkout, run `make package-rpm` with Docker available; output is under `dist/packages/fedora/`, and filenames identify `fc45`. Fedora 44 remains a separate CI/build target.

The regular source installer still expects a PyPI-compatible Python 3.11–3.14 environment. On Fedora 45, use the native RPM route for now; source-installer adaptation is tracked in [#18](https://github.com/iller7/type-as-you-speak/issues/18). The package uses the system interpreter without replacing it. See the [distribution guide](https://github.com/iller7/type-as-you-speak/blob/master/packaging/README.md) for native/bundled dependency scope.

Strict offline dictation is enabled by default. Before the first session, run `tays download` or use the GUI Download button. Source installations also need `libseccomp2` (Debian/Ubuntu) or `libseccomp` (Fedora/Arch). Model downloads remain available during `tays setup --download-model`; see [privacy controls](privacy.md).

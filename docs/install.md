---
title: "Installation"
---

# Installation

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

For source installs, verify the client/daemon version and current distro availability. Debian 12 supplies an older ydotool, while Debian 13 may require backports or a reviewed source build. The new Debian/Ubuntu packages include private compatible tools. Source-installer validation is tracked under [T025](https://github.com/iller7/type-as-you-speak/issues/18).

The Whisper model (~1.5 GB for `medium.en`) is downloaded automatically on first run and cached under `~/.cache/huggingface`.

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

### Option C — ready-made `.deb` (CPU build)

Choose an asset from the [Releases page](https://github.com/iller7/type-as-you-speak/releases) that matches your distro and architecture. Published v0.5.1 predates the new distro-specific packaging. The following is the legacy v0.5.1 example:

```bash
curl -L -o tays.deb \
  https://github.com/iller7/type-as-you-speak/releases/download/v0.5.1/type-as-you-speak_0.5.1_amd64.deb
sudo apt install ./tays.deb
```

_(the filename carries the version — future releases are on the Releases page)_

All package-channel builds are **CPU builds** (no GPU in a sandbox) — the right choice if you don't need GPU acceleration. The power-user route (Options A/B) is the one that adds the CUDA build.

Other channels have recipes in the repository. Submission/publication status needs confirmation under [T010](https://github.com/iller7/type-as-you-speak/issues/15); a recipe alone is not proof that a channel is published:

- **Arch / AUR:** `packaging/aur/PKGBUILD`
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

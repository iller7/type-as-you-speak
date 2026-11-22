# Packaging

Distribution channels for **type-as-you-speak**. The public GitHub repository
is the single source of truth for every channel — nothing here duplicates code.

All store/distro builds are **CPU builds** (no CUDA/NVIDIA in a sandbox or
package — too heavy to share). The GPU path stays the power-user route:
`git clone` + `./install.sh`.

| Channel   | Path                    | User installs with                          |
|-----------|-------------------------|---------------------------------------------|
| Flatpak   | `flatpak/*.json`        | `flatpak install` / KDE Discover / Flathub  |
| AUR       | `aur/PKGBUILD`          | `yay -S type-as-you-speak`                  |
| Debian    | `deb/control` + `deb/build-deb.sh` | `apt install ./type-as-you-speak_*.deb` |
| Fedora    | `fedora/type-as-you-speak.spec`    | Copr project / `dnf copr enable`       |

## Shared app identity (in `../data/`)

- `type-as-you-speak.desktop` — menu entry; **Exec is `tays toggle`** (one
  press starts, next stops — the same behaviour as the Dictation key).
- `type-as-you-speak.metainfo.xml` — AppStream metadata (name, description,
  categories, keywords, releases, developer). Feeds Discover / GNOME
  Software / appstream-gtk.
- `icons/type-as-you-speak-{512,256,128,64,32}.png` — hicolor sizes.
  Transparent background; no embedded metadata.

App ID: `io.github.iller7.TypeAsYouSpeak` (AppStream + Flatpak).
Icon name: `type-as-you-speak`.

## Flatpak / Flathub

Manifest: `flatpak/io.github.iller7.TypeAsYouSpeak.json`.

Sandbox needs (all in `finish-args`):

- `--device=all` — `ydotoold` uses `/dev/uinput` for keystroke injection
- `--socket=pulseaudio` — mic capture (`ffmpeg -f pulse`) + output muting (`pactl`)
- `--socket=wayland` / `--socket=x11` + `--share=ipc` — clipboard fallback
  (`wl-copy` / `xclip`) and display
- `--share=network` — first-run model download (Hugging Face)
- `--filesystem=xdg-config` — user config · `--filesystem=xdg-cache` — model cache
- `org.freedesktop.Platform.ffmpeg8` extension — the `ffmpeg` binary
- modules: `ydotool` (CMake), `wl-clipboard` (meson), the app (pip, from tag)

The app **starts `ydotoold` itself** if it isn't running (`tays` →
`_prepare_env`), so no systemd service is needed inside the sandbox.

To submit to Flathub: fork/PR [flathub/flathub](https://github.com/flathub/flathub),
add the manifest (Flathub prefers the manifest at the repo root of its own
mirror; it pulls our git source by tag), and open the PR. The first build may
need small module fixes (e.g. a missing SDK dep) — the manifest is a
deliberately conservative starting point.

## AUR

`aur/PKGBUILD`. Uses Arch's `[extra]` Python packages
(`python-faster-whisper`, `python-onnxruntime`) and only bundles the app code.
**`sha256sums` is set from the tagged tarball** — when you bump `pkgver`,
recompute it (`sha256sum` of the release tarball).

## Debian / Ubuntu

`deb/build-deb.sh` produces `dist/type-as-you-speak_<ver>_<arch>.deb`:

```bash
./packaging/deb/build-deb.sh
apt install ./dist/type-as-you-speak_0.5.0_amd64.deb
```

Bundles the Python deps under `/opt/type-as-you-speak/pydeps` (Debian/Ubuntu
do not package faster-whisper) and declares the system tools
(`ydotool`, `wl-clipboard`, `xclip`, `ffmpeg`) as dependencies.

## Fedora / Copr

`fedora/type-as-you-speak.spec`. Create a
[Copr project](https://copr.fedorainfracloud.org/), point it at this repo
(spec path `fedora/type-as-you-speak.spec`, source = tagged tarball), and let
it build for the target Fedora release(s). Then users run:

```bash
dnf copr enable @<user>/type-as-you-speak
dnf install type-as-you-speak
```

# type-as-you-speak

Mac-like, **type-as-you-speak dictation for Linux (Wayland & X11).**

Press a key and the words you say are typed into the focused window *as you
talk* — no "record, then paste a blob" step. Each word is finalised with full
sentence context, so:

- **words never change** once they land (no live-region rewriting),
- **punctuation lands at real sentence ends**, not wherever your audio was cut,
- **spaces and casing come out right** between words and across pauses,
- a **hallucination filter** stops Whisper's stock "thanks for watching!" /
  "don't forget to subscribe!" closers (and its trailing "X X" repeats) from
  being typed when you pause.

It uses [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
(Whisper, CTranslate2 backend) for recognition, runs the model on your **GPU if
it's available** (otherwise CPU), and injects keystrokes with **ydotool** so it
works on any Wayland or X11 compositor.

> **Why this exists:** the hard part of Linux dictation isn't transcription —
> it's the system glue (injecting keystrokes into the focused window, muting
> output while the mic is live, and a one-key start/stop). That glue is
> fiddly per-desktop and nobody had productised it well, so this does.

> **100% local, by design.** This is *dictation, not transcription*: an input
> method, like a keyboard. All audio is processed on your machine with
> Whisper — nothing is uploaded, there's no account and no telemetry — and
> after the first model download it works completely offline.

---

## Requirements

| What | Why | Install |
|---|---|---|
| **Wayland or X11** (KDE, GNOME, Niri, Hyprland, …) | keystrokes are injected into the focused window | your compositor / window manager — either works |
| **NVIDIA GPU** *(optional, recommended)* | fast, low-CPU transcription | your driver — otherwise it runs on CPU (slower) |
| **Python 3.11–3.14** | the engine | `python3` |
| **ffmpeg** | mic capture | `apt install ffmpeg` / `dnf install ffmpeg` |
| **PulseAudio/PipeWire** (`pactl`) | mute output while the mic is live | usually present with any DE |
| **ydotool** + its daemon | type into the focused window | `apt install ydotool` / `dnf install ydotool` |
| **Clipboard** (`wl-copy` on Wayland, `xclip` on X11) | clipboard fallback if typing fails | `apt install wl-clipboard` / `apt install xclip` |
| **libnotify** (`notify-send`) | desktop notifications | usually present |

The Whisper model (~1.5 GB for `medium.en`) is downloaded automatically on
first run and cached under `~/.cache/huggingface`.

---

## Install

### Option A — clone + `install.sh` (recommended)

```bash
git clone https://github.com/iller7/type-as-you-speak.git
cd type-as-you-speak
./install.sh
```

`install.sh` is idempotent and does all the safe, user-owned setup: creates a
venv, installs the Python package **in editable mode** (so this repo stays the
single source of truth — `git pull` updates the tool with no reinstall), puts
`tays` on your PATH, makes sure the ydotool daemon (a systemd **user** service)
is running, and drops a sample config. It never uses `sudo` — any OS package
you're missing is printed with the exact install command.

### Option B — `pipx` / `pip`

```bash
pipx install "git+https://github.com/iller7/type-as-you-speak.git"
# or, into your own venv:
python3 -m venv .venv && .venv/bin/pip install "git+https://github.com/iller7/type-as-you-speak.git"
```

This gets you the `tays` command. You still need the OS prerequisites above
(especially **ydotool + its daemon**) — `pip` can't set those up, so prefer
`install.sh` if you want it all handled.

### Option C — ready-made `.deb` (CPU build)

The easiest first taste on a Debian/Ubuntu machine — the [latest
release](https://github.com/iller7/type-as-you-speak/releases) ships a
ready-made `.deb`:

```bash
curl -L -o tays.deb \
  https://github.com/iller7/type-as-you-speak/releases/latest/download/type-as-you-speak_0.5.1_amd64.deb
sudo apt install ./tays.deb
```

_(the filename carries the version — future releases are on the Releases page)_

All package-channel builds are **CPU builds** (no GPU in a sandbox) — the
right choice if you don't need GPU acceleration. The power-user route
(Options A/B) is the one that adds the CUDA build.

Other channels — **packaging is ready in-repo, publication is pending**:

- **Arch / AUR:** `packaging/aur/PKGBUILD` (AUR package not yet created)
- **Fedora / Copr:** `packaging/fedora/type-as-you-speak.spec` (not yet on Copr)
- **Flatpak / Flathub:** `packaging/flatpak/…json` (not yet submitted — once
  live, shows in KDE Discover / GNOME Software)

Prefer building the latest master yourself? `./packaging/deb/build-deb.sh` →
`sudo apt install ./dist/type-as-you-speak_*.deb`

See [`packaging/README.md`](packaging/README.md) for the full per-channel
notes.

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

New code applies immediately. Re-run `./install.sh` only if you also want to
refresh the Python dependencies.

Package installs (`.deb`, and later AUR/Flatpak/Copr) update with their
channel instead — e.g. `sudo apt install --only-upgrade ./tays.deb` when a
newer release ships.

---

## Usage

```bash
tays start     # run a live session in the foreground (ducks output; Ctrl-C stops)
tays stop      # stop the running session (commits pending text, restores volume)
tays toggle    # one-key: stop if running, else start — bind THIS to your Dictation key
tays status    # show state + the model/device in use + recent log
tays setup     # check requirements, enable the daemon, write a sample config
tays keybind   # print copy-paste steps to bind a Dictation key for your desktop
tays models    # list the Whisper models, their sizes, and your current choice
tays gui       # settings window: pick model & options, start/stop (optional extra)
```

**Typical day:** bind your Logitech **Dictation** key (or any spare key) to
`toggle`, then just press it, talk, press it again to stop. Background audio
is ducked (lowered to `duck_volume_pct`) while the mic is live and ramped back
up the moment the session ends.

### Bind the key

Easiest: `tays keybind` prints the exact steps for your desktop (auto-detects
KDE/GNOME/Sway/…; `--de <name>` to pick one).

- **OpenLogi:** the `KeyDictation` action → *Run shell command* → `tays toggle`.
- **KDE:** *System Settings → Keyboard → Custom Shortcuts* → new shortcut,
  action *Run command/URL* → `tays toggle`.
- **Any compositor:** point its keybinding at `tays toggle` (the repo also
  ships `bin/tays-toggle.sh`, which sets a safe environment first — useful when
  the key is triggered from a background agent).

### Settings window

Prefer picking options over editing TOML? Install the optional GUI extra and
open the settings window:

```bash
pip install 'type-as-you-speak[gui]'   # PySide6 + tomlkit (not in the core)
tays gui
```

It shows a live start/stop panel (driven by `tays status --json`, naming the
exact runtime device — e.g. "small.en on NVIDIA GeForce RTX 5090 (CUDA)";
while a session is running on one device but the config selects another, it
says "(configured: … — applies to the next session)" so the two never look
out of sync) and every config option, on three tabs:

- **General** — Model & device, Background audio
- **Corrections** — Hotwords and Hallucination tails. Each list has **one
  editor** (the words/phrases that are actually in effect — inline and file
  combined, one per line) and **one file entry** (where the list is kept;
  it comes pre-filled with the natural home next to your settings, and
  saving creates the file if it doesn't exist yet). Save writes the list to
  exactly one place — the file when a path is set (the inline copy is
  cleared so the list isn't in two places), or the settings when no path.
- **Advanced** — Typing & pacing, Decode stability

Details:

- **Language** is first (a dropdown with flags and native names —
  🇬🇧 English, 🇫🇷 Français, … — editable for the long tail): it decides
  what the model slider means.
- **Model size** is a **notched slider**, smallest → largest (tiny → base →
  small → medium → large-v3-turbo → large-v3). With English (or Auto-detect)
  the notches mean the English-only `.en` models (fastest and most accurate
  for English); with any other language they automatically mean the
  multilingual model of the same size. The line under the slider shows the
  current model as *downloaded* / *not downloaded*, and the **Download**
  button fetches the model at the current notch (it would be fetched at
  session start anyway — this just makes it visible and safe). A model set
  directly in the config that isn't on the slider is shown as-is, with a
  note.
- **Device** is a radio choice (Auto / GPU-CUDA / GPU-ROCm(AMD) / CPU) —
  each vendor option is enabled only when the *installed CTranslate2 build*
  can actually use that GPU (hardware presence alone isn't enough: an AMD
  iGPU with the CUDA build stays greyed out, with the reason in the
  tooltip). AMD ROCm needs CTranslate2's ROCm wheel (the standard pip
  install is CUDA/CPU only).
- **Background audio** — "Reduce background volume to (% — 0 = mute)"
  (that quiet-down is the so-called *ducking*) plus the fade time.
- **Hover any field** and the window's status bar explains what it does in
  plain English (plus a native tooltip).

**Save** writes your `config.toml` preserving its comments, and writes the
hotwords / tails files when their contents were edited; **Revert** reloads;
**Open config file** opens it in your editor. Changes apply to the next
session.

### Panel applet (KDE Plasma)

For an always-present mic icon in your panel — no window, no extra process
(it runs inside `plasmashell`, and drives `tays status --json` /
`tays toggle` as short-lived commands):

- **Grey mic icon** while stopped, **red** while the session is live.
- **Left-click** — status (model + where it's running — GPU name, or the
  CPU name on CPU) with Start/Stop and Settings; if an action fails, the
  popup says why instead of doing nothing.
- **Right-click** — Start/Stop (flips with the live state), Settings.

Install it (needs the app installed as above — the applet finds `tays` in
your usual locations; the mic icons go into your icon theme, where Plasma
looks for applet icons):

```bash
cd type-as-you-speak
./install.sh --applet
# or, manually:
#   mkdir -p ~/.local/share/icons/hicolor/scalable/apps
#   cp applet/contents/icons/*.svg ~/.local/share/icons/hicolor/scalable/apps/
#   cp -r applet ~/.local/share/plasma/plasmoids/org.iller7.tays
```

Then right-click your panel → **Add Widgets…** → search "type-as-you-speak"
→ add.

**Updating the applet:** remove it from the panel, re-run the install
step, re-add. Plasma keeps the version it first loaded in memory for the
life of the session — if the applet still misbehaves after remove/re-add,
the running session itself is holding the old code, and a desktop logout
(or restarting `plasmashell`) is the one-time fix.

---

## Configuration

Copy the sample and edit — every key is optional:

```bash
mkdir -p ~/.config/type-as-you-speak
cp config/default.toml ~/.config/type-as-you-speak/config.toml
```

| key | default | what it does |
|---|---|---|
| `model_name` | `small.en` | any faster-whisper model (`tiny.en`…`medium.en`…`large-v3`); see `tays models` |
| `device` | `auto` | `auto` = GPU if it fits else CPU · `cuda` = force NVIDIA GPU · `rocm` = force AMD GPU (needs the ROCm CTranslate2 build) · `cpu` = force CPU |
| `language` | `en` | Whisper language code |
| `cpu_threads` | `2` | cap on CTranslate2's CPU-side threads (narrows the per-round CPU burst) |
| `commit_lag_s` | `1.2` | how long a word is held before it's typed (the "Mac-like" lag) |
| `transcribe_every_s` | `0.9` | how often the pending audio is re-transcribed |
| `type_ms` | `5` | ydotool ms per key (raise to `10` if an app drops characters) |
| `hallucination_tails` | *(list)* | trailing phrases stripped before typing (add any you spot) |
| `hallucination_tails_file` | *(empty)* | path to a tails text file (one per line, `#` comments) — a shareable list; combined with the inline list (like `hotwords_file`) |
| `no_repeat_ngram_size` | `2` | blocks repeated N-grams in the decode (suppresses `Cl- Cl- Cl-` loops when the GPU is busy; `0` = off) |
| `condition_on_previous_text` | `false` | `false` = segments don't re-emit earlier text (suppresses duplicated phrases) |
| `hotwords` | *(empty)* | words/phrases to bias the decoder toward (proper nouns, names, jargon); comma-separated |
| `hotwords_file` | *(empty)* | path to a hotwords text file (one per line, `#` comments) — a shareable list; combined with the inline `hotwords` |
| `duck_volume_pct` | `5` | background audio duck level while dictating (% of sink volume; `0` = the old hard-mute) |
| `duck_ramp_ms` | `400` | fade time for the duck/restore ramps (ms) — the graceful dip and return |

Per-run overrides without editing the file:

```bash
DICTATE_DEVICE=cpu DICTATE_MODEL=small.en tays start
DICTATE_CPU_THREADS=4 tays start
```

Precedence: **env var > config file > built-in default**.

---

## How it works

1. **Capture** — the mic is read as ~0.3 s chunks (16 kHz mono) while a
   drainer thread keeps filling a buffer, so no early speech is lost.
2. **Listen** — each chunk is scored by Silero VAD (speech vs silence).
3. **Transcribe** — the audio you've heard but *not yet committed* is
   re-transcribed about every 0.9 s, always primed with the last words you
   already said, so Whisper continues your sentence instead of restarting it.
4. **Commit at word granularity** — only words that ended more than
   `commit_lag_s` ago are typed. That's what makes words finalise with full
   sentence context and then never change — exactly the macOS feel.
5. **Polish** — hyphenated words are re-joined, the leading capital after a
   mid-sentence pause is lower-cased, and Whisper's end-of-speech
   hallucinations are stripped before anything is typed.
6. **Type** — keystrokes go to the focused window via ydotool (clipboard
   fallback if that fails). Output stays muted for the whole session.

Recognition is on the GPU (float16) when available; the CPU only does light
bookkeeping, so the per-second cost is a brief, small burst rather than
sustained load.

---

## GPU vs CPU

- **`device = "auto"`** (default): tries the GPU with the biggest model it can
  hold, then falls back to CPU. Good default if other apps (e.g. an LLM) are
  reserving some VRAM.
- **`device = "cuda"`**: forces the GPU and fails clearly if none is usable —
  no silent slow-CPU fallback.
- **`device = "cpu"`**: always CPU (int8). Works on any machine, just slower.

Pick a smaller `model_name` (e.g. `small.en`) to reduce per-round GPU/CPU cost
and increase transcription rate, at a small accuracy cost.

---

## Troubleshooting

- **Nothing types, but I hear a "copied to clipboard" notification** — ydotool
  failed to inject. Check `systemctl --user status ydotoold`, that you're in
  the distro service and narrowly scoped `/dev/uinput` permissions (see SECURITY.md), and that `ydotool key F13` (or similar) works
  by hand.
- **Keys are dropped or doubled** — raise `type_ms` to `10`.
- **Words keep changing / punctuation is off** — raise `commit_lag_s` a touch
  (e.g. `1.4`) so more context is available when a word is finalised.
- **It types a closing phrase I didn't say** — add that phrase (lowercase) to
  `hallucination_tails`.
- **`libcublas.so.12 is not found`** — your `faster-whisper`/`ctranslate2`
  build isn't seeing the CUDA libraries; a clean reinstall into the venv fixes
  it: `venv/bin/pip install -U faster-whisper`.
- **`tays: command not found`** — `~/.local/bin` isn't on your PATH, or run
  `venv/bin/tays` directly; re-run `./install.sh`.
- **Where's the log?** — `~/.local/state/type-as-you-speak/live.log`.

---

## Development

```bash
git clone https://github.com/iller7/type-as-you-speak.git && cd type-as-you-speak
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/tays start        # or: DICTATE_WAV=audio.wav tays start  (test without a mic)
```

The engine is `src/type_as_you_speak/engine.py`; tunables live in
`src/type_as_you_speak/config.py` (defaults mirrored in `config/default.toml`).

---

## License

MIT — see [LICENSE](LICENSE).

## Development and distribution

Use `make setup`, `make check` and `make build` for a locked development environment, tests and package validation. See [CONTRIBUTING.md](CONTRIBUTING.md) for desktop QA, [packaging/README.md](packaging/README.md) for the distro/ABI matrix, and [SECURITY.md](SECURITY.md) for input-device and diagnostics privacy.

Development uses Python 3.14; Linux compatibility checks cover 3.11–3.14. Dependencies are recorded in `uv.lock`. New native packages carry a distro-specific filename and include the settings window. Published v0.5.1 assets above predate this packaging change; future releases use the matching distro asset on the Releases page. Flatpak remains experimental. macOS and Windows checks cover portable code only; desktop dictation on those platforms is not available yet.

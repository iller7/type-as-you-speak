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

---

## Demo

_A screen-capture GIF is coming soon._

<!-- When a demo is ready, drop `docs/demo.gif` (or a screenshot) in the repo
     and replace the line above with, e.g.:

     ![type-as-you-speak in action](docs/demo.gif)
-->

---

## Requirements

| What | Why | Install |
|---|---|---|
| **Wayland or X11** (KDE, GNOME, Niri, Hyprland, …) | keystrokes are injected into the focused window | your compositor / window manager — either works |
| **NVIDIA GPU** *(optional, recommended)* | fast, low-CPU transcription | your driver — otherwise it runs on CPU (slower) |
| **Python 3.11+** | the engine | `python3` |
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

---

## Usage

```bash
tays start     # run a live session in the foreground (mutes output; Ctrl-C stops)
tays stop      # stop the running session (commits pending text, unmutes)
tays toggle    # one-key: stop if running, else start — bind THIS to your Dictation key
tays status    # show state + the model/device in use + recent log
tays setup     # check requirements, enable the daemon, write a sample config
tays keybind   # print copy-paste steps to bind a Dictation key for your desktop
```

**Typical day:** bind your Logitech **Dictation** key (or any spare key) to
`toggle`, then just press it, talk, press it again to stop. Output is muted
while the mic is live so you don't hear yourself; it's unmuted the moment the
session ends.

### Bind the key

Easiest: `tays keybind` prints the exact steps for your desktop (auto-detects
KDE/GNOME/Sway/…; `--de <name>` to pick one).

- **OpenLogi:** the `KeyDictation` action → *Run shell command* → `tays toggle`.
- **KDE:** *System Settings → Keyboard → Custom Shortcuts* → new shortcut,
  action *Run command/URL* → `tays toggle`.
- **Any compositor:** point its keybinding at `tays toggle` (the repo also
  ships `bin/tays-toggle.sh`, which sets a safe environment first — useful when
  the key is triggered from a background agent).

---

## Configuration

Copy the sample and edit — every key is optional:

```bash
mkdir -p ~/.config/type-as-you-speak
cp config/default.toml ~/.config/type-as-you-speak/config.toml
```

| key | default | what it does |
|---|---|---|
| `model_name` | `medium.en` | any faster-whisper model (`small.en`, `base.en`, `large-v3`, …) |
| `device` | `auto` | `auto` = GPU if it fits else CPU · `cuda` = force GPU · `cpu` = force CPU |
| `language` | `en` | Whisper language code |
| `cpu_threads` | `2` | cap on CTranslate2's CPU-side threads (narrows the per-round CPU burst) |
| `commit_lag_s` | `1.2` | how long a word is held before it's typed (the "Mac-like" lag) |
| `transcribe_every_s` | `0.9` | how often the pending audio is re-transcribed |
| `type_ms` | `5` | ydotool ms per key (raise to `10` if an app drops characters) |
| `hallucination_tails` | *(list)* | trailing phrases stripped before typing (add any you spot) |

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
  the `input` group (`id -nG`), and that `ydotool key F13` (or similar) works
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

AGPL-3.0-only — see [LICENSE](LICENSE).

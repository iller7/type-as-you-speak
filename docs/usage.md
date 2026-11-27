---
title: "Usage"
---

# Usage

Download your selected model first with `tays download`, `tays setup --download-model`, or the GUI Download button. Strict offline dictation is on by default; see [privacy controls](privacy.md).

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

**Typical day:** bind your Logitech **Dictation** key (or any spare key) to `toggle`, then just press it, talk, press it again to stop. Background audio is ducked (lowered to `duck_volume_pct`) while the mic is live and ramped back up the moment the session ends.

## Bind the key

Easiest: `tays keybind` prints the exact steps for your desktop (auto-detects KDE/GNOME/Sway/…; `--de <name>` to pick one).

- **OpenLogi:** the `KeyDictation` action → _Run shell command_ → `tays toggle`.
- **KDE:** _System Settings → Keyboard → Custom Shortcuts_ → new shortcut, action _Run command/URL_ → `tays toggle`.
- **Any compositor:** point its keybinding at `tays toggle` (the repo also ships `bin/tays-toggle.sh`, which sets a safe environment first — useful when the key is triggered from a background agent).

## Settings window

For a source install using the default install.sh location, run this from the repository to install the optional GUI and open settings. If TAYS_HOME overrides the install location, use that environment instead:

```bash
"$HOME/.local/share/type-as-you-speak/venv/bin/python" -m pip install -e ".[gui]"
tays gui
```

It shows a live start/stop panel (driven by `tays status --json`, naming the exact runtime device — e.g. "small.en on NVIDIA GeForce RTX 5090 (CUDA)"; while a session is running on one device but the config selects another, it says "(configured: … — applies to the next session)" so the two never look out of sync) and every config option, on three tabs:

- **General** — Model & device, Background audio
- **Corrections** — Hotwords and Hallucination tails. Each list has **one editor** (the words/phrases that are actually in effect — inline and file combined, one per line) and **one file entry** (where the list is kept; it comes pre-filled with the natural home next to your settings, and saving creates the file if it doesn't exist yet). Save writes the list to exactly one place — the file when a path is set (the inline copy is cleared so the list isn't in two places), or the settings when no path.
- **Advanced** — Typing & pacing, Decode stability

Details:

- **Language** is first (a dropdown with flags and native names — 🇬🇧 English, 🇫🇷 Français, … — editable for the long tail): it decides what the model slider means.
- **Model size** is a **notched slider**, smallest → largest (tiny → base → small → medium → large-v3-turbo → large-v3). With English (or Auto-detect) the notches mean the English-only `.en` models (fastest and most accurate for English); with any other language they automatically mean the multilingual model of the same size. The line under the slider shows the current model as _downloaded_ / _not downloaded_, and the **Download** button fetches the model at the current notch (it would be fetched at session start anyway — this just makes it visible and safe). A model set directly in the config that isn't on the slider is shown as-is, with a note.
- **Device** is a radio choice (Auto / GPU-CUDA / GPU-ROCm(AMD) / CPU) — each vendor option is enabled only when the _installed CTranslate2 build_ can actually use that GPU (hardware presence alone isn't enough: an AMD iGPU with the CUDA build stays greyed out, with the reason in the tooltip). AMD ROCm needs CTranslate2's ROCm wheel (the standard pip install is CUDA/CPU only).
- **Background audio** — "Reduce background volume to (% — 0 = mute)" (that quiet-down is the so-called _ducking_) plus the fade time.
- **Hover any field** and the window's status bar explains what it does in plain English (plus a native tooltip).

**Save** writes your `config.toml` preserving its comments, and writes the hotwords / tails files when their contents were edited; **Revert** reloads; **Open config file** opens it in your editor. Changes apply to the next session.

## Panel applet (KDE Plasma)

For an always-present mic icon in your panel — no window, no extra process (it runs inside `plasmashell`, and drives `tays status --json` / `tays toggle` as short-lived commands):

- **Grey mic icon** while stopped, **red** while the session is live; the tooltip shows the model and where it's running (GPU name, or the CPU name on CPU).
- **Click (left or right)** — one short menu: Start/Stop (flips with the live state), Settings…, and the project page.

Install it (needs the app installed as above — the applet finds `tays` in your usual locations; the mic icons go into your icon theme, where Plasma looks for applet icons):

```bash
cd type-as-you-speak
./install.sh --applet
# or, manually:
#   mkdir -p ~/.local/share/icons/hicolor/scalable/apps
#   cp applet/contents/icons/*.svg ~/.local/share/icons/hicolor/scalable/apps/
#   cp -r applet ~/.local/share/plasma/plasmoids/org.iller7.tays
```

Then right-click your panel → **Add Widgets…** → search "type-as-you-speak" → add.

**Updating the applet:** remove it from the panel, re-run the install step, re-add. Plasma keeps the version it first loaded in memory for the life of the session — if the applet still misbehaves after remove/re-add, the running session itself is holding the old code, and a desktop logout (or restarting `plasmashell`) is the one-time fix.

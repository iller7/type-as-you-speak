# Changelog

All notable changes to **type-as-you-speak** are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **Settings GUI — `tays gui`** (optional `gui` extra: PySide6 + tomlkit):
  a window to pick models and options instead of editing TOML — General
  tab (Model & device, Background audio), Corrections tab (hotwords +
  hallucination tails, each inline and file-backed), and Advanced tab
  (Typing & pacing, Decode stability). Model picker marks each model
  *downloaded* / *not downloaded* with an on-demand **Download** button;
  device is a radio choice (Auto / GPU-CUDA / GPU-ROCm(AMD) / CPU — vendor
  options greyed out with a reason when absent); language is a dropdown of
  flags + native names; hovering any field shows what it does. Saving
  preserves the config file's comments.
- **`status --json` / `stop --json` / `toggle --json`:** machine-readable
  state (running, pid, model, device, **and the exact runtime GPU**) —
  the contract desktop applets drive the app through.
- **Audio ducking instead of hard-mute:** while the mic is live the
  default sink is lowered to `duck_volume_pct` (default 5%) with a
  graceful fade (`duck_ramp_ms`, default 400 ms) and ramped back up on
  stop — background music keeps playing quietly. `duck_volume_pct = 0`
  restores the old hard-mute. A hard-killed session's duck state is
  restored on the next start.
- **`hotwords` + `hotwords_file` config keys:** bias the decoder toward
  words Whisper otherwise mishears (proper nouns, names, jargon).
  `hotwords` is an inline comma-separated list; `hotwords_file` points at a
  plain text file (one entry per line, `#` comments allowed) — a shareable
  list for a team or topic. Both combine, deduped case-insensitively.
  A starter list ships at `config/hotwords.example.txt` and `tays setup`
  drops a copy next to your config. (`DICTATE_HOTWORDS` /
  `DICTATE_HOTWORDS_FILE` overrides.)
- **CPU fallback model `small.en`:** when the GPU decode is unstable, the
  session continues on CPU `small.en` int8 (was `base.en`).
- **KDE Plasma panel applet** (`org.iller7.tays`): an always-present mic
  icon in the panel — **grey** while stopped, **red** while a dictation
  session is live. Left-click pops up the status (model + actual GPU) with
  Start/Stop and Settings (failures are shown in the popup instead of doing
  nothing); right-click gives the full menu (Start/Stop, Settings →
  `tays gui --detach`, Status, About). Runs entirely inside `plasmashell`
  — no extra process, no daemon — driving `tays status --json` /
  `tays toggle` as short-lived commands and finding `tays` in the usual
  install locations. Shipped at `applet/` in the repo; `./install.sh
  --applet` installs it plus the mic icons into the icon theme (where
  Plasma looks for applet icons).
- **`tays gui --detach`:** launches the settings window in its own session
  and returns immediately — used by the panel applet so it is never blocked
  for the lifetime of the window.
- **`hallucination_tails_file`:** a file of extra tail phrases (one per
  line, `#` comments allowed), combined with the inline
  `hallucination_tails` list and deduped — the shareable-list treatment of
  `hotwords_file`, mirrored for tails (`DICTATE_TAILS_FILE` override).
- **Corrections tab in the settings GUI (redesigned):** hotwords and
  hallucination tails each get **one editor** showing the list that's
  actually in effect (inline + file combined, one per line) and **one file
  entry** — pre-filled with the natural home next to your settings (e.g.
  `~/.config/type-as-you-speak/hotwords.txt`), so there is always a visible,
  sensible path and an existing hotwords file is picked up and wired in on
  Save. Save writes the list to exactly one place — the file when a path is
  set (the inline copy is cleared so the list isn't duplicated), or the
  settings when no path is set.
- **Model ↔ language sync in the settings GUI:** with a non-English language
  selected, English-only `.en` models are marked "English only"; picking
  one points at (or auto-switches to) its multilingual twin
  (tiny/base/small/medium) when that is already downloaded. Dictating, say,
  French into `small.en` is the top cause of degraded recognition — this
  surfaces and fixes it.
- **Settings GUI status-line sync:** while a session is running on one
  device and the config selects another, the status line appends
  "(configured: … — applies to the next session)" — the panel and the radio
  buttons can no longer look out of sync.

### Changed
- **Settings GUI device radios gated on the installed CTranslate2 build:**
  a vendor option (CUDA / ROCm) is enabled only when the installed build
  can actually use that GPU — hardware presence alone no longer enables it.
  (An AMD iGPU with the CUDA build now greys out ROCm and explains why in
  the tooltip.)
- **Settings GUI i18n-ready:** all window strings route through
  `QObject.tr()` (and the applet uses QML `i18n()`), ready for `.ts`/`.qm`
  translations.
- **Settings GUI help text rewritten in plain English:** every hover
  explanation now starts with what the option does in everyday language
  ("How quiet the music and other sound get while you're talking…"), with
  the technical detail after — no degree required.

### Fixed
- **Dictation duplicated everything (two sessions at once):** `tays start`
  had no single-instance guard — a second `start` while a session ran
  launched a second engine and overwrote the pidfile (the first became an
  unstoppable zombie); both listened on the same mic and both typed into
  the same window, so every phrase landed 2–3×. `start` now refuses when a
  session is already running ("already running (pid N) — use 'tays stop'
  first") and the engine logs its own pid so log lines are attributable.
  (`toggle` was already safe.)
- **Applet blank icon + empty popup:** the QML called `Qt.env("HOME")`,
  which does not exist in QML — the resulting TypeError killed the icon
  binding and the popup at once. Command paths now use `$HOME` shell
  expansion (the `executable` data source runs commands through a shell),
  verified under plasmashell's own environment. Follow-ups from the first
  re-add: the **icon was still blank** because applet icons resolve through
  the icon theme (no system applet ships `contents/icons`) — the mic icons
  are now installed into the `hicolor` theme by `./install.sh --applet`;
  and **Settings did nothing** because (a) the running `plasmashell` kept
  the first-compiled version of the applet in memory for the life of the
  session (the applet now ships under a fresh package id, `org.iller7.tays`,
  which loads cleanly; if a session ever holds stale code, a desktop logout
  clears it) and (b) the settings window ran in the foreground, holding the
  applet's "busy" flag — it now launches with `tays gui --detach`.
- **GUI model download result clobbered:** the status timer re-consumed the
  finished download every tick, so the true outcome (e.g. a successful
  "Downloaded ✓") was overwritten by "unknown error" a second later. The
  result is now consumed exactly once; the final message stays. Related:
  `large-v3-turbo` was always shown "not downloaded" (its Hugging Face repo
  is `mobiuslabsgmbh/…`, not `Systran/…`) — availability now resolves the
  repo via faster-whisper's own mapping, and downloads log to
  `~/.local/state/type-as-you-speak/model-download.log`.
- **Degenerate decodes under GPU contention** (observed with Ollama serving
  on the same GPU): repetition loops (`Cl- Cl- Cl-`), re-emitted phrases
  (the same sentence typed 3–4×), and mishears. Suppressed at the decode
  level (`no_repeat_ngram_size=2`, `condition_on_previous_text=false` —
  both configurable, `0`/`true` restores old behaviour) and at the commit
  level (runs of the same word 2+ are stripped).
- **Stray trailing hallucinations over silence** (`All right.` on 0.14 s,
  `you` on 0.08 s, `ships.` on 0.18 s, `Hi.` after a long pause): a trailing
  run stamped faster than ~0.1 s per word is dropped, and a trailing word
  whose audio span has no VAD speech energy is dropped (max two, real words
  untouched).
- **Hotword prompt leaks:** whisper can re-emit the hotword prompt itself as
  "transcription" (observed: `for the Linux, glue, productised, per-disk,
  for all the` stamped over 0.06 s). A segment naming 3+ distinct hotwords
  is now dropped as a leak and logged; the real words around it survive.
- **Tail recovery re-decoding your silence:** the leftover-audio recovery
  path now checks the VAD first (its own comment always claimed it did) —
  a silent tail is consumed instead of being re-decoded into a hallucinated
  closing word. Recovered words pass the same trailing guard as the main
  path, and genuine recoveries (real speech the model stopped before) still
  work.
- **False CPU-fallback trigger:** the repetition-loop tripwire now requires
  3+ back-to-back (a Whisper segmentation stutter on a legit word like
  `end end` no longer locks the session to CPU).

## [0.5.1] - 2026-11-23

### Changed
- **New app icon:** a clean, simplified vector design (smooth edges, no bitmap
  noise) in a soft pastel palette — periwinkle outline and stand, mint top,
  coral body, and a soft-rose accent band. Shipped as a hand-authored SVG
  master plus all five rendered PNG sizes (512/256/128/64/32), so the icon in
  every package is crisp and metadata-free.

### Added
- **Automated release pipeline:** a GitHub Actions `release` workflow that, on
  a `v*` tag, checks the tag matches the project version, builds the sdist,
  wheel, and a `.deb`, and publishes them as a GitHub release with the
  CHANGELOG slice as the notes.
- **`RELEASES.md`:** the step-by-step checklist for cutting a release through
  the new pipeline (tag → CI → artifacts → AUR hash update).

## [0.5.0] - 2026-11-22

### Added
- **App identity:** an icon (transparent background, no embedded metadata), a
  `.desktop` file, and AppStream `.metainfo.xml` in `data/` — so the app shows
  up cleanly in app stores (KDE Discover / KDE Marketplace via Flathub, GNOME
  Software, …).
- **Packaging scaffolds for the distribution channels**, all CPU builds, under
  `packaging/`: a Flatpak/Flathub manifest, an AUR `PKGBUILD`, a `.deb`
  builder (`build-deb.sh`), and a Fedora/Copr `spec`.
- `tays` now **auto-starts the `ydotoold` daemon** if it isn't running (needed
  inside the Flatpak sandbox, and handy on any host without a user service).

## [0.4.0] - 2026-11-22

### Added
- **`tays models`** — lists the Whisper models with their download sizes and a
  one-line note each, and marks your current choice.
- **`tays start --model NAME`** (and `tays toggle --model NAME`) — pick a model
  for a single run without editing config (sets `DICTATE_MODEL`).

### Changed
- **Default model is now `small.en`** (~484 MB) — a lighter, faster first-run
  that still sounds good. Bump to `medium.en` or `large-v3-turbo` for more
  accuracy. (Set your own in `~/.config/type-as-you-speak/config.toml`.)

## [0.3.0] - 2026-11-22

### Added
- **`tays keybind`** helper: prints the exact, copy-paste steps to bind a
  Dictation key for your desktop — auto-detects KDE / GNOME / Sway / Hyprland /
  XFCE, or `--de <name>` to target one. It recommends the env-safe wrapper
  already on your PATH and notes the binding is a *run-command* (so it never
  types into your window). `tays setup` now points here too.

## [0.2.0] - 2026-11-22

### Added
- **X11 support.** Keystroke injection via `ydotool` already works on both
  Wayland and X11; the clipboard-fallback tool is now chosen per session
  (`wl-copy` on Wayland, `xclip` on X11). `install.sh`, `tays setup`, and the
  docs no longer treat X11 as unsupported — a GUI session (Wayland *or* X11)
  is all that's required. On X11, install `xclip` for the clipboard fallback.

## [0.1.1] - 2026-11-22

### Fixed
- **Hallucination filter now strips Whisper's stock "closing" phrases wherever
  they appear in a commit — not only at the tail.** A spliced-in phrase such as
  `… what would it take? Thank you for watching. Please` is now cleaned even
  when real words follow it (Whisper inserts these mid-stream, not just at the
  end). `clean_hallucinations` was also lifted to a module-level, testable
  function.

## [0.1.0] - 2026-11-22

### Added
- First public release: Mac-like, **type-as-you-speak dictation for Linux
  (Wayland)** — the words you say are typed into the focused window as you talk.
- `tays` CLI: `start` / `stop` / `toggle` / `status` / `setup`.
- Config-driven: `config/default.toml`, a user file at
  `~/.config/type-as-you-speak/config.toml`, and `DICTATE_*` env overrides.
- GPU auto-detect (`auto` | `cuda` | `cpu`) using the CTranslate2 CUDA build,
  with a CPU fallback.
- `install.sh`: idempotent, no `sudo`, and an **editable install** so the repo
  stays the single source of truth (`git pull` updates the tool with no
  reinstall).
- Silero VAD, streaming commit with sentence-context finalisation, prompt-echo
  stripping, trailing-hallucination filter, output muting while live, and a
  `DICTATE_DRY_RUN` test mode.

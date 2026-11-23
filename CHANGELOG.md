# Changelog

All notable changes to **type-as-you-speak** are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
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

### Fixed
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

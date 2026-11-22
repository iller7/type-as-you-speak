# Changelog

All notable changes to **type-as-you-speak** are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project follows [Semantic Versioning](https://semver.org/).

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

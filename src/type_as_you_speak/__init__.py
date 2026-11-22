"""type-as-you-speak — Mac-like, type-as-you-speak dictation for Linux (Wayland & X11).

Press a key and the words you speak are typed into the focused window as you
talk: each word finalises with full sentence context, so it never changes and
punctuation lands at real sentence ends.

Modules:
  config  — tunables + defaults (TOML / env / built-ins), no heavy deps
  engine  — the live streaming session (faster-whisper, word-level commits)
  cli     — the `tays` command (start / stop / toggle / status / setup)
"""

__version__ = "0.2.0"

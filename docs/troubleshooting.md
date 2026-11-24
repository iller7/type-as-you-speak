---
title: "Troubleshooting"
---

# Troubleshooting

- **Nothing types, but I hear a "copied to clipboard" notification** — ydotool failed to inject. Check the configured daemon socket and narrowly scoped `/dev/uinput` permissions; see [SECURITY.md](https://github.com/iller7/type-as-you-speak/blob/master/SECURITY.md). Source installs may use the distro service; Debian/Ubuntu packages also include private input tools. Use a disposable editor when testing input.
- **Keys are dropped or doubled** — raise `type_ms` to `10`.
- **Words keep changing / punctuation is off** — raise `commit_lag_s` a touch (e.g. `1.4`) so more context is available when a word is finalised.
- **It types a closing phrase I didn't say** — add that phrase (lowercase) to `hallucination_tails`.
- **`libcublas.so.12 is not found`** — the inference backend cannot find the required NVIDIA runtime libraries. Check the backend/driver compatibility and the source installer's CUDA runtime step. Do not assume upgrading faster-whisper alone supplies those libraries; hardware QA remains [T005](https://github.com/iller7/type-as-you-speak/issues/8).
- **`tays: command not found`** — `~/.local/bin` isn't on your PATH, or run `venv/bin/tays` directly; re-run `./install.sh`.
- **Where's the log?** — `~/.local/state/type-as-you-speak/live.log`.

---
title: "How it works"
---

# How it works

1. **Capture** — the mic is read as ~0.3 s chunks (16 kHz mono) while a drainer thread keeps filling a buffer, so no early speech is lost.
2. **Listen** — each chunk is scored by Silero VAD (speech vs silence).
3. **Transcribe** — the audio you've heard but _not yet committed_ is re-transcribed about every 0.9 s, always primed with the last words you already said, so Whisper continues your sentence instead of restarting it.
4. **Commit at word granularity** — only words that ended more than `commit_lag_s` ago are typed. That's what makes words finalise with full sentence context and then never change — exactly the macOS feel.
5. **Polish** — hyphenated words are re-joined, the leading capital after a mid-sentence pause is lower-cased, and Whisper's end-of-speech hallucinations are stripped before anything is typed.
6. **Type** — keystrokes go to the focused window via ydotool (clipboard fallback if that fails). Background output is ducked while the session is active; setting duck_volume_pct to zero uses muting.

Recognition uses a compatible GPU when available or the CPU. Measure latency and contention on the target hardware; container checks do not establish real-time performance.

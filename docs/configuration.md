# Configuration

Copy the sample and edit — every key is optional:

```bash
mkdir -p ~/.config/type-as-you-speak
cp config/default.toml ~/.config/type-as-you-speak/config.toml
```

| key                          | default    | what it does                                                                                                                                 |
| ---------------------------- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `model_name`                 | `small.en` | any faster-whisper model (`tiny.en`…`medium.en`…`large-v3`); see `tays models`                                                               |
| `device`                     | `auto`     | `auto` = GPU if it fits else CPU · `cuda` = force NVIDIA GPU · `rocm` = force AMD GPU (needs the ROCm CTranslate2 build) · `cpu` = force CPU |
| `language`                   | `en`       | Whisper language code                                                                                                                        |
| `cpu_threads`                | `2`        | cap on CTranslate2's CPU-side threads (narrows the per-round CPU burst)                                                                      |
| `commit_lag_s`               | `1.2`      | how long a word is held before it's typed (the "Mac-like" lag)                                                                               |
| `transcribe_every_s`         | `0.9`      | how often the pending audio is re-transcribed                                                                                                |
| `type_ms`                    | `5`        | ydotool ms per key (raise to `10` if an app drops characters)                                                                                |
| `hallucination_tails`        | _(list)_   | trailing phrases stripped before typing (add any you spot)                                                                                   |
| `hallucination_tails_file`   | _(empty)_  | path to a tails text file (one per line, `#` comments) — a shareable list; combined with the inline list (like `hotwords_file`)              |
| `no_repeat_ngram_size`       | `2`        | blocks repeated N-grams in the decode (suppresses `Cl- Cl- Cl-` loops when the GPU is busy; `0` = off)                                       |
| `condition_on_previous_text` | `false`    | `false` = segments don't re-emit earlier text (suppresses duplicated phrases)                                                                |
| `hotwords`                   | _(empty)_  | words/phrases to bias the decoder toward (proper nouns, names, jargon); comma-separated                                                      |
| `hotwords_file`              | _(empty)_  | path to a hotwords text file (one per line, `#` comments) — a shareable list; combined with the inline `hotwords`                            |
| `duck_volume_pct`            | `5`        | background audio duck level while dictating (% of sink volume; `0` = the old hard-mute)                                                      |
| `duck_ramp_ms`               | `400`      | fade time for the duck/restore ramps (ms) — the graceful dip and return                                                                      |

Per-run overrides without editing the file:

```bash
DICTATE_DEVICE=cpu DICTATE_MODEL=small.en tays start
DICTATE_CPU_THREADS=4 tays start
```

Precedence: **env var > config file > built-in default**.

## GPU vs CPU

- **`device = "auto"`** (default): tries the GPU with the biggest model it can hold, then falls back to CPU. Good default if other apps (e.g. an LLM) are reserving some VRAM.
- **`device = "cuda"`**: forces the GPU and fails clearly if none is usable — no silent slow-CPU fallback.
- **`device = "cpu"`**: always CPU (int8). Works on any machine, just slower.

Pick a smaller `model_name` (e.g. `small.en`) to reduce per-round GPU/CPU cost and increase transcription rate, at a small accuracy cost.

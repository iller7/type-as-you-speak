"""Configuration for type-as-you-speak.

Precedence (highest wins):
  1. Environment variables — quick, per-run overrides (DICTATE_*).
  2. User config file — ~/.config/type-as-you-speak/config.toml
     (copy config/default.toml there and edit).
  3. Built-in defaults — the values the engine always worked with.

The engine reads a flat dict of keys from load_config(); see the keys below.
"""
import os
from pathlib import Path

# Built-in defaults (identical to the original hard-coded values).
DEFAULTS = {
    # model / device
    "model_name": "small.en",       # default: good everyday balance (tiny/base/small.en, medium.en, large-v3, …)
    "language": "en",
    "device": "auto",               # auto | cuda | cpu   (auto = GPU if present, else CPU)
    "cpu_threads": 2,               # CTranslate2 CPU-side threads (caps the per-round CPU spike)
    # typing
    "type_ms": 5,                   # ydotool ms per key (raise to 10 if an app drops chars)
    # streaming (Mac-like) behaviour
    "chunk_s": 0.3,                 # audio chunk size (loop pacing)
    "vad_threshold": 0.5,           # mean Silero probability that counts as speech
    "transcribe_every_s": 0.9,      # re-transcribe the pending audio this often while talking
    "commit_lag_s": 1.2,            # hold this much recent audio uncommitted (words finalise with context)
    "silence_commit_s": 1.0,        # after this much silence, commit the remaining tail
    "min_pending_s": 0.7,           # don't transcribe less than this of pending audio
    "max_pending_s": 8.0,           # safety cap: force progress if pending keeps growing
    "prompt_tail_words": 12,        # committed words used as context for the next chunk
    "max_session_s": 600.0,         # safety cap only (10 min) so a forgotten session can't run forever
    "prebuf_cap_s": 15.0,           # keep at most this much audio recorded during model load
    # Decode stability (matters when the GPU is busy — e.g. Ollama on the same card):
    # under contention the beam search degenerates into repetition loops
    # ("Cl- Cl- Cl-") and re-emitted phrases. These two suppress that at the source.
    "no_repeat_ngram_size": 2,      # 0 = off; block repeated N-grams (kills the repetition loops)
    "condition_on_previous_text": False,  # don't let whisper re-emit earlier segments in a call
    # Whisper "end-of-speech" hallucinations: when it hits trailing silence it emits a
    # stock closing line (or re-emits your last phrase). These trailing phrases are
    # stripped before typing (see clean_hallucinations in engine.py). Add any you spot.
    "hallucination_tails": [
        "thanks for watching",
        "thank you for watching",
        "don't forget to subscribe",
        "dont forget to subscribe",
        "don't forget to like the video",
        "subscribe to my channel",
        "hope you enjoyed this video",
        "see you in the next video",
        "i'll see you in the next video",
        "ill see you in the next video",
        "see you in the next one",
        "see you next time",
        "voice to text",
    ],
}

def _env_bool(raw: str) -> bool:
    return raw.strip().lower() in ("1", "true", "yes", "on")


# Environment variable -> config key (quick overrides).
_ENV_MAP = {
    "DICTATE_MODEL": ("model_name", str),
    "DICTATE_LANG": ("language", str),
    "DICTATE_DEVICE": ("device", str),
    "DICTATE_TYPE_MS": ("type_ms", int),
    "DICTATE_CPU_THREADS": ("cpu_threads", int),
    "DICTATE_COMMIT_LAG_S": ("commit_lag_s", float),
    "DICTATE_TRANSCRIBE_EVERY_S": ("transcribe_every_s", float),
    "DICTATE_NO_REPEAT_NGRAM_SIZE": ("no_repeat_ngram_size", int),
    "DICTATE_CONDITION_ON_PREVIOUS_TEXT": ("condition_on_previous_text", _env_bool),
}


def user_config_path() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return Path(xdg) / "type-as-you-speak" / "config.toml"


def _load_user_config() -> dict:
    p = user_config_path()
    if not p.is_file():
        return {}
    try:
        import tomllib
        with open(p, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        return {}
    flat = {}
    for k, v in data.items():
        if isinstance(v, dict):          # allow [model] name = … style grouping
            flat.update(v)
        else:
            flat[k] = v
    return flat


def load_config() -> dict:
    cfg = {k: (list(v) if isinstance(v, list) else v) for k, v in DEFAULTS.items()}
    user = _load_user_config()
    for k, v in user.items():
        if k in cfg:
            cfg[k] = v
    for env, (key, conv) in _ENV_MAP.items():
        if env in os.environ:
            raw = os.environ[env]
            try:
                cfg[key] = conv(raw)
            except (ValueError, TypeError):
                pass
    return cfg

#!/usr/bin/env python3
"""Live dictation session: types into the focused window as you speak.

Flow (streaming, Mac-like):
  1. start mic capture (audio is buffered while the model loads)
  2. load Whisper model (GPU, CPU fallback) + warm up
  3. loop over ~0.3 s chunks:
       - VAD marks speech vs silence
       - heard-but-uncommitted audio is re-transcribed every ~0.9 s
       - only words older than COMMIT_LAG_S are typed: they have finalised
         with full sentence context, so they never change and punctuation
         lands at real sentence ends
       - already-typed words seed the next transcription as context, so the
         model continues your sentence instead of restarting it
  4. stays open (output muted) until the dictation key is pressed again,
     or the 10-minute safety cap is reached
  5. on stop, commit anything pending, then exit

Test hook: set DICTATE_WAV=/path/to.wav to read that file instead of the mic
(same chunk loop, same VAD/flush/stop logic).
"""
import ctypes
import numpy as np
import os
import re
import signal
import shutil
import site
import subprocess
import sys
import threading
import time
from pathlib import Path

# ---- configuration ----------------------------------------------------------
# All tunables live in config.py (defaults in config/default.toml), overridable
# by the user config file or DICTATE_* env vars. Loaded once at import so the
# rest of this file can keep reading plain module globals.
try:
    from . import config as _cfgmod
except ImportError:      # also allow running the file directly
    import config as _cfgmod

CFG = _cfgmod.load_config()

# What build_model() actually resolved (model, device) — written to live.json
# so `tays status --json` (GUI, applet) can report the EXACT runtime device.
RUNTIME: dict = {}


def _live_state_file() -> Path:
    xdg = os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state"))
    return Path(xdg) / "type-as-you-speak" / "live.json"


def _write_live_state() -> None:
    import json
    try:
        p = _live_state_file()
        p.parent.mkdir(parents=True, exist_ok=True)
        st = {"pid": os.getpid()}
        st.update(RUNTIME)
        p.write_text(json.dumps(st))
    except Exception:
        pass


def _clear_live_state() -> None:
    try:
        _live_state_file().unlink()
    except OSError:
        pass


def _detect_gpu_name() -> str | None:
    """Human-readable GPU name, if a driver exposes one (for logging)."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5).stdout.strip().splitlines()
        if out and out[0].strip():
            return out[0].strip()
    except Exception:
        pass
    return None


def _log(msg):
    print(f"[live] {msg}", file=sys.stderr, flush=True)


def load_hotwords(inline, path):
    """Combine the inline `hotwords` string with an optional hotwords file
    (one word or phrase per line; '#' comments and blank lines ignored).
    Entries are deduped case-insensitively (first occurrence wins) and
    returned as one comma-separated string. A missing/unreadable file warns
    and falls back to the inline list — never crashes a session."""
    entries = [e.strip() for e in re.split(r"[,;]", inline or "") if e.strip()]
    if path:
        p = os.path.expanduser(str(path))
        try:
            with open(p, encoding="utf-8") as f:
                for line in f:
                    e = line.split("#", 1)[0].strip()
                    if e:
                        entries.append(e)
        except OSError as e:
            _log(f"hotwords file {p!r} unreadable ({e}) — inline list only")
    seen, out = set(), []
    for e in entries:
        k = e.casefold()
        if k not in seen:
            seen.add(k)
            out.append(e)
    return ", ".join(out)

MODEL_NAME = CFG["model_name"]                  # any faster-whisper model
LANG = CFG["language"]
TYPE_MS = int(CFG["type_ms"])                   # ydotool ms per key
CHUNK_S = float(CFG["chunk_s"])                 # audio chunk size (loop pacing)
VAD_THRESHOLD = float(CFG["vad_threshold"])     # mean Silero prob that is speech
TRANSCRIBE_EVERY_S = float(CFG["transcribe_every_s"])  # re-transcribe cadence
COMMIT_LAG_S = float(CFG["commit_lag_s"])       # words finalise with sentence context
SILENCE_COMMIT_S = float(CFG["silence_commit_s"])
MIN_PENDING_S = float(CFG["min_pending_s"])
MAX_PENDING_S = float(CFG["max_pending_s"])
PROMPT_TAIL_WORDS = int(CFG["prompt_tail_words"])
MAX_SESSION_S = float(CFG["max_session_s"])     # safety cap only (10 min)
PREBUF_CAP_S = float(CFG["prebuf_cap_s"])
NO_REPEAT_NGRAM_SIZE = int(CFG["no_repeat_ngram_size"])
CONDITION_ON_PREVIOUS_TEXT = bool(CFG["condition_on_previous_text"])
HOTWORDS = load_hotwords(str(CFG["hotwords"]).strip(),
                         str(CFG.get("hotwords_file", "")).strip())
HOTWORD_ENTRIES = [e.strip() for e in HOTWORDS.split(",") if e.strip()]


def hotword_leak(text, min_distinct=3):
    """True if `text` contains at least `min_distinct` distinct hotwords —
    the signature of whisper re-emitting the hotword *prompt* as
    "transcription" (observed in the log: 'for the Linux, glue, productised,
    per-disk, for all the' stamped over 0.06 s of silence). Real dictation
    naming three-plus of your own hotwords in one breath is vanishingly
    unlikely, so a segment like that is dropped as a whole."""
    if len(HOTWORD_ENTRIES) < min_distinct:
        return False
    t = text.casefold()
    return sum(1 for h in HOTWORD_ENTRIES if h.casefold() in t) >= min_distinct

SR = 16000                                       # Whisper requires 16 kHz mono
CHUNK_SAMPLES = SR * CHUNK_S
CHUNK_BYTES = int(CHUNK_SAMPLES) * 4

# Whisper "end-of-speech" hallucinations: on trailing silence it emits a stock
# closing line (or re-emits your last phrase). These trailing phrases are
# stripped before typing (see clean_hallucinations). Edit in your config file.
WHISPER_HALLUCINATION_TAILS = list(CFG["hallucination_tails"])
# -----------------------------------------------------------------------------


def norm(s):
    """Collapse any whitespace runs to single spaces."""
    return " ".join(s.split())


def _wordkey(x):
    """Normalise a word for comparison: lowercase, keep [a-z0-9] and apostrophes."""
    return re.sub(r"[^a-z0-9']", "", x.lower())


def clean_hallucinations(text):
    """Strip Whisper hallucinations before typing:

    (0) repetition loops — under GPU contention the decode can lock onto a
        single token and emit it over and over ("Cl- Cl- Cl- Cl-", "you you
        you"). A run of the same word 2+ times (anywhere in the text) is
        dropped entirely: real dictation speech almost never says one word
        back-to-back twice.
    (1) stock "closing" phrases — Whisper inserts these *anywhere* it wants (it
        splices them mid-stream, not only at the end), so every contiguous
        occurrence is removed. Longest-first, so "i'll see you in the next
        video" wins over its suffix "see you in the next video" (no dangling
        word left behind).
    (2) a trailing exact "X X" repeat (the last K words duplicate the K before).

    Called at the single commit point, so it catches both the main transcribe
    pass and the tail-recovery re-transcribe.
    """
    words = norm(text).split()
    if not words:
        return ""

    # (0) drop repetition-loop runs: "cl cl cl" -> "", "option a still cl cl"
    #     -> "option a still". Whole run (incl. first copy) is dropped.
    kept, prev = [], None
    for w in words:
        k = _wordkey(w)
        if not k:                       # punctuation-only token: keep, no loop
            kept.append(w)
            continue
        if k == prev:
            if kept and _wordkey(kept[-1]) == k:
                del kept[-1]
            continue
        kept.append(w)
        prev = k
    words = kept

    # (1) remove stock hallucination phrases wherever they occur.
    tails = [[_wordkey(w) for w in p.split()] for p in WHISPER_HALLUCINATION_TAILS]
    tails.sort(key=len, reverse=True)
    changed = True
    while changed and words:
        changed = False
        keys = [_wordkey(w) for w in words]
        for t in tails:
            if not t or len(t) > len(keys):
                continue
            for i in range(len(keys) - len(t) + 1):
                if keys[i:i + len(t)] == t:
                    words = words[:i] + words[i + len(t):]
                    changed = True
                    break
            if changed:
                break

    # (2) dedup a trailing exact repeat: "X X" -> "X" (K words, K >= 2)
    n = len(words)
    if n:
        keys = [_wordkey(w) for w in words]
        for k in range(n // 2, 1, -1):
            if keys[-k:] == keys[-2 * k:-k]:
                words = words[:-k]
                break
    if not any(_wordkey(w) for w in words):
        return ""      # nothing but punctuation survived the stripping
    return " ".join(words)


def has_repetition_loop(words, min_run=3):
    """True if the same word occurs back-to-back `min_run` or more times —
    the signature of a degenerate beam-search decode ("Cl- Cl- Cl-").

    Two back-to-back is NOT enough to trip the CPU fallback: now that
    no_repeat_ngram_size blocks most loops at the source, a double occurrence
    is more often a Whisper segmentation stutter on a legit word (or a
    speaker stutter) than degeneration."""
    prev, run = None, 0
    for w in words:
        k = _wordkey(w)
        if not k:
            prev, run = None, 0
            continue
        run = run + 1 if k == prev else 1
        prev = k
        if run >= min_run:
            return True
    return False


def trim_fast_tail(words, min_span_s=0.10):
    """Drop a trailing run of words stamped faster than speech can go.

    Over trailing silence Whisper hallucinates a short closing word/phrase and
    stamps it implausibly fast — observed "All right." on 0.14 s (0.07 s/word)
    and a lone "you" on 0.08 s. Real speech can't sustain < ~0.1 s per word
    (even fast), so a trailing run that fast is a hallucination. Position-
    scoped to the tail: real words mid-sentence are never touched.
    """
    i = len(words)
    while i > 0 and (words[i - 1].end - words[i - 1].start) < min_span_s:
        i -= 1
    return words[:i]


def span_has_speech(vad, audio, start_s, end_s, min_prob=0.5):
    """VAD probability over one word's span of `audio` (word timestamps are
    relative to `audio`). Whisper can stamp a hallucinated word with plausible
    speed ("ships." on 0.18 s); if there is no speech energy in its span, it
    was invented over silence. A span too short to judge is kept."""
    s = max(0, int(start_s * SR))
    e = min(len(audio), int(end_s * SR))
    span = np.ascontiguousarray(audio[s:e], dtype=np.float32)
    if span.size < 512:          # too short to judge — keep the word
        return True
    rem = span.size % 512
    if rem:
        span = np.concatenate([span, np.zeros(512 - rem, dtype=np.float32)])
    return float(np.mean(vad(span))) >= min_prob


def guard_trailing(words, audio, vad):
    """Drop a trailing hallucination run from a decoded word list (timestamps
    relative to `audio`), shared by the main commit path and the tail
    recovery path:
    1) trim_fast_tail — stamped faster than speech can go;
    2) up to two words whose audio span has no VAD speech energy
       (invented over silence, e.g. "Hi." after a long pause).
    Returns the surviving words — possibly empty for a hallucination-only
    decode (the caller decides what to do with an empty result)."""
    words = trim_fast_tail(words)
    if len(words) > 1:
        dropped = 0
        while dropped < 2:
            w = words[-1]
            if span_has_speech(vad, audio, w.start, w.end):
                break
            words = words[:-1]
            dropped += 1
    return words


def speech_fraction(vad, audio):
    """Fraction of `audio` the VAD scores as speech (block prob >= 0.5).
    More robust than a mean when a region mixes real speech with silence:
    a silent tail scores ~0, a tail containing any real speech scores well
    above the recovery gate."""
    arr = np.ascontiguousarray(audio, dtype=np.float32)
    if arr.size < 512:
        return 0.0
    rem = arr.size % 512
    if rem:
        arr = np.concatenate([arr, np.zeros(512 - rem, dtype=np.float32)])
    probs = np.asarray(vad(arr), dtype=np.float64)
    return float(np.count_nonzero(probs >= 0.5) / probs.size)


# A tail is only worth re-decoding if at least this much of it is speech —
# re-decoding a silent tail is exactly how whisper hallucinates a closing
# word over the pause ("Hi." after "So be it." — observed in the log).
TAIL_SPEECH_FRACTION = 0.10

_stop = {"flag": False}


def _on_signal(signum, frame):
    _stop["flag"] = True


def _preload_nvidia():
    try:
        sp = site.getsitepackages()[0]
    except Exception:
        return
    for sub, name in (
        ("nvidia/cublas/lib", "libcublas.so.12"),
        ("nvidia/cuda_runtime/lib", "libcudart.so.12"),
        ("nvidia/cuda_nvrtc/lib", "libnvrtc.so.12"),
    ):
        p = os.path.join(sp, sub, name)
        if os.path.exists(p):
            try:
                ctypes.CDLL(p, mode=ctypes.RTLD_GLOBAL)
            except OSError:
                pass


def build_model():
    """Pick a model + device from config.

    device (config key `device` / DICTATE_DEVICE):
      auto  (default) — GPU if it can hold a model, else CPU.
                        (Ollama may be reserving most of the VRAM for its KV
                        cache, so a big model can fail and a smaller one fit.)
      cuda             — force the NVIDIA GPU; if nothing loads, fail clearly
                         rather than silently falling back to slow CPU.
      rocm             — force an AMD GPU. CTranslate2's ROCm build exposes
                         the GPU through the same "cuda" device string (HIP),
                         so this path is shared — the difference is the build:
                         standard pip wheels are CUDA/CPU only.
      cpu              — force CPU (int8); never touch the GPU.

    `model_name` is the primary choice. On the GPU we try it first, then fall
    back down the standard ladder if it doesn't fit in the current VRAM
    headroom. cpu_threads (config `cpu_threads` / DICTATE_CPU_THREADS) caps
    CTranslate2's CPU-side bookkeeping on every transcription round, which
    narrows the per-round CPU spike; the GPU does the actual ASR, so capping
    barely costs speed. On a CPU model the threads *are* the compute, so we
    leave that at the library default."""
    from faster_whisper import WhisperModel
    device = CFG["device"]
    name = CFG["model_name"]
    cpu_threads = int(CFG["cpu_threads"])

    if device == "cpu":
        m = WhisperModel(name, device="cpu", compute_type="int8")
        _log(f"model: {name} on cpu (int8) [device=cpu]")
        RUNTIME.update(model=name, device="cpu")
        return m

    # device in (auto, cuda, rocm): try the GPU, biggest model that fits first.
    # (A CTranslate2 ROCm build presents its AMD GPU as a "cuda" device via
    # HIP, so all GPU paths use the same device string.)
    gpu_label = device if device in ("cuda", "rocm") else "cuda"
    actual_gpu = _detect_gpu_name()
    ladder = [name] + [n for n in ("medium.en", "small.en", "base.en") if n != name]
    for cand in ladder:
        try:
            m = WhisperModel(cand, device="cuda", compute_type="float16",
                             cpu_threads=cpu_threads)
            _log(f"model: {cand} on {gpu_label} (cpu_threads={cpu_threads})"
                 + (f" [actual GPU: {actual_gpu}]" if actual_gpu else ""))
            RUNTIME.update(model=cand, device=gpu_label)
            return m
        except Exception as e:
            _log(f"{gpu_label} {cand} unavailable ({e!r})")

    # No GPU model loaded.
    if device == "cuda":
        raise RuntimeError(
            "device=cuda was requested but no CUDA model could load. Check the "
            "NVIDIA driver, and that faster-whisper is built with CUDA support "
            "(on a fresh install: `pip install -U faster-whisper`).")
    if device == "rocm":
        raise RuntimeError(
            "device=rocm was requested but no GPU model could load. AMD ROCm "
            "support needs CTranslate2's ROCm wheel — the standard pip wheel "
            "is CUDA/CPU only. See https://github.com/OpenNMT/CTranslate2/releases "
            "for the ROCm build (then reinstall faster-whisper against it).")
    m = WhisperModel(name, device="cpu", compute_type="int8")
    _log(f"model: {name} on cpu (int8)")
    RUNTIME.update(model=name, device="cpu")
    return m


def get_vad():
    from faster_whisper.vad import get_vad_model
    return get_vad_model()


class AudioReader:
    """Reads 16 kHz mono float32 audio in CHUNK_BYTES units, from the mic
    (ffmpeg) or from a wav file (DICTATE_WAV). A drainer thread keeps
    collecting while the model loads, so no early speech is lost."""

    def __init__(self):
        import numpy as np
        self._np = np
        self._buf = bytearray()
        self._lock = threading.Lock()
        self._closed = False
        self._src = os.environ.get("DICTATE_WAV", "")
        input_dev = os.environ.get("DICTATE_INPUT", "default")
        if self._src:
            self._proc = subprocess.Popen(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", self._src,
                 "-ar", str(SR), "-ac", "1", "-f", "f32le", "-"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            self._fh = self._proc.stdout
        else:
            self._proc = subprocess.Popen(
                ["ffmpeg", "-hide_banner", "-loglevel", "error",
                 "-f", "pulse", "-i", input_dev,
                 "-ar", str(SR), "-ac", "1", "-f", "f32le", "-"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            # IMPORTANT: _drain() reads the raw fd (os.read), bypassing the
            # BufferedReader — that blocks read(n) until n full bytes arrive,
            # delivering audio in 1 s quanta and starving the session.
            self._fh = self._proc.stdout
        self._thread = threading.Thread(target=self._drain, daemon=True)
        self._thread.start()

    def _drain(self):
        cap = int(PREBUF_CAP_S * SR * 4)
        self._drain_exit = "running"
        fd = self._fh.fileno()
        while not self._closed:
            try:
                # os.read() on a pipe returns as soon as >=1 byte is
                # available. BufferedReader.read(n) would block until n full
                # bytes arrive, delivering audio in 1 s quanta.
                data = os.read(fd, 65536)
            except (OSError, ValueError) as e:
                self._drain_exit = f"read error: {e!r}"
                break
            if not data:
                self._drain_exit = "EOF"
                break
            with self._lock:
                self._buf.extend(data)
                if len(self._buf) > cap:
                    del self._buf[: len(self._buf) - cap]
        if self._proc is not None:
            rc = self._proc.poll()
            if rc is not None:
                self._drain_exit += f" ffmpeg_exit={rc}"
        self._eof = True

    def read_chunk(self, timeout_s=1.0):
        """Return CHUNK_BYTES of audio (as numpy float32) or None at end."""
        deadline = time.time() + timeout_s
        while True:
            with self._lock:
                if len(self._buf) >= CHUNK_BYTES:
                    data = bytes(self._buf[:CHUNK_BYTES])
                    del self._buf[:CHUNK_BYTES]
                else:
                    data = None
            if data is not None:
                return self._np.frombuffer(data, dtype=self._np.float32)
            # none in buffer yet
            with self._lock:
                empty = len(self._buf) == 0
            if empty and self._thread is not None and not self._thread.is_alive():
                return None  # source ended
            if time.time() > deadline:
                return None  # no audio arriving (mic dead?)
            time.sleep(0.01)

    def close(self):
        self._closed = True
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=2)
            except Exception:
                self._proc.kill()


def _clipboard_args():
    """Command to place text on the system clipboard, chosen per desktop.

    Wayland -> `wl-copy` (wl-clipboard); X11 -> `xclip -selection clipboard`.
    If neither display env var is set (e.g. launched by a trimmed agent), pick
    whichever clipboard tool is actually installed."""
    if os.environ.get("WAYLAND_DISPLAY"):
        return ["wl-copy"]
    if os.environ.get("DISPLAY"):
        return ["xclip", "-selection", "clipboard"]
    if shutil.which("xclip"):
        return ["xclip", "-selection", "clipboard"]
    return ["wl-copy"]


def make_type():
    runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    os.environ.setdefault("YDOTOOL_SOCKET", f"{runtime}/.ydotool_socket")
    # DICTATE_DRY_RUN=1: run the whole pipeline (VAD, transcribe, commit,
    # hallucination filter) but log what *would* be typed instead of injecting
    # keystrokes — handy for testing without a display/mic or touching windows.
    dry = os.environ.get("DICTATE_DRY_RUN") == "1"

    def _run(args):
        if dry:
            _log(f"dry-run type: {args[-1]!r}")
            return True
        try:
            subprocess.run(args, timeout=30, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=True)
            return True
        except Exception as e:
            _log(f"ydotool failed: {e!r}")
            return False

    def type_text(text):
        # Collapse whitespace runs to single spaces — but PRESERVE a leading
        # space: commit() prepends one to separate this chunk from whatever
        # was already typed. (" ".join(text.split()) would strip it and glue
        # the chunks together — the 2026-11-22 "missing spaces" bug.)
        text = re.sub(r"\s+", " ", text).rstrip()
        core = text.lstrip()
        if not core or re.fullmatch(r"\(.*\)", core):
            return False
        if _run(["ydotool", "type", "--key-delay", str(TYPE_MS),
                 "--key-hold", str(TYPE_MS), text]):
            return True
        try:
            subprocess.run(_clipboard_args(), input=text.encode(), timeout=10, check=True)
            _log("copied to clipboard instead")
            return True
        except Exception as e2:
            _log(f"clipboard fallback failed: {e2!r}")
            return False

    def type_space():
        _run(["ydotool", "type", "--key-delay", str(TYPE_MS),
              "--key-hold", str(TYPE_MS), " "])

    return type_text, type_space


def unmute_out():
    """Session always leaves the output unmuted (bash also unmuting on manual
    stop — idempotent)."""
    try:
        subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=5)
    except Exception:
        pass


def notify_done():
    try:
        subprocess.run(["notify-send", "-a", "type-as-you-speak",
                        "-i", "audio-microphone", "Dictation",
                        "Finished — output un-muted."],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=5)
    except Exception:
        pass


def main():
    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    t0 = time.time()
    reader = AudioReader()
    _log(f"audio source: {os.environ.get('DICTATE_WAV', 'mic')}")
    exit_code = 3
    try:
        exit_code = run_session(reader, t0)
    finally:
        reader.close()
        unmute_out()
        _clear_live_state()
    return exit_code


def run_session(reader, t0):

    _preload_nvidia()
    model = build_model()
    _write_live_state()   # status/GUI/applet can now report the exact device
    vad = get_vad()

    def warmup():
        try:
            import numpy as np
            model.transcribe(np.zeros(SR * 2, dtype=np.float32), language=LANG)
        except Exception:
            pass

    warmup()
    type_text, type_space = make_type()
    _log(f"ready in {time.time() - t0:.2f}s — speak now")

    # ---- streaming state ----------------------------------------------------
    # pending: audio heard but not yet committed; re-transcribed each round.
    # committed: everything typed so far; seeds the next transcription as
    # context so Whisper continues your sentence instead of restarting it.
    pending = []
    pending_dur = 0.0
    committed = ""
    last_speech = None
    last_round_at = 0.0
    session_start = time.time()
    typed_any = False
    _cpu_fallback = [None]

    def engage_cpu_fallback(reason):
        """Build the CPU fallback model once; every round after this uses it.
        Triggers: a GPU transcribe exception (OOM), or the GPU decode produced
        a repetition loop (it degenerates under VRAM/compute contention — e.g.
        Ollama serving on the same GPU). small.en int8: good quality, and the
        CPU isn't the scarce resource here."""
        if _cpu_fallback[0] is None:
            from faster_whisper import WhisperModel
            _cpu_fallback[0] = WhisperModel("small.en", device="cpu",
                                            compute_type="int8")
            _log(f"{reason} — cpu small.en for the rest of this session")

    def transcribe(audio, prompt):
        """GPU model first; if it OOMs mid-session (or was engaged as the
        fallback after unstable decodes), use the CPU model instead. Word
        timestamps let us commit at word granularity (only words older than
        the commit lag are finalised). no_repeat_ngram_size +
        condition_on_previous_text keep the decode from looping/re-emitting
        under GPU contention (config `no_repeat_ngram_size`,
        `condition_on_previous_text`)."""
        kwargs = dict(language=LANG, vad_filter=False, word_timestamps=True,
                      no_repeat_ngram_size=NO_REPEAT_NGRAM_SIZE,
                      condition_on_previous_text=CONDITION_ON_PREVIOUS_TEXT)
        if HOTWORDS:
            kwargs["hotwords"] = HOTWORDS
        if prompt:
            kwargs["initial_prompt"] = prompt
        if _cpu_fallback[0] is not None:
            return _cpu_fallback[0].transcribe(audio, **kwargs)
        try:
            return model.transcribe(audio, **kwargs)
        except Exception:
            engage_cpu_fallback("GPU transcribe failed")
            return _cpu_fallback[0].transcribe(audio, **kwargs)

    def speech_prob(chunk):
        arr = chunk
        rem = len(arr) % 512
        if rem:
            arr = np.concatenate([arr, np.zeros(512 - rem, dtype=np.float32)])
        probs = vad(arr)
        return float(np.mean(probs))

    def strip_echo(prompt_text, text):
        """Drop leading words of `text` that merely repeat the prompt tail.
        Whisper primed with context either re-emits the prompt or skips over
        it — either way the repeated words are already typed, so strip them
        (largest overlap wins; a full re-echo strips to empty)."""
        words = text.split()
        pw = [_wordkey(x) for x in prompt_text.split()]
        fw = [_wordkey(x) for x in words]
        if not pw or not fw:
            return text
        for k in range(min(len(pw), len(fw)), 0, -1):
            if fw[:k] == pw[-k:]:
                return " ".join(words[k:])
        return text

    def silence_bounds(audio, min_speech_s=0.5):
        """Sample range of the speech region (with small margins), or None if
        there is none (whisper hallucinates on pure silence)."""
        rem = len(audio) % 512
        arr = audio if not rem else np.concatenate(
            [audio, np.zeros(512 - rem, dtype=np.float32)])
        speech = np.where(np.asarray(vad(arr)) >= 0.5)[0]
        if len(speech) == 0:
            return None
        start = max(0, int(speech[0]) * 512 - 256)
        end = min(len(audio), int(speech[-1]) * 512 + 768)
        if end - start < SR * min_speech_s:
            return None
        return start, end

    def commit(text):
        """Type brand-new words after everything committed so far."""
        nonlocal committed, typed_any
        text = norm(text)
        if not text:
            return False
        lead = " " if committed else ""
        if type_text(lead + text):
            committed = norm(committed + lead + text)
            typed_any = True
            _log(f"typed (+{len(text)} chars): {text[:60]!r}")
            return True
        return False

    def do_round(commit_lag, now):
        """Transcribe the pending audio; commit only the part older than
        `commit_lag`. The tail stays pending and is re-transcribed next round
        with more context, so words finalise with the sentence, not with our
        cut — that is what keeps punctuation and word choice accurate."""
        nonlocal pending, pending_dur, last_round_at
        if not pending:
            return
        audio = np.concatenate(pending)
        b = silence_bounds(audio)
        if b is None:
            pending, pending_dur = [], 0.0
            return
        start, end = b
        segment = audio[start:end]
        dur = (end - start) / SR
        if dur < MIN_PENDING_S:
            return
        prompt = None
        if committed:
            tail = committed.split()[-PROMPT_TAIL_WORDS:]
            if tail:
                # Always prime with the committed tail (even 1-2 words):
                # it both guides the decode and anchors the echo-stripping,
                # so boundary words can't be typed twice.
                prompt = " ".join(tail)
        _log(f"round: lag={commit_lag:.1f}s region={start/SR:.2f}-{end/SR:.2f}s "
             f"dur={dur:.2f}s prompt={bool(prompt)}")
        try:
            segs, _ = transcribe(segment, prompt)
            segs = list(segs)
        except Exception as e:
            _log(f"transcribe error: {e!r}")
            last_round_at = now
            return
        # Hotword prompt leak: whisper can re-emit the hotword prompt itself
        # as "transcription" (observed: 'for the Linux, glue, productised,
        # per-disk, for all the' over 0.06 s of silence). A segment naming
        # 3+ distinct hotwords is a leak — drop just that segment; the real
        # words around it survive.
        leaked = [s for s in segs if hotword_leak(s.text)]
        if leaked:
            for s in leaked:
                _log(f"hotword leak dropped: {s.text.strip()[:60]!r}")
            segs = [s for s in segs if not hotword_leak(s.text)]
        last_round_at = now
        for s in segs:
            _log(f"  seg [{s.start:5.2f} -> {s.end:5.2f}] {s.text.strip()[:60]!r}")
        words = [w for s in segs for w in (s.words or [])]
        if not words:
            _log("no word timestamps — skipping round")
            return
        # Word-level stability: a word is finalised once it ended more than
        # `commit_lag` ago — exactly the Mac behaviour (words land a beat
        # after you say them, and the live tail re-transcribes next round
        # with more context). This also works for one long unbroken phrase,
        # where segment-end filtering could never finalise anything.
        limit = dur - commit_lag
        stable_words = [w for w in words if w.end <= limit]
        if not stable_words:
            if commit_lag == 0.0:
                stable_words = words      # final commit: take everything
            else:
                return                    # nothing finalised yet — re-try next round
        # Drop trailing hallucinations: stamped faster than speech can go
        # ("All right." on 0.14 s) or with no speech energy in their span
        # ("ships." on 0.18 s over silence). Same guard the tail recovery
        # path below uses.
        stable_words = guard_trailing(stable_words, segment, vad)
        if not stable_words:
            return                        # hallucination-only round — re-try next
        parts = []
        for w in stable_words:
            p = w.word.strip()
            if not p:
                continue
            if p.startswith("-") and parts:
                parts[-1] += p          # "open" + "-source" -> "open-source"
            else:
                parts.append(p)
        # Degenerate-decode tripwire: the GPU is looping the same word (this
        # happens under VRAM/compute contention). The loop itself is stripped
        # by clean_hallucinations below; this switches the *session* to the CPU
        # model so the next rounds decode cleanly.
        if has_repetition_loop(parts):
            engage_cpu_fallback("GPU decode produced a repetition loop")
        stable_text = norm(" ".join(parts))
        covered = stable_words[-1].end
        if prompt:
            stable_text = norm(strip_echo(prompt, stable_text))

        # --- tail recovery (final commits only) ------------------------------
        # GPU decodes can silently stop before the audio does (observed with
        # medium.en under VRAM pressure — words vanish, or the whole segment
        # comes back empty). Re-transcribe the untranscribed tail primed with
        # what we already have — but ONLY if the VAD shows speech in it:
        # re-decoding a silent tail is exactly how whisper hallucinates a
        # closing word over your pause ("Hi." after "So be it." — observed
        # in the log). A silent tail is VAD-certified, so it is consumed.
        if commit_lag == 0.0 and dur - covered > 0.7:
            tail = segment[max(0, int(covered * SR)):]
            if speech_fraction(vad, tail) >= TAIL_SPEECH_FRACTION:
                base = norm(committed + " " + stable_text)
                tail_prompt = " ".join(base.split()[-PROMPT_TAIL_WORDS:])
                _log(f"tail recovery: {dur - covered:.2f}s untranscribed")
                try:
                    segs2 = list(transcribe(tail, tail_prompt)[0])
                except Exception as e:
                    segs2 = []
                    _log(f"tail transcribe error: {e!r}")
                tw = guard_trailing([w for s in segs2 for w in (s.words or [])],
                                   tail, vad)
                t2 = norm(strip_echo(tail_prompt,
                                     " ".join(w.word.strip() for w in tw)))
                if t2:
                    stable_text = norm((stable_text + " " + t2).strip())
                    covered = dur
                    _log(f"tail recovered: {t2[:60]!r}")
            else:
                skipped = dur - covered
                covered = dur
                _log(f"tail silent ({skipped:.2f}s, VAD) — not re-decoded")

        # Strip Whisper end-of-speech hallucinations before typing (a stock
        # closing line and/or a trailing "X X" repeat). If the region turned
        # out to be hallucination-only (whisper filling silence), drop the
        # covered audio so we don't re-transcribe the same silence and
        # re-hallucinate on every round.
        stable_text = clean_hallucinations(stable_text)
        if not stable_text:
            drop = start + int(min(dur, covered) * SR) + 80
            keep = audio[drop:] if drop < len(audio) else np.zeros(0, dtype=np.float32)
            if keep.size >= 1600:
                pending, pending_dur = [keep], keep.size / SR
            else:
                pending, pending_dur = [], 0.0
            _log("hallucination-only region dropped (nothing typed)")
            return
        if committed:
            # Continuation fixes: whisper treats every transcription as the
            # start of a new sentence, so it capitalises the first word and
            # sometimes prepends a stray period. Both are wrong mid-sentence.
            if stable_text[:1] in ".!?":
                stable_text = norm(stable_text.lstrip(".!?"))
                if not stable_text:
                    return
            last_char = committed.rstrip()[-1]
            if last_char not in ".!?'\"" and stable_text[:1].isupper():
                stable_text = stable_text[0].lower() + stable_text[1:]
        if not commit(stable_text):
            return
        # Drop the covered audio; keep the rest (a little overlap so the
        # boundary word can't be lost) for the next round.
        drop = start + int(min(dur, covered) * SR) + 80
        keep = audio[drop:] if drop < len(audio) else np.zeros(0, dtype=np.float32)
        if keep.size >= 1600:
            pending, pending_dur = [keep], keep.size / SR
        else:
            pending, pending_dur = [], 0.0

    while not _stop["flag"]:
        elapsed = time.time() - session_start
        if elapsed > MAX_SESSION_S:
            _log("max session time reached")
            break
        chunk = reader.read_chunk(timeout_s=1.0)
        if chunk is None:
            _log(f"audio source ended: drain={getattr(reader, '_drain_exit', '?')}, "
                 f"buf={len(reader._buf)}b, thread_alive={reader._thread.is_alive()}")
            break
        now = time.time()
        # Test mode: DICTATE_WAV + DICTATE_REALTIME=1 paces file playback
        # like a live mic, so the round/commit logic behaves realistically.
        if reader._src and os.environ.get("DICTATE_REALTIME"):
            time.sleep(CHUNK_S)

        if speech_prob(chunk) >= VAD_THRESHOLD:
            last_speech = now

        if last_speech is None:
            # No word yet — discard the pre-roll so we don't buffer minutes of
            # silence; the session simply keeps listening (no auto-end).
            pending, pending_dur = [], 0.0
            continue

        pending.append(chunk)
        pending_dur += CHUNK_S

        # No auto-stop on silence: stay open (output muted) until the
        # dictation key is pressed again (SIGTERM) or MAX_SESSION_S is hit.
        silent_for = now - last_speech
        # One transcription round per TRANSCRIBE_EVERY_S wall time (GPU is
        # busy; this also avoids hammering when a round couldn't commit).
        if (now - last_round_at) >= TRANSCRIBE_EVERY_S and pending_dur >= 0.2:
            if silent_for >= SILENCE_COMMIT_S:
                # You paused: commit the whole tail — end-of-sentence
                # punctuation lands here, with full context.
                do_round(0.0, now)
            elif pending_dur > MAX_PENDING_S:
                # Safety: something isn't finalising; make progress.
                do_round(0.3, now)
            elif silent_for < 1.0 and pending_dur >= MIN_PENDING_S:
                do_round(COMMIT_LAG_S, now)

    # final commit of anything pending
    do_round(0.0, time.time())
    if not _stop["flag"]:
        notify_done()
    reader.close()
    _log(f"done in {time.time() - session_start:.1f}s typed_any={typed_any}")
    return 0 if typed_any else 3  # 3 = session ended, nothing typed


if __name__ == "__main__":
    sys.exit(main())

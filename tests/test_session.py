from types import SimpleNamespace
import json
import sys

import numpy as np
import pytest

from type_as_you_speak import engine


def segment(text="Hello world.", end=0.8):
    parts = text.split()
    width = end / len(parts)
    return SimpleNamespace(
        text=text,
        start=0.0,
        end=end,
        words=[
            SimpleNamespace(word=w, start=i * width, end=(i + 1) * width)
            for i, w in enumerate(parts)
        ],
    )


@pytest.fixture
def session(monkeypatch, tmp_path):
    clock = SimpleNamespace(now=1000.0)
    monkeypatch.setattr(engine, "time", SimpleNamespace(time=lambda: clock.now))
    monkeypatch.setattr(engine, "CHUNK_S", 1.0)
    monkeypatch.setattr(engine, "TRANSCRIBE_EVERY_S", 100000.0)
    monkeypatch.setattr(engine, "MIN_PENDING_S", 0.7)
    monkeypatch.setattr(engine, "MAX_PENDING_S", 8.0)
    monkeypatch.setattr(engine, "MAX_SESSION_S", 600.0)
    monkeypatch.setattr(engine, "VAD_THRESHOLD", 0.5)
    monkeypatch.setattr(engine, "LANG", "en")
    monkeypatch.setattr(engine, "HOTWORDS", "")
    monkeypatch.setattr(engine, "HOTWORD_ENTRIES", [])
    monkeypatch.setattr(engine, "_stop", {"flag": False})
    monkeypatch.setattr(engine, "RUNTIME", {"model": "base.en", "device": "cuda"})
    monkeypatch.setattr(engine, "_preload_nvidia", lambda: None)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setattr(engine, "WHISPER_HALLUCINATION_TAILS", ["thanks for watching"])
    notified, typed, decoded = [], [], []
    monkeypatch.setattr(engine, "notify_done", lambda: notified.append(True))
    monkeypatch.setattr(
        engine, "make_type", lambda: (lambda t: typed.append(t) or True, lambda: None)
    )

    def vad(audio):
        blocks = np.asarray(audio).reshape(-1, 512)
        return (np.max(np.abs(blocks), axis=1) > 0).astype(np.float32)

    monkeypatch.setattr(engine, "get_vad", lambda: vad)

    def run(chunks=None, decode=None, stop=False):
        chunks = iter(
            chunks if chunks is not None else [np.ones(16000, dtype=np.float32)]
        )

        def read_chunk(**kwargs):
            clock.now += 1
            if stop:
                engine._on_signal(None, None)
            return next(chunks, None)

        reader = SimpleNamespace(
            read_chunk=read_chunk,
            close=lambda: None,
            _src="",
            _buf=b"",
            _thread=SimpleNamespace(is_alive=lambda: False),
        )

        def transcribe(audio, **kwargs):
            if not kwargs.get("word_timestamps"):
                return iter(()), None
            decoded.append(kwargs)
            return (decode(audio, kwargs) if decode else iter([segment()])), None

        monkeypatch.setattr(
            engine, "build_model", lambda: SimpleNamespace(transcribe=transcribe)
        )
        return engine.run_session(reader, clock.now)

    return SimpleNamespace(run=run, typed=typed, notified=notified, decoded=decoded)


def test_eof_flushes_pending_words(session):
    assert session.run() == 0
    assert session.typed == ["Hello world."]


def test_silence_never_decodes_or_types(session):
    assert session.run(chunks=[np.zeros(16000, dtype=np.float32)]) == 3
    assert session.typed == []
    assert session.decoded == []


def test_stop_signal_flushes_pending_words_without_completion_notification(session):
    assert session.run(stop=True) == 0
    assert session.typed == ["Hello world."]
    assert session.notified == []


def test_failed_input_does_not_report_a_successful_session(session, monkeypatch):
    monkeypatch.setattr(engine, "make_type", lambda: (lambda _: False, lambda: None))
    assert session.run() == 3
    assert session.typed == []


def test_hallucination_only_decode_is_not_typed(session):
    assert session.run(decode=lambda *_: iter([segment("Thanks for watching!")])) == 3
    assert session.typed == []


def test_missing_word_timestamps_do_not_type_unverified_segment_text(session):
    item = segment()
    item.words = None
    assert session.run(decode=lambda *_: iter([item])) == 3
    assert session.typed == []


def test_streaming_commits_preserve_spaces_and_strip_prompt_echo(session, monkeypatch):
    monkeypatch.setattr(engine, "TRANSCRIBE_EVERY_S", 0.5)
    monkeypatch.setattr(engine, "COMMIT_LAG_S", 0.1)
    results = iter([segment("Hello"), segment("Hello world.", end=0.9)])
    assert (
        session.run(
            chunks=[np.ones(16000, dtype=np.float32)] * 2,
            decode=lambda *_: iter([next(results)]),
        )
        == 0
    )
    assert session.typed == ["Hello", " world."]
    assert session.decoded[1]["initial_prompt"] == "Hello"


@pytest.mark.parametrize("lazy", [False, True], ids=["call-error", "iterator-error"])
def test_inference_failure_retries_on_cpu_without_typing_partial_results(
    session, monkeypatch, lazy
):
    def fail(*_):
        if not lazy:
            raise RuntimeError("GPU unavailable")

        def segments():
            yield segment("Partial GPU output")
            raise RuntimeError("GPU unavailable during iteration")

        return segments()

    def cpu_transcribe(audio, **kwargs):
        return iter([segment("Recovered words.")]), None

    cpu = SimpleNamespace(transcribe=cpu_transcribe)
    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        SimpleNamespace(WhisperModel=lambda *a, **kw: cpu),
    )
    assert session.run(decode=fail) == 0
    assert session.typed == ["Recovered words."]
    assert engine.RUNTIME["device"] == "cpu"
    assert engine.RUNTIME["model"] == "small.en"
    state = json.loads(engine._live_state_file().read_text())
    assert (state["model"], state["device"]) == ("small.en", "cpu")


@pytest.mark.parametrize(
    "failure", [RuntimeError("model failed"), ValueError("bad audio")]
)
def test_engine_failure_closes_reader_restores_audio_and_clears_state(
    monkeypatch, failure
):
    cleaned = []
    monkeypatch.setattr(engine, "CFG", {**engine.CFG, "strict_offline": False})
    monkeypatch.setattr(engine.signal, "signal", lambda *a: None)
    monkeypatch.setattr(
        engine,
        "AudioReader",
        lambda: SimpleNamespace(close=lambda: cleaned.append("reader")),
    )

    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(engine, "run_session", fail)
    monkeypatch.setattr(engine, "unmute_out", lambda: cleaned.append("audio"))
    monkeypatch.setattr(engine, "_clear_live_state", lambda: cleaned.append("state"))
    with pytest.raises(type(failure), match=str(failure)):
        engine.main()
    assert cleaned == ["reader", "audio", "state"]

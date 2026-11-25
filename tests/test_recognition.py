"""Opt-in real CPU recognition; never download models or inject desktop input."""

import importlib.util
import json
import os
from pathlib import Path
import socket
import time
from types import SimpleNamespace
import wave

import numpy as np
import pytest


pytestmark = pytest.mark.recognition


def support():
    path = Path(__file__).resolve().parents[1] / "scripts/recognition.py"
    spec = importlib.util.spec_from_file_location("recognition", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def cpu_model(pytestconfig):
    tools = support()
    directory = pytestconfig.getoption("--recognition-model") or os.environ.get(
        "TAYS_TEST_MODEL_DIR"
    )
    assert directory, (
        "Run prepare-test-model.py and pass --recognition-model or set TAYS_TEST_MODEL_DIR"
    )
    tools.verify_files(directory, tools.manifest()["model"]["files"])

    def no_network(*args, **kwargs):
        pytest.fail("Model loading and recognition must remain offline")

    with pytest.MonkeyPatch.context() as offline:
        offline.setattr(socket.socket, "connect", no_network)
        offline.setattr(socket, "create_connection", no_network)
        from type_as_you_speak import engine

        offline.setattr(engine, "CFG", {**engine.CFG, "strict_offline": True})
        yield engine._load_model(
            directory,
            device="cpu",
            compute_type="int8",
            cpu_threads=2,
        )


@pytest.fixture
def recognized(cpu_model, monkeypatch, tmp_path, pytestconfig):
    from type_as_you_speak import engine

    installed = pytestconfig.getoption("--recognition-installed-path")
    if installed:
        assert Path(engine.__file__).resolve().is_relative_to(Path(installed).resolve())

    def blocked(*args, **kwargs):
        pytest.fail("Recognition checks must not use network or desktop commands")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(engine.subprocess, "run", blocked)
    monkeypatch.setattr(engine.subprocess, "Popen", blocked)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setattr(engine, "build_model", lambda: cpu_model)
    original = cpu_model.transcribe
    monkeypatch.setattr(
        cpu_model,
        "transcribe",
        lambda audio, **kw: original(audio, beam_size=5, temperature=0, **kw),
    )
    monkeypatch.setattr(engine, "notify_done", lambda: None)
    monkeypatch.setattr(engine, "notify_ready", lambda: None)
    settings = dict(
        SR=16000,
        CHUNK_S=0.3,
        CHUNK_BYTES=19200,
        TRANSCRIBE_EVERY_S=1e12,
        MIN_PENDING_S=0.7,
        MAX_SESSION_S=600,
        VAD_THRESHOLD=0.5,
        LANG="en",
        PROMPT_TAIL_WORDS=12,
        HOTWORDS="",
        HOTWORD_ENTRIES=[],
        NO_REPEAT_NGRAM_SIZE=2,
        CONDITION_ON_PREVIOUS_TEXT=False,
        _stop={"flag": False},
        RUNTIME={"model": "tiny.en", "device": "cpu"},
    )
    for name, value in settings.items():
        monkeypatch.setattr(engine, name, value)
    monkeypatch.setattr(
        engine,
        "WHISPER_HALLUCINATION_TAILS",
        list(engine._cfgmod.DEFAULTS["hallucination_tails"]),
    )
    typed = []
    monkeypatch.setattr(
        engine,
        "make_type",
        lambda: (lambda text: typed.append(text) or True, lambda: None),
    )

    def run(audio):
        chunks = iter(audio[i : i + 4800] for i in range(0, len(audio), 4800))
        reader = SimpleNamespace(
            read_chunk=lambda **kw: next(chunks, None),
            close=lambda: None,
            _src="",
            _buf=b"",
            _thread=SimpleNamespace(is_alive=lambda: False),
        )
        start = time.perf_counter()
        status = engine.run_session(reader, time.time())
        return status, "".join(typed), time.perf_counter() - start

    return run


@pytest.mark.parametrize("noise", [0.0, 0.002], ids=["clean", "seeded-noise"])
def test_known_recording_reaches_commit_with_bounded_error(recognized, noise):
    tools = support()
    recording = tools.manifest()["recording"]
    tools.verify_files(tools.FIXTURES, {recording["path"]: recording["sha256"]})
    with wave.open(str(tools.FIXTURES / recording["path"]), "rb") as source:
        assert (
            source.getnchannels(),
            source.getsampwidth(),
            source.getframerate(),
        ) == (1, 2, 16000)
        audio = (
            np.frombuffer(source.readframes(source.getnframes()), dtype="<i2").astype(
                np.float32
            )
            / 32768
        )
    if noise:
        audio = audio + np.random.default_rng(0).normal(0, noise, len(audio)).astype(
            np.float32
        )
    status, text, elapsed = recognized(audio)
    wer, cer = tools.error_rates(recording["reference"], text)
    print(
        json.dumps(
            dict(
                fixture=recording["id"],
                noise_std=noise,
                wer=wer,
                cer=cer,
                elapsed_s=round(elapsed, 3),
                audio_s=len(audio) / 16000,
                model_revision=tools.manifest()["model"]["revision"],
            )
        )
    )
    assert status == 0
    assert wer <= recording["max_wer"]
    assert cer <= recording["max_cer"]


def test_silence_never_reaches_the_input_boundary(recognized):
    status, text, _ = recognized(np.zeros(32000, dtype=np.float32))
    assert status == 3
    assert text == ""

import os
from types import SimpleNamespace

import numpy as np
import pytest

from type_as_you_speak import cli, engine


def test_dry_run_does_not_log_dictation(monkeypatch, capsys):
    monkeypatch.setenv("DICTATE_DRY_RUN", "1")
    monkeypatch.setenv("YDOTOOL_SOCKET", "/unused")
    type_text, _ = engine.make_type()
    assert type_text("private account number 123456")
    output = capsys.readouterr().err
    assert "private account" not in output
    assert "123456" not in output
    assert "chars" in output


def test_session_diagnostics_do_not_include_transcripts(monkeypatch, capsys):
    secret = "confidential customer account"
    word = SimpleNamespace(word=secret, start=0.0, end=0.8)
    segment = SimpleNamespace(text=secret, start=0.0, end=0.8, words=[word])
    model = SimpleNamespace(transcribe=lambda *a, **kw: ([segment], None))
    chunks = iter([np.ones(16000, dtype=np.float32), None])
    reader = SimpleNamespace(
        read_chunk=lambda **kw: next(chunks),
        close=lambda: None,
        _src=None,
        _buf=b"",
        _thread=SimpleNamespace(is_alive=lambda: False),
    )
    typed = []
    monkeypatch.setattr(engine, "_preload_nvidia", lambda: None)
    monkeypatch.setattr(engine, "build_model", lambda: model)
    monkeypatch.setattr(
        engine, "get_vad", lambda: lambda a: np.ones((len(a) + 511) // 512)
    )
    monkeypatch.setattr(engine, "_write_live_state", lambda: None)
    monkeypatch.setattr(
        engine,
        "make_type",
        lambda: (lambda text: typed.append(text) or True, lambda: None),
    )
    monkeypatch.setattr(engine, "notify_done", lambda: None)
    monkeypatch.setattr(engine, "_stop", {"flag": False})
    assert engine.run_session(reader, engine.time.time()) == 0
    assert secret in " ".join(typed)
    output = capsys.readouterr().err
    assert secret not in output
    assert "chars" in output


@pytest.mark.skipif(os.name == "nt", reason="POSIX file permissions")
def test_session_state_and_log_are_private(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    state = tmp_path / "type-as-you-speak"
    state.mkdir(mode=0o755)
    log = state / "live.log"
    log.write_text("old log\n")
    log.chmod(0o644)
    cli._log_line("session started")
    assert state.stat().st_mode & 0o777 == 0o700
    assert log.stat().st_mode & 0o777 == 0o600


def test_dry_run_does_not_require_linux_user_ids(monkeypatch):
    monkeypatch.setenv("DICTATE_DRY_RUN", "1")
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    monkeypatch.delattr(os, "getuid", raising=False)
    type_text, _ = engine.make_type()
    assert type_text("portable dry run")

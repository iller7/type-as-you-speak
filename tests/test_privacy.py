import os
from pathlib import Path
import subprocess
import shutil
import sys
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
    monkeypatch.setattr(engine, "notify_ready", lambda: None)
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


@pytest.mark.parametrize("inherited", [None, "0"])
def test_app_startup_disables_telemetry_before_loading_dependencies(inherited):
    env = dict(os.environ)
    for name in ("ORT_DISABLE_TELEMETRY", "HF_HUB_DISABLE_TELEMETRY", "DO_NOT_TRACK"):
        env.pop(name, None)
        if inherited is not None:
            env[name] = inherited
    env["HF_XET_TELEMETRY_ENABLED"] = "1"
    code = """
import os, sys
import type_as_you_speak
assert os.environ['ORT_DISABLE_TELEMETRY'] == '1'
assert os.environ['HF_HUB_DISABLE_TELEMETRY'] == '1'
assert os.environ['DO_NOT_TRACK'] == '1'
assert os.environ['HF_XET_TELEMETRY_ENABLED'] == '0'
assert 'onnxruntime' not in sys.modules
assert 'faster_whisper' not in sys.modules
from huggingface_hub import constants
assert constants.HF_HUB_DISABLE_TELEMETRY
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_vad_cannot_start_before_runtime_telemetry_is_disabled(monkeypatch):
    runtime = SimpleNamespace(enabled=True)

    def disable():
        runtime.enabled = False

    def vad():
        assert not runtime.enabled, "VAD created before telemetry was disabled"
        return "local VAD"

    monkeypatch.setitem(
        sys.modules, "onnxruntime", SimpleNamespace(disable_telemetry_events=disable)
    )
    monkeypatch.setitem(
        sys.modules, "faster_whisper.vad", SimpleNamespace(get_vad_model=vad)
    )
    assert engine.get_vad() == "local VAD"


def test_gui_download_child_uses_app_privacy_policy(monkeypatch, tmp_path):
    from type_as_you_speak import gui

    private = tmp_path / "private-deps"
    shutil.copytree(Path(gui.__file__).parent, private / "type_as_you_speak")
    monkeypatch.setattr(gui, "__file__", str(private / "type_as_you_speak/gui.py"))
    monkeypatch.setattr(
        gui.privacy, "__file__", str(private / "type_as_you_speak/privacy.py")
    )
    monkeypatch.delenv("PYTHONPATH", raising=False)
    monkeypatch.setenv("ORT_DISABLE_TELEMETRY", "0")
    monkeypatch.setenv("HF_HUB_DISABLE_TELEMETRY", "0")
    commands = []
    worker = SimpleNamespace(
        _dl_line="Downloading tiny.en…", _log_download=lambda *args: None
    )

    class Child:
        stdout = []
        returncode = 0

        def wait(self, timeout):
            return self.returncode

    def launch(command, **kwargs):
        commands.append((command, kwargs["env"]))
        return Child()

    with monkeypatch.context() as capture:
        capture.setattr(gui.subprocess, "Popen", launch)
        gui.SettingsWindow._download_worker(worker, "tiny.en")
    assert worker._dl_result == (True, "done")
    assert len(commands) == 1
    (private / "onnxruntime.py").write_text(
        "enabled = True\n"
        "def disable_telemetry_events():\n"
        "    global enabled\n"
        "    enabled = False\n"
    )
    (private / "faster_whisper.py").write_text(
        "import os, onnxruntime\n"
        "assert os.environ['ORT_DISABLE_TELEMETRY'] == '1'\n"
        "assert os.environ['HF_HUB_DISABLE_TELEMETRY'] == '1'\n"
        "assert os.environ['DO_NOT_TRACK'] == '1'\n"
        "assert os.environ['HF_XET_TELEMETRY_ENABLED'] == '0'\n"
        "assert not onnxruntime.enabled\n"
        "def WhisperModel(*args, **kwargs): pass\n"
    )
    command, env = commands[0]
    # Hide the developer installation; only the private bundle may supply the app.
    result = subprocess.run(
        [command[0], "-S", *command[1:]],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("boundary", ["get_vad", "build_model"])
def test_inference_fails_closed_when_runtime_opt_out_fails(monkeypatch, boundary):
    def broken_opt_out():
        raise RuntimeError("telemetry opt-out unavailable")

    monkeypatch.setitem(
        sys.modules,
        "onnxruntime",
        SimpleNamespace(disable_telemetry_events=broken_opt_out),
    )
    with pytest.raises(RuntimeError, match="telemetry opt-out unavailable"):
        getattr(engine, boundary)()


@pytest.mark.parametrize(
    "loader,inline", [("load_hotwords", "safe"), ("load_tail_lines", ["safe"])]
)
def test_unreadable_phrase_files_do_not_log_private_paths(
    loader, inline, tmp_path, capsys
):
    secret_path = tmp_path / "private-customer-phrase-list"
    getattr(engine, loader)(inline, str(secret_path))
    output = capsys.readouterr().err
    assert "unreadable" in output
    assert "FileNotFoundError" in output
    assert str(secret_path) not in output


def test_gpu_load_failure_does_not_log_exception_payload(monkeypatch, capsys):
    monkeypatch.setattr(engine, "CFG", {**engine.CFG, "device": "cuda"})
    monkeypatch.setattr(engine, "_detect_gpu_name", lambda: None)

    def fail(*args, **kwargs):
        raise RuntimeError("private access-token and customer phrase")

    monkeypatch.setattr(engine, "_load_model", fail)
    with pytest.raises(RuntimeError, match="device=cuda"):
        engine.build_model()
    output = capsys.readouterr().err
    assert "RuntimeError" in output
    assert "private access-token" not in output
    assert "customer phrase" not in output


def test_live_metadata_is_atomic_and_private(monkeypatch, tmp_path):
    import json

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setattr(engine, "RUNTIME", {"state": "preparing"})
    target = engine._live_state_file()
    target.parent.mkdir(mode=0o755)
    target.write_text('{"state":"old"}')
    target.chmod(0o644)
    engine._write_live_state()
    assert json.loads(target.read_text())["state"] == "preparing"
    if os.name != "nt":
        assert target.stat().st_mode & 0o777 == 0o600
        assert target.parent.stat().st_mode & 0o777 == 0o700


def test_failed_live_metadata_replace_preserves_previous_state(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    target = engine._live_state_file()
    target.parent.mkdir()
    target.write_text('{"state":"old"}')

    def fail_replace(*args, **kwargs):
        raise OSError("disk failure")

    monkeypatch.setattr(engine.os, "replace", fail_replace)
    engine._write_live_state()
    assert target.read_text() == '{"state":"old"}'
    assert list(target.parent.iterdir()) == [target]

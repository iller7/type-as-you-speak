import subprocess
import sys
from types import SimpleNamespace

import pytest

from type_as_you_speak import cli, config


def test_strict_offline_is_default_and_bad_values_cannot_enable_network(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("DICTATE_STRICT_OFFLINE", raising=False)
    assert config.load_config()["strict_offline"] is True
    path = config.user_config_path()
    path.parent.mkdir()
    path.write_text('strict_offline = "false"\n')
    assert config.load_config()["strict_offline"] is True
    path.write_text("strict_offline = false\n")
    assert config.load_config()["strict_offline"] is False
    monkeypatch.setenv("DICTATE_STRICT_OFFLINE", "typo")
    assert config.load_config()["strict_offline"] is True
    monkeypatch.setenv("DICTATE_STRICT_OFFLINE", "0")
    assert config.load_config()["strict_offline"] is False


def test_guard_failure_stops_start_before_helpers_or_microphone(monkeypatch, capsys):
    from type_as_you_speak import offline

    def fail():
        raise RuntimeError("network protection unavailable")

    monkeypatch.setattr(offline, "enforce", fail)
    monkeypatch.setattr(cli, "_prepare_env", lambda: pytest.fail("helpers started"))
    monkeypatch.setattr(cli._config, "load_config", lambda: {"strict_offline": True})
    assert cli.cmd_start(SimpleNamespace()) == 2
    assert "network protection unavailable" in capsys.readouterr().err


@pytest.mark.skipif(sys.platform != "linux", reason="Linux seccomp process enforcement")
def test_network_guard_blocks_native_threads_and_exec_but_preserves_unix_ipc():
    code = r"""
import ctypes, errno, socket, subprocess, sys, threading
from type_as_you_speak import offline
ready = threading.Event()
run = threading.Event()
failures = []
def denied():
    for family in (socket.AF_INET, socket.AF_INET6):
        for kind in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
            try:
                socket.socket(family, kind)
            except OSError as e:
                assert e.errno == errno.EPERM
            else:
                failures.append('network socket permitted')
def existing_thread():
    ready.set()
    run.wait()
    denied()
t = threading.Thread(target=existing_thread)
t.start()
ready.wait()
offline.enforce()
run.set()
t.join()
denied()
t = threading.Thread(target=denied)
t.start()
t.join()
assert not failures, failures
libc = ctypes.CDLL(None, use_errno=True)
assert libc.socket(socket.AF_INET, socket.SOCK_STREAM, 0) == -1
assert ctypes.get_errno() == errno.EPERM
library = offline._library()
for name in (b'io_uring_setup', b'io_uring_enter', b'io_uring_register'):
    number = library.seccomp_syscall_resolve_name(name)
    assert libc.syscall(number, 0, 0, 0, 0, 0, 0) == -1
    assert ctypes.get_errno() == errno.EPERM
left, right = socket.socketpair()
left.sendall(b'local IPC')
assert right.recv(9) == b'local IPC'
left.close(); right.close()
child = subprocess.run([sys.executable, '-c', 'import socket; socket.socket(socket.AF_INET, socket.SOCK_DGRAM)'], capture_output=True)
assert child.returncode != 0 and b'Operation not permitted' in child.stderr
print('guard passed')
"""
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr
    assert "guard passed" in result.stdout


@pytest.mark.skipif(sys.platform != "linux", reason="Linux inherited descriptor policy")
def test_existing_internet_socket_prevents_strict_start():
    code = """
import socket
from type_as_you_speak import offline
existing = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    offline.enforce()
except RuntimeError as error:
    assert 'inherited' in str(error)
else:
    raise AssertionError('inherited network descriptor accepted')
"""
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr


def test_generated_setup_config_preserves_strict_default():
    import tomllib

    loaded = tomllib.loads(cli._sample_config_text())
    assert loaded["strict_offline"] is True
    assert loaded["condition_on_previous_text"] is False


@pytest.mark.parametrize(
    "live", [None, {"strict_offline": False, "network_guard": False}]
)
def test_status_uses_active_privacy_not_the_saved_checkbox(monkeypatch, live):
    monkeypatch.setattr(cli, "_is_running", lambda: (True, 123))
    monkeypatch.setattr(cli, "_read_live_state", lambda pid: live)
    monkeypatch.setattr(cli, "_cpu_name", lambda: None)
    monkeypatch.setattr(
        cli._config,
        "load_config",
        lambda: {
            "model_name": "tiny.en",
            "device": "cpu",
            "strict_offline": True,
        },
    )
    status = cli._status_dict()
    assert status["strict_offline"] is (None if live is None else False)
    assert status["network_guard"] is (None if live is None else False)


@pytest.mark.parametrize("failure", ["init", "nnp", "tsync", "rule", "resolve", "load"])
def test_native_filter_failures_cannot_silently_enable_network(monkeypatch, failure):
    from type_as_you_speak import offline

    library = SimpleNamespace(
        seccomp_init=lambda action: None if failure == "init" else 1,
        seccomp_release=lambda context: None,
        seccomp_attr_set=lambda context, attr, value: (
            -1 if (failure, attr) in [("nnp", 3), ("tsync", 4)] else 0
        ),
        seccomp_syscall_resolve_name=lambda name: -1 if failure == "resolve" else 1,
        seccomp_rule_add_array=lambda *args: -1 if failure == "rule" else 0,
        seccomp_load=lambda context: -1 if failure == "load" else 0,
    )
    monkeypatch.setattr(offline, "_active", False)
    monkeypatch.setattr(offline.sys, "platform", "linux")
    monkeypatch.setattr(offline, "_library", lambda: library)
    with pytest.raises(RuntimeError, match="Strict offline protection unavailable"):
        offline.enforce()
    assert offline.active() is False


def test_inherited_ring_is_rejected_without_closing_it(monkeypatch, tmp_path):
    from type_as_you_speak import offline

    monkeypatch.setattr(offline.Path, "iterdir", lambda path: iter([tmp_path / "123"]))
    monkeypatch.setattr(offline.os, "readlink", lambda path: "anon_inode:[io_uring]")
    with pytest.raises(RuntimeError, match="inherited io_uring"):
        offline._reject_inherited_network()


def test_explicit_download_is_available_while_strict_mode_is_enabled(
    monkeypatch, capsys
):
    from type_as_you_speak import privacy

    monkeypatch.setattr(privacy, "disable_inference_telemetry", lambda: None)
    monkeypatch.setattr(
        cli._config,
        "load_config",
        lambda: {"strict_offline": True, "model_name": "tiny.en"},
    )

    def download(name):
        assert name == "tiny.en"

    monkeypatch.setitem(
        sys.modules, "faster_whisper.utils", SimpleNamespace(download_model=download)
    )
    assert cli.main(["download"]) == 0
    assert "Model downloaded" in capsys.readouterr().out


def test_missing_native_library_cannot_silently_enable_network(monkeypatch):
    from type_as_you_speak import offline

    monkeypatch.setattr(offline, "_active", False)
    monkeypatch.setattr(offline.sys, "platform", "linux")
    monkeypatch.setattr(offline.ctypes.util, "find_library", lambda name: None)
    with pytest.raises(RuntimeError, match="install libseccomp"):
        offline.enforce()


def test_uncached_strict_model_does_not_open_the_microphone(monkeypatch, capsys):
    from type_as_you_speak import engine, offline

    monkeypatch.setattr(offline, "enforce", lambda: None)
    monkeypatch.setattr(offline, "active", lambda: True)
    monkeypatch.setattr(engine, "CFG", {**engine.CFG, "strict_offline": True})
    monkeypatch.setattr(engine, "RUNTIME", {})
    monkeypatch.setattr(engine.signal, "signal", lambda *args: None)
    monkeypatch.setattr(engine, "_preload_nvidia", lambda: None)

    def missing():
        raise RuntimeError("Use tays download before strict offline dictation")

    monkeypatch.setattr(engine, "build_model", missing)
    monkeypatch.setattr(engine, "AudioReader", lambda: pytest.fail("microphone opened"))
    assert engine.main() == 2
    assert "tays download" in capsys.readouterr().err


def test_successful_start_enforces_policy_before_session_helpers(monkeypatch):
    from type_as_you_speak import engine, offline

    events = []
    monkeypatch.setattr(cli._config, "load_config", lambda: {"strict_offline": True})
    monkeypatch.setattr(offline, "enforce", lambda: events.append("guard"))
    monkeypatch.setattr(cli, "_prepare_env", lambda: events.append("helpers"))
    monkeypatch.setattr(cli, "_is_running", lambda: (False, None))
    monkeypatch.setattr(cli, "_write_pid", lambda pid: None)
    monkeypatch.setattr(cli, "_remove_pid", lambda: None)
    monkeypatch.setattr(cli, "_log_line", lambda *args: None)
    monkeypatch.setattr(cli, "_duck_restore_stale", lambda: None)
    monkeypatch.setattr(cli, "_duck_on", lambda pid: None)
    monkeypatch.setattr(cli, "_duck_off", lambda: None)
    monkeypatch.setattr(engine, "main", lambda: events.append("engine") or 0)
    assert cli.cmd_start(SimpleNamespace()) == 0
    assert events == ["guard", "helpers", "engine"]


@pytest.mark.skipif(sys.platform != "linux", reason="Linux inherited descriptor policy")
@pytest.mark.parametrize("stdio", [False, True])
def test_exec_inherited_internet_socket_fails_without_closing_it(stdio):
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as network:
        descriptor = 0 if stdio else network.fileno()
        code = f"""
import os
from type_as_you_speak import offline
try:
    offline.enforce()
except RuntimeError as error:
    assert 'inherited network socket' in str(error)
    os.fstat({descriptor})
else:
    raise AssertionError('inherited socket accepted')
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            pass_fds=() if stdio else (network.fileno(),),
            stdin=network if stdio else None,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr

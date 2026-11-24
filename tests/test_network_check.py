import importlib.util
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check-inference-network.py"


def checker():
    spec = importlib.util.spec_from_file_location("network_check", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "probe_trace", ["socket(0x2, 0x1, 0) = 3", "syscall_0xffff(0) = 0"]
)
def test_network_or_invalid_trace_cannot_pass(monkeypatch, tmp_path, probe_trace):
    module = checker()
    traces = iter(["socket(0x2) = 3\nsocket(0xa) = 3", probe_trace])
    monkeypatch.setattr(module, "trace_command", lambda *args: next(traces))
    with pytest.raises(RuntimeError, match="network activity or invalid trace"):
        module.check(tmp_path)


def test_unproven_tracer_cannot_report_privacy_success(monkeypatch, tmp_path):
    module = checker()
    monkeypatch.setattr(module, "trace_command", lambda *args: "")
    with pytest.raises(RuntimeError, match="positive control"):
        module.check(tmp_path)


@pytest.mark.parametrize(
    "status,stderr", [(1, ""), (0, "strace: Exit of unknown pid 27 ignored")]
)
def test_probe_failure_or_tracer_warning_cannot_pass(
    monkeypatch, tmp_path, status, stderr
):
    module = checker()
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=status, stderr=stderr),
    )
    with pytest.raises(RuntimeError, match="probe or tracer failed"):
        module.trace_command(["unused"], tmp_path / "trace", {})


def test_tracer_timeout_cannot_report_success(monkeypatch, tmp_path):
    module = checker()

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("strace", 120)

    monkeypatch.setattr(module.subprocess, "run", timeout)
    with pytest.raises(RuntimeError, match="timed out"):
        module.trace_command(["unused"], tmp_path / "trace", {})

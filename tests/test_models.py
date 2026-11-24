import sys
from types import SimpleNamespace

import pytest

from type_as_you_speak import engine


@pytest.fixture
def model_factory(monkeypatch):
    monkeypatch.setattr(
        engine, "CFG", {"device": "auto", "model_name": "large-v3", "cpu_threads": 2}
    )
    monkeypatch.setattr(engine, "RUNTIME", {})
    monkeypatch.setattr(engine, "_detect_gpu_name", lambda: "Test GPU")
    calls = []

    def install(fail=lambda name, device: False):
        def factory(name, **kwargs):
            calls.append((name, kwargs))
            if fail(name, kwargs["device"]):
                raise RuntimeError("unavailable")
            return SimpleNamespace(name=name, device=kwargs["device"])

        monkeypatch.setitem(
            sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=factory)
        )

    return SimpleNamespace(install=install, calls=calls)


def test_forced_cpu_never_probes_or_loads_a_gpu(model_factory, monkeypatch):
    engine.CFG["device"] = "cpu"
    model_factory.install()
    monkeypatch.setattr(
        engine, "_detect_gpu_name", lambda: pytest.fail("CPU mode must not probe GPU")
    )
    model = engine.build_model()
    assert model.device == "cpu"
    assert model_factory.calls == [
        (
            "large-v3",
            {"device": "cpu", "compute_type": "int8", "local_files_only": True},
        )
    ]
    assert engine.RUNTIME == {"model": "large-v3", "device": "cpu"}


def test_primary_gpu_model_is_used_when_available(model_factory):
    model_factory.install()
    assert engine.build_model().name == "large-v3"
    assert len(model_factory.calls) == 1
    assert engine.RUNTIME == {"model": "large-v3", "device": "cuda"}


def test_gpu_memory_failure_uses_the_next_model_and_reports_it(model_factory):
    model_factory.install(fail=lambda name, device: name == "large-v3")
    assert engine.build_model().name == "medium.en"
    assert engine.RUNTIME == {"model": "medium.en", "device": "cuda"}


def test_auto_device_falls_back_to_requested_model_on_cpu(model_factory):
    model_factory.install(fail=lambda name, device: device == "cuda")
    result = engine.build_model()
    assert (result.name, result.device) == ("large-v3", "cpu")
    assert engine.RUNTIME == {"model": "large-v3", "device": "cpu"}


@pytest.mark.parametrize("device", ["cuda", "rocm"])
def test_forced_gpu_failure_does_not_silently_choose_cpu(model_factory, device):
    engine.CFG["device"] = device
    model_factory.install(fail=lambda *_: True)
    with pytest.raises(RuntimeError, match=f"device={device}"):
        engine.build_model()
    assert all(options["device"] == "cuda" for _, options in model_factory.calls)
    assert engine.RUNTIME == {}


def test_cpu_load_failure_propagates_without_a_misleading_runtime(model_factory):
    engine.CFG["device"] = "cpu"
    model_factory.install(fail=lambda *_: True)
    with pytest.raises(RuntimeError, match="unavailable"):
        engine.build_model()
    assert engine.RUNTIME == {}


@pytest.mark.parametrize("strict", [True, False])
def test_every_gpu_ladder_and_cpu_load_respects_offline_policy(model_factory, strict):
    engine.CFG["strict_offline"] = strict
    model_factory.install(fail=lambda name, device: device == "cuda")
    engine.build_model()
    assert all(
        options["local_files_only"] is strict for _, options in model_factory.calls
    )

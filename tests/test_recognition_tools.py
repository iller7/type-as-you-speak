import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/recognition.py"


def tools():
    assert SCRIPT.exists(), (
        "Recognition checks need shared normalization and error metrics"
    )
    spec = importlib.util.spec_from_file_location("recognition", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "reference,hypothesis,wer",
    [
        ("Hello world", "hello, WORLD!", 0),
        ("one two three four", "one three four", 0.25),
        ("one two", "one blue two", 0.5),
        ("one two", "one three", 0.5),
        ("one two", "", 1),
        ("one", "two three four", 3),
    ],
)
def test_word_error_rates_measure_edits_not_formatting(reference, hypothesis, wer):
    assert tools().error_rates(reference, hypothesis)[0] == wer


def test_character_error_rate_detects_the_known_homophone_spelling():
    assert tools().error_rates("cat", "cats")[1] == pytest.approx(1 / 3)


def test_empty_reference_requires_a_separate_silence_assertion():
    with pytest.raises(ValueError, match="reference"):
        tools().error_rates("", "hallucination")


def test_model_integrity_rejects_a_corrupted_download(tmp_path):
    (tmp_path / "model.bin").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="model.bin"):
        tools().verify_files(tmp_path, {"model.bin": "0" * 64})


def test_model_integrity_rejects_an_incomplete_download(tmp_path):
    with pytest.raises(ValueError, match="missing"):
        tools().verify_files(tmp_path, {"model.bin": "0" * 64})


def test_public_wav_fixture_has_verified_bytes_and_expected_pcm_format():
    import wave

    module = tools()
    recording = module.manifest()["recording"]
    module.verify_files(module.FIXTURES, {recording["path"]: recording["sha256"]})
    with wave.open(str(module.FIXTURES / recording["path"]), "rb") as source:
        assert (
            source.getnchannels(),
            source.getsampwidth(),
            source.getframerate(),
        ) == (1, 2, 16000)
        assert source.getnframes() > 16000


@pytest.mark.parametrize(
    "requested,actual,compute",
    [
        ("cuda", "cpu", "int8_float32"),
        ("cpu", "cuda", "float16"),
        ("cuda", "cuda", "float32"),
        ("cpu", "cpu", "float32"),
    ],
)
def test_explicit_hardware_validation_rejects_fallback(requested, actual, compute):
    from types import SimpleNamespace

    model = SimpleNamespace(model=SimpleNamespace(device=actual, compute_type=compute))
    with pytest.raises(ValueError, match="Requested"):
        tools().verified_backend(model, requested)


@pytest.mark.parametrize(
    "device,compute", [("cpu", "int8_float32"), ("cuda", "float16")]
)
def test_explicit_hardware_validation_reports_loaded_backend(device, compute):
    from types import SimpleNamespace

    model = SimpleNamespace(model=SimpleNamespace(device=device, compute_type=compute))
    assert tools().verified_backend(model, device) == {
        "device": device,
        "compute_type": compute,
    }

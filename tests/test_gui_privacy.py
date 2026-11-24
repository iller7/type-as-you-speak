import json
import subprocess

import pytest


@pytest.fixture
def settings(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("DICTATE_STRICT_OFFLINE", raising=False)
    from PySide6.QtWidgets import QApplication
    from type_as_you_speak import gui

    application = QApplication.instance() or QApplication([])
    monkeypatch.setattr(gui, "_nvidia_gpu", lambda: None)
    monkeypatch.setattr(gui, "_amd_gpu", lambda: None)
    monkeypatch.setattr(gui, "_gpu_count", lambda: 0)
    monkeypatch.setattr(gui, "_model_available", lambda name: False)
    monkeypatch.setattr(
        gui.SettingsWindow,
        "_tays",
        lambda *args: subprocess.CompletedProcess(
            [], 0, json.dumps({"running": False})
        ),
    )
    window = gui.SettingsWindow()
    yield window
    window._timer.stop()
    window.close()
    assert application is not None


def test_strict_checkbox_is_default_and_survives_save_reload(settings):
    from type_as_you_speak import config

    checkbox = settings._fields["strict_offline"]
    assert checkbox.isChecked()
    assert "Download" in settings.dl_btn.text()
    checkbox.setChecked(False)
    settings.save()
    assert config.load_config()["strict_offline"] is False
    checkbox.setChecked(True)
    settings.reload()
    assert checkbox.isChecked() is False
    checkbox.setChecked(True)
    settings.save()
    assert config.load_config()["strict_offline"] is True


def test_saved_strict_setting_cannot_claim_an_unprotected_session_is_protected(
    settings,
):
    line = settings._status_line(
        {
            "running": True,
            "device": "cpu",
            "model": "tiny.en",
            "strict_offline": False,
            "network_guard": False,
        }
    )
    assert "strict offline disabled" in line
    assert "stop and restart" in line
    unknown = settings._status_line({"running": True, "device": "cpu"})
    assert "privacy status unknown" in unknown


def test_environment_override_is_visible_and_does_not_overwrite_saved_policy(
    settings, monkeypatch
):
    import tomllib
    from type_as_you_speak import config, gui

    settings.save()
    monkeypatch.setenv("DICTATE_STRICT_OFFLINE", "0")
    overridden = gui.SettingsWindow()
    try:
        checkbox = overridden._fields["strict_offline"]
        assert checkbox.isChecked() is False
        assert checkbox.isEnabled() is False
        overridden.save()
        saved = tomllib.loads(config.user_config_path().read_text())
        assert saved["strict_offline"] is True
    finally:
        overridden._timer.stop()
        overridden.close()


def test_settings_use_utf8_even_with_a_windows_style_default_encoding(
    settings, monkeypatch
):
    from pathlib import Path
    from type_as_you_speak import config

    original_write = Path.write_text
    target = config.user_config_path()

    def platform_default(path, data, encoding=None, **kwargs):
        if path == target and encoding is None:
            encoding = "cp1252"
        return original_write(path, data, encoding=encoding, **kwargs)

    monkeypatch.setattr(Path, "write_text", platform_default)
    settings._fields["strict_offline"].setChecked(False)
    settings.save()
    target.read_bytes().decode("utf-8")
    assert config.load_config()["strict_offline"] is False

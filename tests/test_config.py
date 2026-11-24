from type_as_you_speak import config


def test_config_precedence_and_unknown_keys(tmp_path, monkeypatch):
    for name in config._ENV_MAP:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = config.user_config_path()
    path.parent.mkdir()
    path.write_text('model_name = "base.en"\nunknown = "ignored"\n')
    assert config.load_config()["model_name"] == "base.en"
    monkeypatch.setenv("DICTATE_MODEL", "tiny.en")
    loaded = config.load_config()
    assert loaded["model_name"] == "tiny.en"
    assert "unknown" not in loaded


def test_invalid_environment_value_keeps_default(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("DICTATE_CPU_THREADS", "invalid")
    assert config.load_config()["cpu_threads"] == config.DEFAULTS["cpu_threads"]


def test_default_lists_are_not_shared(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    config.load_config()["hallucination_tails"].append("test phrase")
    assert "test phrase" not in config.load_config()["hallucination_tails"]


def test_grouped_file_values_are_overridden_by_environment(tmp_path, monkeypatch):
    for name in config._ENV_MAP:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = config.user_config_path()
    path.parent.mkdir()
    path.write_text('[model]\nmodel_name = "base.en"\ncpu_threads = 4\n')
    monkeypatch.setenv("DICTATE_CPU_THREADS", "6")
    loaded = config.load_config()
    assert loaded["model_name"] == "base.en"
    assert loaded["cpu_threads"] == 6


def test_invalid_environment_override_preserves_a_valid_file_value(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = config.user_config_path()
    path.parent.mkdir()
    path.write_text("cpu_threads = 4\n")
    monkeypatch.setenv("DICTATE_CPU_THREADS", "not an integer")
    assert config.load_config()["cpu_threads"] == 4


def test_malformed_toml_does_not_prevent_environment_recovery(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = config.user_config_path()
    path.parent.mkdir()
    path.write_text('model_name = "unterminated\n')
    monkeypatch.setenv("DICTATE_MODEL", "tiny.en")
    assert config.load_config()["model_name"] == "tiny.en"

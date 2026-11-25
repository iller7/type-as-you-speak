import json
from types import SimpleNamespace

import pytest

from type_as_you_speak import cli


@pytest.mark.parametrize(
    "live",
    [
        None,
        [],
        {"pid": 123},
        {"pid": 123, "state": "unknown"},
        {"pid": 999, "state": "listening"},
    ],
)
def test_running_process_without_confirmed_readiness_is_preparing(
    monkeypatch, tmp_path, live
):
    monkeypatch.setattr(cli, "_is_running", lambda: (True, 123))
    monkeypatch.setattr(cli, "_state_dir", lambda: tmp_path)
    monkeypatch.setattr(cli, "_cpu_name", lambda: None)
    (tmp_path / "live.json").write_text(json.dumps(live))
    status = cli._status_dict()
    assert status["running"] is True
    assert status["state"] == "preparing"


def test_matching_live_session_can_report_listening(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "_is_running", lambda: (True, 123))
    monkeypatch.setattr(cli, "_state_dir", lambda: tmp_path)
    monkeypatch.setattr(cli, "_cpu_name", lambda: None)
    (tmp_path / "live.json").write_text(json.dumps({"pid": 123, "state": "listening"}))
    assert cli._status_dict()["state"] == "listening"


def test_detached_launch_does_not_announce_listening(monkeypatch, tmp_path, capsys):
    events = []
    monkeypatch.setattr(cli, "_prepare_env", lambda: None)
    monkeypatch.setattr(cli, "_is_running", lambda: (False, None))
    monkeypatch.setattr(cli, "_logfile", lambda: tmp_path / "session.log")
    monkeypatch.setattr(cli, "_log_line", lambda _: None)
    monkeypatch.setattr(cli.time, "sleep", lambda _: None)
    monkeypatch.setattr(cli, "_notify", lambda summary, body: events.append(summary))

    def launch(*args, **kwargs):
        events.append("launch")
        return SimpleNamespace(poll=lambda: None, pid=123)

    monkeypatch.setattr(cli.subprocess, "Popen", launch)
    assert cli.cmd_toggle(SimpleNamespace(json=False)) == 0
    assert events == ["Preparing dictation…", "launch"]
    assert "Listening… speak now" not in capsys.readouterr().out


def test_json_launch_remains_json_only(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "_prepare_env", lambda: None)
    monkeypatch.setattr(cli, "_is_running", lambda: (False, None))
    monkeypatch.setattr(cli, "_logfile", lambda: tmp_path / "session.log")
    monkeypatch.setattr(cli, "_log_line", lambda _: None)
    monkeypatch.setattr(cli.time, "sleep", lambda _: None)
    monkeypatch.setattr(cli, "_notify", lambda *a: pytest.fail("parent notification"))
    monkeypatch.setattr(
        cli, "_status_dict", lambda: {"running": True, "state": "preparing"}
    )
    monkeypatch.setattr(
        cli.subprocess,
        "Popen",
        lambda *a, **kw: SimpleNamespace(poll=lambda: None, pid=123),
    )
    assert cli.cmd_toggle(SimpleNamespace(json=True)) == 0
    assert json.loads(capsys.readouterr().out) == {
        "running": True,
        "state": "preparing",
    }

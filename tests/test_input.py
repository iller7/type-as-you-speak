import subprocess

import pytest

from type_as_you_speak import engine


@pytest.fixture
def input_commands(monkeypatch, tmp_path):
    monkeypatch.delenv("DICTATE_DRY_RUN", raising=False)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("WAYLAND_DISPLAY", "test-display")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("YDOTOOL_SOCKET", raising=False)
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(engine.subprocess, "run", run)
    return calls


def test_input_preserves_unicode_spacing_and_shell_characters_as_one_argument(
    input_commands,
):
    type_text, _ = engine.make_type()
    assert type_text("  café   $HOME; `echo unsafe`\n")
    args, options = input_commands[0]
    assert args[-1] == " café $HOME; `echo unsafe`"
    assert options.get("shell", False) is False
    assert options["timeout"] == 30


@pytest.mark.parametrize("text", ["", " \n\t ", "(background noise)"])
def test_empty_or_annotation_only_text_never_starts_an_input_command(
    input_commands, text
):
    type_text, _ = engine.make_type()
    assert type_text(text) is False
    assert input_commands == []


def test_injection_failure_preserves_text_in_clipboard_fallback(
    input_commands, monkeypatch
):
    def run(args, **kwargs):
        input_commands.append((args, kwargs))
        if args[0] == "ydotool":
            raise subprocess.CalledProcessError(1, args)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(engine.subprocess, "run", run)
    type_text, _ = engine.make_type()
    assert type_text(" café")
    args, options = input_commands[-1]
    assert args == ["wl-copy"]
    assert options["input"] == " café".encode()


def test_input_and_clipboard_failure_return_failure_without_transcript_logs(
    monkeypatch, input_commands, capsys
):
    secret = "synthetic private phrase"

    def fail(args, **kwargs):
        raise subprocess.CalledProcessError(1, args, stderr=secret)

    monkeypatch.setattr(engine.subprocess, "run", fail)
    type_text, _ = engine.make_type()
    assert type_text(secret) is False
    assert secret not in capsys.readouterr().err


def test_dry_run_never_starts_input_or_clipboard_commands(input_commands, monkeypatch):
    monkeypatch.setenv("DICTATE_DRY_RUN", "1")
    type_text, type_space = engine.make_type()
    assert type_text("Synthetic words.")
    type_space()
    assert input_commands == []


@pytest.mark.parametrize(
    "wayland,x11,expected",
    [
        ("wayland-0", ":1", ["wl-copy"]),
        (None, ":1", ["xclip", "-selection", "clipboard"]),
    ],
)
def test_clipboard_selection_uses_display_protocol_not_desktop_name(
    monkeypatch, wayland, x11, expected
):
    for name, value in [("WAYLAND_DISPLAY", wayland), ("DISPLAY", x11)]:
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "Sway")
    assert engine._clipboard_args() == expected

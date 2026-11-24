import sys

import pytest

from type_as_you_speak import cli


@pytest.mark.parametrize("platform", ["darwin", "win32"])
def test_linux_commands_fail_clearly_on_other_platforms(monkeypatch, capsys, platform):
    monkeypatch.setattr(
        cli,
        "_prepare_env",
        lambda: pytest.fail("Unsupported platforms must not prepare a Linux session"),
    )
    monkeypatch.setattr(sys, "platform", platform)
    assert cli.main(["start"]) == 2
    assert "Linux" in capsys.readouterr().err

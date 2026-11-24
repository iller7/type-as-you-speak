import os
import socket
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from type_as_you_speak import cli


@pytest.mark.skipif(os.name == "nt", reason="Linux daemon uses a Unix socket")
def test_daemon_uses_the_configured_private_socket(monkeypatch, tmp_path):
    with (
        tempfile.TemporaryDirectory(dir="/tmp") as directory,
        socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as server,
    ):
        path = Path(directory) / "custom.sock"
        monkeypatch.setenv("XDG_RUNTIME_DIR", directory)
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
        monkeypatch.setenv("YDOTOOL_SOCKET", str(path))
        monkeypatch.delenv("DICTATE_DRY_RUN", raising=False)
        monkeypatch.setattr(cli.shutil, "which", lambda exe: f"/usr/bin/{exe}")
        monkeypatch.setattr(
            cli.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=1)
        )
        monkeypatch.setattr(cli.time, "sleep", lambda _: None)
        commands = []

        def start(command, **kwargs):
            commands.append(command)
            server.bind(str(path))
            return SimpleNamespace()

        monkeypatch.setattr(cli.subprocess, "Popen", start)
        cli._ensure_ydotool_daemon()
        assert commands == [
            ["/usr/bin/ydotoold", "--socket-path", str(path), "--socket-perm", "0600"]
        ]
        cli._ensure_ydotool_daemon()
        assert len(commands) == 1, "An existing configured socket must be reused"

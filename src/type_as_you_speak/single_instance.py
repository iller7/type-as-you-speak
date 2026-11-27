# SPDX-FileCopyrightText: 2026 Faizal Sahebdin
# SPDX-License-Identifier: AGPL-3.0-only
"""Single-instance guard for the settings window.

The first ``tays gui`` binds a Unix socket in ``$XDG_RUNTIME_DIR`` and
stays the owner for the lifetime of the window. A later launch connects
to it, sends ``activate`` (the owner brings its window to the front), and
exits immediately — so repeated launches never pile up settings windows.

A socket left behind by a crashed instance is taken over: a refused
connect means there is no live owner. When ``$XDG_RUNTIME_DIR`` is
unavailable, or the socket cannot be used at all, the guard degrades to a
plain window instead of refusing to start. Stdlib only — no new
dependencies, no DBus.
"""

import os
import socket
from pathlib import Path

_SOCKET_NAME = "tays-gui.sock"
_CONNECT_TIMEOUT_S = 2.0

_server: socket.socket | None = None


def socket_path() -> Path | None:
    """Where the handshake socket lives, or None when single-instance
    cannot be used in this session (no ``$XDG_RUNTIME_DIR``)."""
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if not runtime_dir:
        return None
    return Path(runtime_dir) / _SOCKET_NAME


def acquire() -> bool:
    """Take the single-instance slot.

    Returns True when this process should open its window (it owns the
    slot, or the slot is unavailable here). Returns False when another
    settings window is already open — it has been asked to come to the
    front, and this process should exit.
    """
    global _server
    path = socket_path()
    if path is None:
        return True
    # Is a settings window already listening?
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(_CONNECT_TIMEOUT_S)
            client.connect(str(path))
            client.sendall(b"activate")
        return False
    except (FileNotFoundError, ConnectionRefusedError):
        # No live owner (missing, or stale from a crash): take over.
        path.unlink(missing_ok=True)
    except OSError:
        return True  # degrade: open a plain window

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server.bind(str(path))
        server.listen(2)
    except OSError:
        # Lost a bind race with another launcher: ask whoever owns it to
        # surface its window, and only fall back to a plain window if no
        # one answers.
        server.close()
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(_CONNECT_TIMEOUT_S)
                client.connect(str(path))
                client.sendall(b"activate")
            return False
        except OSError:
            return True
    _server = server
    return True


def release() -> None:
    """Give up the slot (called when the settings window exits)."""
    global _server
    if _server is not None:
        _server.close()
        _server = None
    path = socket_path()
    if path is not None:
        path.unlink(missing_ok=True)


def server_fd() -> int | None:
    """The listening socket's file descriptor (owner side), or None."""
    return _server.fileno() if _server is not None else None


def accept_once() -> bool:
    """Owner side: accept one pending ``activate`` request.

    Returns True when a request was received (the window should be shown
    and raised).
    """
    if _server is None:
        return False
    try:
        conn, _addr = _server.accept()
    except OSError:
        return False
    try:
        conn.recv(64)
    except OSError:
        pass
    conn.close()
    return True

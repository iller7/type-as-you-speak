# SPDX-FileCopyrightText: 2026 Faizal Sahebdin
# SPDX-License-Identifier: AGPL-3.0-only
"""Single-instance handshake for the settings window (pure sockets, no Qt)."""

import socket

import pytest

from type_as_you_speak import single_instance


@pytest.fixture(autouse=True)
def _isolated_runtime_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    single_instance.release()
    yield
    single_instance.release()


def test_acquired_owner_listens_at_xdg_runtime_dir():
    assert single_instance.acquire() is True
    path = single_instance.socket_path()
    assert path is not None and path.exists()
    assert single_instance.server_fd() is not None


def test_second_acquire_notifies_owner_and_refuses():
    assert single_instance.acquire() is True
    assert single_instance.acquire() is False


def test_activate_requests_are_delivered():
    assert single_instance.acquire() is True
    assert single_instance.acquire() is False
    assert single_instance.accept_once() is True
    # The owner keeps serving further launches.
    assert single_instance.acquire() is False
    assert single_instance.accept_once() is True


def test_stale_socket_is_taken_over():
    # A socket file with no listener behind it: a previous instance died.
    path = single_instance.socket_path()
    stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stale.bind(str(path))
    stale.close()
    assert single_instance.acquire() is True
    assert single_instance.socket_path().exists()
    assert single_instance.server_fd() is not None


def test_release_closes_and_removes_socket():
    assert single_instance.acquire() is True
    single_instance.release()
    assert single_instance.server_fd() is None
    assert not single_instance.socket_path().exists()


def test_without_xdg_runtime_dir_degrades_to_plain_window(monkeypatch):
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    assert single_instance.acquire() is True
    assert single_instance.socket_path() is None
    assert single_instance.server_fd() is None


def test_acquire_is_usable_again_after_release():
    assert single_instance.acquire() is True
    single_instance.release()
    assert single_instance.acquire() is True

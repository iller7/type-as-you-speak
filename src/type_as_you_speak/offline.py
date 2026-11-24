# SPDX-FileCopyrightText: 2026 Faizal Sahebdin
# SPDX-License-Identifier: AGPL-3.0-only
"""Irreversible, process-local Linux network restriction for dictation.

Local desktop IPC remains trusted. This is not a sandbox for hostile host
services, drivers or code that deliberately proxies through allowed Unix IPC.
"""

import ctypes
import ctypes.util
import errno
import os
from pathlib import Path
import socket
import stat
import sys

_active = False


class _Comparison(ctypes.Structure):
    _fields_ = [
        ("arg", ctypes.c_uint),
        ("op", ctypes.c_int),
        ("datum_a", ctypes.c_uint64),
        ("datum_b", ctypes.c_uint64),
    ]


def _library():
    name = ctypes.util.find_library("seccomp")
    if not name:
        raise RuntimeError(
            "install libseccomp2 (Debian/Ubuntu) or libseccomp (Fedora/Arch)"
        )
    library = ctypes.CDLL(name)
    signatures = {
        "seccomp_init": ([ctypes.c_uint32], ctypes.c_void_p),
        "seccomp_release": ([ctypes.c_void_p], None),
        "seccomp_attr_set": (
            [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32],
            ctypes.c_int,
        ),
        "seccomp_syscall_resolve_name": ([ctypes.c_char_p], ctypes.c_int),
        "seccomp_rule_add_array": (
            [
                ctypes.c_void_p,
                ctypes.c_uint32,
                ctypes.c_int,
                ctypes.c_uint,
                ctypes.POINTER(_Comparison),
            ],
            ctypes.c_int,
        ),
        "seccomp_load": ([ctypes.c_void_p], ctypes.c_int),
    }
    for function, (arguments, result) in signatures.items():
        getattr(library, function).argtypes = arguments
        getattr(library, function).restype = result
    return library


def _check(result, operation):
    if result != 0:
        raise RuntimeError(f"{operation} failed ({result})")


def _reject_inherited_network():
    # Inspect after TSYNC: existing threads can no longer open Internet sockets.
    for entry in Path("/proc/self/fd").iterdir():
        descriptor = int(entry.name)
        try:
            if "io_uring" in os.readlink(entry):
                raise RuntimeError("inherited io_uring descriptor is not allowed")
            if stat.S_ISSOCK(os.fstat(descriptor).st_mode):
                borrowed = socket.socket(fileno=descriptor)
                try:
                    family = borrowed.getsockopt(socket.SOL_SOCKET, socket.SO_DOMAIN)
                finally:
                    borrowed.detach()
                if family != socket.AF_UNIX:
                    raise RuntimeError("inherited network socket is not allowed")
        except OSError as error:
            if error.errno not in (errno.ENOENT, errno.EBADF):
                raise


def enforce() -> None:
    """Allow Unix IPC only; fail before sensitive IO if protection is unavailable.

    The filter covers existing threads and survives fork/exec. It cannot be
    removed; saved preference changes require a new dictation process.
    """
    global _active
    if _active:
        return
    if sys.platform != "linux":
        raise RuntimeError("strict offline process protection currently requires Linux")
    try:
        library = _library()
        context = library.seccomp_init(0x7FFF0000)  # SCMP_ACT_ALLOW
        if not context:
            raise RuntimeError("cannot allocate network filter")
        try:
            _check(library.seccomp_attr_set(context, 3, 1), "no-new-privileges")
            _check(library.seccomp_attr_set(context, 4, 1), "thread synchronization")
            deny = 0x00050000 | errno.EPERM  # SCMP_ACT_ERRNO(EPERM)
            comparison = _Comparison(0, 1, socket.AF_UNIX, 0)  # SCMP_CMP_NE
            for name in (
                b"socket",
                b"socketpair",
                b"io_uring_setup",
                b"io_uring_enter",
                b"io_uring_register",
            ):
                number = library.seccomp_syscall_resolve_name(name)
                if number == -1:
                    raise RuntimeError("libseccomp cannot resolve a required syscall")
                constrained = name in (b"socket", b"socketpair")
                _check(
                    library.seccomp_rule_add_array(
                        context,
                        deny,
                        number,
                        int(constrained),
                        ctypes.byref(comparison) if constrained else None,
                    ),
                    "network filter rule",
                )
            _check(library.seccomp_load(context), "network filter load")
        finally:
            library.seccomp_release(context)
        _reject_inherited_network()
    except (OSError, AttributeError, RuntimeError) as error:
        raise RuntimeError(f"Strict offline protection unavailable: {error}") from error
    _active = True


def active() -> bool:
    return _active

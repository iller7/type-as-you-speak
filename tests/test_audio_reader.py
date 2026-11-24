import threading
from types import SimpleNamespace

import numpy as np
import pytest

from type_as_you_speak import engine


def buffered_reader(samples):
    reader = engine.AudioReader.__new__(engine.AudioReader)
    reader._np = np
    reader._lock = threading.Lock()
    reader._buf = bytearray(np.asarray(samples, dtype=np.float32).tobytes())
    reader._thread = SimpleNamespace(is_alive=lambda: False)
    return reader


def test_eof_delivers_the_last_short_chunk_exactly_once():
    reader = buffered_reader([0.25, -0.5, 0.75])
    result = reader.read_chunk(timeout_s=0)
    assert result is not None, "A recording's final samples must reach the session"
    np.testing.assert_array_equal(result, [0.25, -0.5, 0.75])
    assert reader.read_chunk(timeout_s=0) is None


def test_eof_keeps_a_short_tail_after_a_full_chunk():
    samples = np.arange(engine.CHUNK_BYTES // 4 + 2, dtype=np.float32)
    reader = buffered_reader(samples)
    first = reader.read_chunk(timeout_s=0)
    last = reader.read_chunk(timeout_s=0)
    assert last is not None
    np.testing.assert_array_equal(np.concatenate([first, last]), samples)
    assert reader.read_chunk(timeout_s=0) is None


def test_truncated_float_frame_fails_instead_of_silently_dropping_audio():
    reader = buffered_reader([])
    reader._buf.extend(b"\x00\x01")
    with pytest.raises(ValueError, match="float32"):
        reader.read_chunk(timeout_s=0)


def test_empty_recording_ends_without_audio():
    assert buffered_reader([]).read_chunk(timeout_s=0) is None

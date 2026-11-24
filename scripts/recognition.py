# SPDX-License-Identifier: AGPL-3.0-only
"""Shared integrity and accuracy checks for the public recognition fixture."""

import hashlib
import json
from pathlib import Path
import re
import unicodedata


FIXTURES = Path(__file__).resolve().parents[1] / "tests/fixtures/audio"


def manifest():
    return json.loads((FIXTURES / "manifest.json").read_text())


def verify_files(directory, hashes):
    for name, expected in hashes.items():
        path = Path(directory) / name
        if not path.is_file():
            raise ValueError(f"missing recognition asset: {name}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"recognition asset checksum differs: {name}")


def normalized(text):
    text = unicodedata.normalize("NFKC", text).casefold().replace("’", "'")
    return re.findall(r"\w+(?:'\w+)*", text)


def edit_distance(reference, hypothesis):
    previous = list(range(len(hypothesis) + 1))
    for i, expected in enumerate(reference, 1):
        current = [i]
        for j, actual in enumerate(hypothesis, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[j] + 1,
                    previous[j - 1] + (expected != actual),
                )
            )
        previous = current
    return previous[-1]


def error_rates(reference, hypothesis):
    words = normalized(reference)
    if not words:
        raise ValueError("A nonempty reference is required; check silence separately")
    result = normalized(hypothesis)
    characters = " ".join(words)
    return (
        edit_distance(words, result) / len(words),
        edit_distance(characters, " ".join(result)) / len(characters),
    )

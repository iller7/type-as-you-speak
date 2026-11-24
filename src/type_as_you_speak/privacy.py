# SPDX-FileCopyrightText: 2026 Faizal Sahebdin
# SPDX-License-Identifier: AGPL-3.0-only
"""Apply telemetry opt-outs before inference dependencies initialize."""

import os
from pathlib import Path


def configure_environment() -> None:
    """Enforce app policy even when the parent environment enables telemetry.

    ONNX 1DS can initialize during import, before its Python opt-out is usable.
    Keep this function free of inference imports so CLI help stays lightweight.
    """
    os.environ["ORT_DISABLE_TELEMETRY"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["HF_XET_TELEMETRY_ENABLED"] = "0"
    os.environ["DO_NOT_TRACK"] = "1"


def disable_inference_telemetry() -> None:
    """Also disable ONNX events via its API before model/session construction.

    The API covers legacy Windows events as well as supported native providers.
    Errors propagate: inference must not silently proceed without the opt-out.
    """
    configure_environment()
    import onnxruntime

    onnxruntime.disable_telemetry_events()


def python_environment() -> dict:
    """Preserve the private native-package import path in Python children."""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(filter(None, (
        str(Path(__file__).resolve().parent.parent), environment.get("PYTHONPATH", ""))))
    return environment

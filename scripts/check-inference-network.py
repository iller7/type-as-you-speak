# SPDX-License-Identifier: AGPL-3.0-only
"""Linux native-network regression check using only public, pinned test assets."""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def trace_command(command, log, environment):
    try:
        result = subprocess.run(
            [
                "strace",
                "--kill-on-exit",
                "-f",
                "-qq",
                "-e",
                "trace=%network",
                "-e",
                "signal=none",
                "-e",
                "raw=all",
                "-o",
                str(log),
                *command,
            ],
            env=environment,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("network check timed out") from error
    if result.returncode != 0 or "strace:" in result.stderr:
        raise RuntimeError(
            "network probe or tracer failed; rerun the probe locally for diagnostics"
        )
    return log.read_text()


def check(model):
    environment = dict(os.environ)
    environment.update(
        ORT_DISABLE_TELEMETRY="0",
        HF_HUB_DISABLE_TELEMETRY="0",
        HF_XET_TELEMETRY_ENABLED="1",
        DO_NOT_TRACK="0",
        HF_HUB_OFFLINE="0",
        HF_HUB_DISABLE_IMPLICIT_TOKEN="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
    )
    with tempfile.TemporaryDirectory(prefix="tays-network-") as directory:
        work = Path(directory)
        environment["HF_HOME"] = str(work / "hub")
        control = trace_command(
            [sys.executable, str(__file__), "--control"], work / "control", environment
        )
        if control.count("socket(") < 2:
            raise RuntimeError(
                "network tracer positive control did not observe thread/child sockets"
            )
        trace = trace_command(
            [sys.executable, str(__file__), "--probe", "--model", str(model)],
            work / "probe",
            environment,
        )
        if trace.strip():
            raise RuntimeError(
                "network activity or invalid trace detected during inference"
            )
    print(
        "No network syscalls observed during strict local inference and 15 seconds idle."
    )


def control():
    import socket
    import threading

    def attempt():
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM):
            pass

    thread = threading.Thread(target=attempt)
    thread.start()
    thread.join()
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import socket; socket.socket(socket.AF_INET, socket.SOCK_DGRAM).close()",
        ],
        check=True,
    )


def probe(model):
    from type_as_you_speak import offline
    from type_as_you_speak.privacy import disable_inference_telemetry

    offline.enforce()
    disable_inference_telemetry()
    from huggingface_hub.utils import send_telemetry
    import pytest

    send_telemetry("type-as-you-speak/privacy-regression")
    # Keep pytest's user lookup/cache IO outside the inference network contract.
    with tempfile.TemporaryDirectory(prefix="tays-probe-") as directory:
        status = pytest.main(
            [
                "-q",
                "-p",
                "no:cacheprovider",
                "--basetemp",
                str(Path(directory) / "pytest"),
                "-m",
                "recognition",
                str(ROOT / "tests/test_recognition.py"),
                "--recognition-model",
                str(model),
            ]
        )
    if status:
        return int(status)
    time.sleep(15)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--control", action="store_true", help=argparse.SUPPRESS)
    mode.add_argument("--probe", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.control:
        control()
        return 0
    if not args.model:
        parser.error("--model must point to the explicitly prepared public test model")
    if args.probe:
        return probe(args.model.resolve())
    if sys.platform != "linux":
        parser.error("native-network tracing currently requires Linux and strace")
    try:
        check(args.model.resolve())
    except (OSError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit.py"


def load_audit():
    assert SCRIPT.is_file(), "An audit must inspect the actual packaged dependencies"
    spec = importlib.util.spec_from_file_location("audit", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def distribution(root, name, version):
    metadata = root / f"{name}-{version}.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n"
    )


def test_inventory_excludes_only_the_first_party_app(tmp_path):
    audit = load_audit()
    distribution(tmp_path, "type_as_you_speak", "0.5.1")
    distribution(tmp_path, "numpy", "2.5.5")
    distribution(tmp_path, "PySide6", "6.12.0")
    assert audit.requirements(tmp_path) == ["numpy==2.5.5", "pyside6==6.12.0"]


def test_empty_inventory_is_a_failure(tmp_path):
    with pytest.raises(ValueError, match="No third-party"):
        load_audit().requirements(tmp_path)


@pytest.mark.parametrize("exit_code", [0, 1, 2])
def test_audit_preserves_scanner_failures(tmp_path, monkeypatch, exit_code):
    audit = load_audit()
    distribution(tmp_path, "numpy", "2.5.5")
    commands = []

    def scan(command, **kwargs):
        commands.append(command)
        assert "numpy==2.5.5" in Path(command[command.index("-r") + 1]).read_text()
        return subprocess.CompletedProcess(command, exit_code)

    monkeypatch.setattr(audit.subprocess, "run", scan)
    assert audit.main([str(tmp_path)]) == exit_code
    assert commands[0][:3] == [sys.executable, "-m", "pip_audit"]
    assert {"--strict", "--no-deps", "--disable-pip"} <= set(commands[0])

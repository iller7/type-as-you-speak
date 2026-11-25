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


def test_native_provider_version_is_audited_with_the_bundle(tmp_path, monkeypatch):
    from types import SimpleNamespace

    audit = load_audit()
    distribution(tmp_path, "numpy", "2.5.5")
    monkeypatch.setattr(
        audit.importlib.metadata,
        "distribution",
        lambda name: SimpleNamespace(
            metadata={"Name": "onnxruntime"}, version="1.26.0"
        ),
    )
    assert audit.requirements(tmp_path, system_packages=["onnxruntime"]) == [
        "numpy==2.5.5",
        "onnxruntime==1.26.0",
    ]


def test_missing_native_provider_is_a_failure(tmp_path, monkeypatch):
    audit = load_audit()
    distribution(tmp_path, "numpy", "2.5.5")

    def missing(name):
        raise audit.importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(audit.importlib.metadata, "distribution", missing)
    with pytest.raises(ValueError, match="native.*onnxruntime"):
        audit.requirements(tmp_path, system_packages=["onnxruntime"])


def test_bundled_copy_cannot_shadow_a_declared_native_provider(tmp_path):
    audit = load_audit()
    distribution(tmp_path, "onnxruntime", "1.32.0")
    with pytest.raises(ValueError, match="Duplicate"):
        audit.requirements(tmp_path, system_packages=["onnxruntime"])


def test_native_dependency_closure_is_audited_without_resolving_extras(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    audit = load_audit()
    distribution(tmp_path, "numpy", "2.5.5")
    providers = {
        "onnxruntime": SimpleNamespace(
            version="1.26.0",
            requires=[
                "native-helper>=1",
                "numpy>=2",
                "not-installed; python_version < '1'",
            ],
        ),
        "native-helper": SimpleNamespace(version="1.2.0", requires=["onnxruntime>=1"]),
    }
    monkeypatch.setattr(
        audit.importlib.metadata, "distribution", lambda name: providers[name]
    )
    assert audit.requirements(tmp_path, system_packages=["onnxruntime"]) == [
        "native-helper==1.2.0",
        "numpy==2.5.5",
        "onnxruntime==1.26.0",
    ]


def test_cli_audits_native_provider_and_keeps_scanner_failure(tmp_path, monkeypatch):
    from types import SimpleNamespace

    audit = load_audit()
    distribution(tmp_path, "numpy", "2.5.5")
    monkeypatch.setattr(
        audit.importlib.metadata,
        "distribution",
        lambda name: SimpleNamespace(version="1.26.0", requires=[]),
    )

    def scan(command, **kwargs):
        requirements_file = Path(command[command.index("-r") + 1])
        assert requirements_file.read_text().splitlines() == [
            "numpy==2.5.5",
            "onnxruntime==1.26.0",
        ]
        return subprocess.CompletedProcess(command, 2)

    monkeypatch.setattr(audit.subprocess, "run", scan)
    assert audit.main([str(tmp_path), "--system-package", "onnxruntime"]) == 2


@pytest.mark.parametrize("report_format", ["json", "cyclonedx-json"])
def test_report_format_preserves_exact_inventory_and_audit_failure(
    tmp_path, monkeypatch, report_format
):
    audit = load_audit()
    distribution(tmp_path, "numpy", "2.5.5")
    report = tmp_path / "report.json"

    def scan(command, **kwargs):
        assert command[command.index("--format") + 1] == report_format
        assert command[command.index("--output") + 1] == str(report)
        assert {"--strict", "--no-deps", "--disable-pip"} <= set(command)
        assert Path(command[command.index("-r") + 1]).read_text() == "numpy==2.5.5\n"
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(audit.subprocess, "run", scan)
    assert (
        audit.main([str(tmp_path), "--format", report_format, "--output", str(report)])
        == 1
    )

import importlib.util
import shutil
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def release_module():
    path = ROOT / "scripts" / "check-release.py"
    assert path.exists(), "Release metadata needs a shared validator"
    spec = importlib.util.spec_from_file_location("release_check", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repository_versions_agree():
    assert release_module().check_versions(ROOT) == "0.5.1"


def test_wrong_tag_is_rejected():
    with pytest.raises(ValueError, match="tag"):
        release_module().check_versions(ROOT, "v9.9.9")


def test_packaging_version_drift_is_rejected(tmp_path):
    for name in ["pyproject.toml", "src", "packaging", "data", "CHANGELOG.md"]:
        source = ROOT / name
        target = tmp_path / name
        if source.is_dir():
            shutil.copytree(
                source, target, ignore=shutil.ignore_patterns("__pycache__")
            )
        else:
            shutil.copy(source, target)
    spec = tmp_path / "packaging/fedora/type-as-you-speak.spec"
    spec.write_text(
        spec.read_text().replace("Version:        0.5.1", "Version:        9.9.9")
    )
    with pytest.raises(ValueError, match="Fedora"):
        release_module().check_versions(tmp_path)

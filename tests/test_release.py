import importlib.util
import re
import tomllib
import shutil
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROJECT_VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"][
    "version"
]


def release_module():
    path = ROOT / "scripts" / "check-release.py"
    assert path.exists(), "Release metadata needs a shared validator"
    spec = importlib.util.spec_from_file_location("release_check", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repository_versions_agree():
    assert release_module().check_versions(ROOT) == PROJECT_VERSION


def test_wrong_tag_is_rejected():
    with pytest.raises(ValueError, match="tag"):
        release_module().check_versions(ROOT, f"v{PROJECT_VERSION}.invalid")


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
        re.sub(
            r"^Version:\s+\S+",
            f"Version: {PROJECT_VERSION}.invalid",
            spec.read_text(),
            flags=re.M,
        )
    )
    with pytest.raises(ValueError, match="Fedora"):
        release_module().check_versions(tmp_path)


def test_release_does_not_require_a_handwritten_changelog(monkeypatch):
    original = Path.read_text

    def read_text(path, *args, **kwargs):
        if path.name == "CHANGELOG.md":
            return "# Changelog\n\nSee the automatically generated GitHub releases.\n"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    assert release_module().check_versions(ROOT) == PROJECT_VERSION

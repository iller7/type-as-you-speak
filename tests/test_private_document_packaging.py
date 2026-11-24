"""Build a source archive with synthetic private notes present in the checkout."""

from pathlib import Path
import shutil
import subprocess
import sys
import tarfile


def test_source_build_excludes_private_notes(tmp_path):
    root = Path(__file__).resolve().parents[1]
    source = tmp_path / "source"
    source.mkdir()
    for name in (
        "pyproject.toml",
        "MANIFEST.in",
        "README.md",
        "LICENSE",
        "NOTICE",
        "COMMERCIAL.md",
    ):
        shutil.copyfile(root / name, source / name)
    for name in ("src", "docs"):
        shutil.copytree(
            root / name,
            source / name,
            ignore=shutil.ignore_patterns("__pycache__", "project-direction.md"),
        )
    marker = "SYNTHETIC-PRIVATE-NOTES-DO-NOT-PUBLISH"
    (source / "docs/project-direction.md").write_text(marker, encoding="utf-8")
    subprocess.run(
        [sys.executable, "-m", "build", "--sdist", "--no-isolation"],
        cwd=source,
        check=True,
        capture_output=True,
        text=True,
    )
    archive = next((source / "dist").glob("*.tar.gz"))
    with tarfile.open(archive) as package:
        files = [member for member in package.getmembers() if member.isfile()]
        assert any(member.name.endswith("/docs/licensing.md") for member in files)
        assert not any(
            member.name.endswith("/docs/project-direction.md") for member in files
        )
        assert all(
            marker.encode() not in package.extractfile(member).read()
            for member in files
        )

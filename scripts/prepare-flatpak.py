"""Generate offline Flatpak dependency sources from a target Linux wheelhouse."""

import argparse
import hashlib
import json
import shutil
import urllib.request
import zipfile
from email.parser import BytesParser
from pathlib import Path


def wheel_source(wheel: Path) -> dict:
    with zipfile.ZipFile(wheel) as archive:
        metadata_path = next(
            p for p in archive.namelist() if p.endswith(".dist-info/METADATA")
        )
        metadata = BytesParser().parsebytes(archive.read(metadata_path))
    url = f"https://pypi.org/pypi/{metadata['Name']}/{metadata['Version']}/json"
    with urllib.request.urlopen(url, timeout=30) as response:
        release = json.load(response)
    published = next(f for f in release["urls"] if f["filename"] == wheel.name)
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    if digest != published["digests"]["sha256"]:
        raise ValueError(f"Wheel does not match its published hash: {wheel.name}")
    return {"type": "file", "url": published["url"], "sha256": digest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheelhouse", type=Path)
    parser.add_argument("--output", type=Path, default=Path("dist/flatpak"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.output.exists():
        parser.error("Output already exists; remove it explicitly before regenerating")
    wheels = sorted(args.wheelhouse.glob("*.whl"))
    app = [p for p in wheels if p.name.startswith("type_as_you_speak-")]
    if len(app) != 1 or len(wheels) < 2:
        parser.error("Expected one application wheel and its Linux x86-64 dependencies")
    sources = [wheel_source(p) for p in wheels if p != app[0]]
    manifest = json.loads(
        (root / "packaging/flatpak/io.github.iller7.TypeAsYouSpeak.json").read_text()
    )
    dependency_module = {
        "name": "python-dependencies",
        "buildsystem": "simple",
        "build-commands": [
            "pip3 install --no-index --no-deps --prefix=/app --find-links=. *.whl"
        ],
        "sources": sources,
    }
    manifest["modules"].insert(-1, dependency_module)
    application = manifest["modules"][-1]
    application["sources"] = [{"type": "dir", "path": "source"}]
    application["build-commands"][0] = (
        "pip3 install --no-index --no-deps --prefix=/app type_as_you_speak-*.whl"
    )
    target = args.output / "source"
    target.mkdir(parents=True)
    shutil.copytree(root / "data", target / "data")
    for path in [
        root / "README.md",
        root / "LICENSE",
        root / "NOTICE",
        root / "COMMERCIAL.md",
        app[0],
    ]:
        shutil.copy(path, target / path.name)
    (args.output / "io.github.iller7.TypeAsYouSpeak.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    print(f"Prepared {len(sources)} hashed dependency sources in {args.output}")


if __name__ == "__main__":
    main()

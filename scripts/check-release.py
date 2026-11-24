"""Validate shared release metadata without importing the application or ML stack."""

import argparse
import ast
import json
import re
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path


def check_versions(root: Path, tag: str | None = None) -> str:
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    version = project["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError(
            "Only stable X.Y.Z versions are supported by this release workflow"
        )
    init = ast.parse((root / "src/type_as_you_speak/__init__.py").read_text())
    init_version = next(
        ast.literal_eval(n.value)
        for n in init.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "__version__" for t in n.targets)
    )
    spec = (root / "packaging/fedora/type-as-you-speak.spec").read_text()
    aur = (root / "packaging/aur/PKGBUILD").read_text()
    flatpak = json.loads(
        (root / "packaging/flatpak/io.github.iller7.TypeAsYouSpeak.json").read_text()
    )
    appstream = ET.parse(root / "data/type-as-you-speak.metainfo.xml")
    versions = {
        "__init__": init_version,
        "Fedora": re.search(r"^Version:\s+(\S+)", spec, re.M).group(1),
        "AUR": re.search(r"^pkgver=(\S+)", aur, re.M).group(1),
        "Flatpak": flatpak["modules"][-1]["sources"][0]["tag"].removeprefix("v"),
        "AppStream": appstream.find("releases/release").attrib["version"],
    }
    if tag is not None:
        versions["tag"] = (
            tag.removeprefix("v") if tag.startswith("v") else "invalid tag"
        )
    for name, value in versions.items():
        if value != version:
            raise ValueError(
                f"{name} version {value!r} does not match project version {version}"
            )
    if f"## [{version}]" not in (root / "CHANGELOG.md").read_text():
        raise ValueError(f"Missing CHANGELOG entry for {version}")
    return version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag")
    parser.add_argument("--notes", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        version = check_versions(root, args.tag)
    except (ValueError, AttributeError, StopIteration, KeyError) as exc:
        parser.error(str(exc))
    if args.notes:
        changelog = (root / "CHANGELOG.md").read_text()
        section = changelog.split(f"## [{version}]", 1)[1].split("\n## [", 1)[0]
        args.notes.write_text(f"## [{version}]" + section.rstrip() + "\n")
    print(f"Release metadata agrees: {version}")


if __name__ == "__main__":
    main()

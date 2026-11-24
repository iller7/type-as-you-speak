"""Check installable metadata and the files downstream packagers need."""

import tarfile
import zipfile
from pathlib import Path


def check_distributions(directory: Path) -> None:
    wheels = list(directory.glob("*.whl"))
    sources = list(directory.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1:
        raise ValueError("Expected one wheel and one source archive in dist/")
    with zipfile.ZipFile(wheels[0]) as wheel:
        entrypoints = next(
            n for n in wheel.namelist() if n.endswith(".dist-info/entry_points.txt")
        )
        if "tays = type_as_you_speak.cli:main" not in wheel.read(entrypoints).decode():
            raise ValueError("Wheel is missing the tays entry point")
        if "type_as_you_speak/gui.py" not in wheel.namelist():
            raise ValueError("Wheel is missing the settings window")
    required = {
        "install.sh",
        "uv.lock",
        "config/default.toml",
        "packaging/aur/PKGBUILD",
        "packaging/fedora/type-as-you-speak.spec",
        "packaging/deb/build-deb.sh",
        "data/type-as-you-speak.desktop",
        "data/type-as-you-speak.metainfo.xml",
        "data/icons/type-as-you-speak-512.png",
        "scripts/audit.py",
        "packaging/build-ydotool.sh",
        "packaging/containers/debian.Dockerfile",
    }
    with tarfile.open(sources[0]) as source:
        names = {name.split("/", 1)[1] for name in source.getnames() if "/" in name}
    if missing := required - names:
        raise ValueError(f"Source archive is missing: {', '.join(sorted(missing))}")


if __name__ == "__main__":
    check_distributions(Path("dist"))
    print("Wheel entry point and downstream source files verified")

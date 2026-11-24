"""Audit installed third-party versions without resolving a different dependency tree."""

import argparse
import importlib.metadata
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def requirements(directory: Path) -> list[str]:
    packages = {}
    for dist in importlib.metadata.distributions(path=[str(directory)]):
        name = re.sub(r"[-_.]+", "-", dist.metadata["Name"]).lower()
        if name == "type-as-you-speak":
            continue
        if name in packages:
            raise ValueError(f"Duplicate distribution: {name}")
        packages[name] = dist.version
    if not packages:
        raise ValueError("No third-party packages found; refusing an empty audit")
    return [f"{name}=={version}" for name, version in sorted(packages.items())]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "directory", type=Path, help="installed site-packages directory"
    )
    parser.add_argument("--output", type=Path, help="pip-audit JSON report")
    args = parser.parse_args(argv)
    try:
        inventory = requirements(args.directory)
    except (ValueError, KeyError) as exc:
        parser.error(str(exc))
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "requirements.txt"
        path.write_text("\n".join(inventory) + "\n")
        command = [
            sys.executable,
            "-m",
            "pip_audit",
            "--strict",
            "--no-deps",
            "--disable-pip",
            "--progress-spinner",
            "off",
            "-r",
            str(path),
        ]
        if args.output:
            command += ["--format", "json", "--output", str(args.output)]
        return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())

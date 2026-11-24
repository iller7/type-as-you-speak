"""Audit installed third-party versions without resolving a different dependency tree."""

from collections import deque
import argparse
import importlib.metadata
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from packaging.requirements import Requirement


def requirements(directory: Path, system_packages=()) -> list[str]:
    packages = {}
    for dist in importlib.metadata.distributions(path=[str(directory)]):
        name = re.sub(r"[-_.]+", "-", dist.metadata["Name"]).lower()
        if name == "type-as-you-speak":
            continue
        if name in packages:
            raise ValueError(f"Duplicate distribution: {name}")
        packages[name] = dist.version
    for name in system_packages:
        key = re.sub(r"[-_.]+", "-", name).lower()
        if key in packages:
            raise ValueError(f"Duplicate bundled/native distribution: {key}")
    pending = deque(system_packages)
    while pending:
        name = pending.popleft()
        key = re.sub(r"[-_.]+", "-", name).lower()
        if key in packages:
            continue
        try:
            dist = importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError as exc:
            raise ValueError(f"Missing native distribution: {name}") from exc
        packages[key] = dist.version
        for raw in getattr(dist, "requires", None) or []:
            requirement = Requirement(raw)
            if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
                pending.append(requirement.name)
    if not packages:
        raise ValueError("No third-party packages found; refusing an empty audit")
    return [f"{name}=={version}" for name, version in sorted(packages.items())]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "directory", type=Path, help="installed site-packages directory"
    )
    parser.add_argument("--output", type=Path, help="pip-audit JSON report")
    parser.add_argument(
        "--system-package",
        action="append",
        default=[],
        help="Also audit an explicitly declared native Python provider",
    )
    args = parser.parse_args(argv)
    try:
        inventory = requirements(args.directory, args.system_package)
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

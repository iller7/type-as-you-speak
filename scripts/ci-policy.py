"""Choose conservative PR validation and check required CI job outcomes."""

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess


ROOT_DOCUMENTS = {
    "README.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SUPPORT.md",
    "SECURITY.md",
    "TODO.md",
    "CHANGELOG.md",
}
DOCUMENT_SUFFIXES = {
    ".md",
    ".html",
    ".css",
    ".svg",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".yml",
    ".yaml",
}
REGULAR_MODES = {"100644", "000000"}


def documentation_only(changes: list[tuple[str, str, str]]) -> bool:
    if not changes:
        return False
    for old_mode, new_mode, name in changes:
        if old_mode not in REGULAR_MODES or new_mode not in REGULAR_MODES:
            return False
        if old_mode == new_mode == "000000":
            return False
        if any(ord(char) < 32 or ord(char) == 127 for char in name) or "\\" in name:
            return False
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or str(path) != name:
            return False
        if name in ROOT_DOCUMENTS:
            continue
        if (
            len(path.parts) > 1
            and path.parts[0] == "docs"
            and path.suffix in DOCUMENT_SUFFIXES
        ):
            continue
        return False
    return True


def parse_changes(raw: bytes) -> list[tuple[str, str, str]]:
    if not raw:
        return []
    if not raw.endswith(b"\0"):
        raise ValueError("Incomplete diff")
    tokens = raw[:-1].split(b"\0")
    if len(tokens) % 2:
        raise ValueError("Incomplete diff record")
    changes = []
    for offset in range(0, len(tokens), 2):
        fields = tokens[offset].split()
        if (
            len(fields) != 5
            or not re.fullmatch(rb":[0-7]{6}", fields[0])
            or not re.fullmatch(rb"[0-7]{6}", fields[1])
            or fields[4] not in {b"A", b"D", b"M", b"T"}
        ):
            raise ValueError("Unrecognized diff record")
        changes.append(
            (
                fields[0][1:].decode(),
                fields[1].decode(),
                tokens[offset + 1].decode("utf-8"),
            )
        )
    return changes


def full_validation(
    event: str, payload: dict | None, repository: Path | None = None
) -> bool:
    if event != "pull_request":
        return True
    try:
        base = payload["pull_request"]["base"]["sha"]
        head = payload["pull_request"]["head"]["sha"]
        if not all(
            isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha)
            for sha in (base, head)
        ):
            raise ValueError("Invalid commit identity")
        parents = (
            subprocess.check_output(
                ["git", "rev-list", "--parents", "-n", "1", "HEAD"],
                cwd=repository,
                timeout=20,
            )
            .decode()
            .split()
        )
        if len(parents) != 3 or parents[1:] != [base, head]:
            raise ValueError("Checkout does not match the event merge")
        raw = subprocess.check_output(
            [
                "git",
                "diff",
                "--raw",
                "--no-ext-diff",
                "--no-textconv",
                "--no-renames",
                "-z",
                "HEAD^1",
                "HEAD",
                "--",
            ],
            cwd=repository,
            timeout=20,
        )
        return not documentation_only(parse_changes(raw))
    except (KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError):
        print(
            "::warning::CI changes could not be classified; selecting full validation."
        )
        return True


def gate_passes(full: str, required: list[str], conditional: str) -> bool:
    if not required or any(result != "success" for result in required):
        return False
    expected = {"true": "success", "false": "skipped"}.get(full)
    return expected is not None and conditional == expected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("select")
    gate = commands.add_parser("gate")
    gate.add_argument("--full", choices=["true", "false"], required=True)
    gate.add_argument("--required", action="append", required=True)
    gate.add_argument("--conditional", required=True)
    args = parser.parse_args()
    if args.command == "gate":
        if not gate_passes(args.full, args.required, args.conditional):
            parser.exit(1, "CI jobs did not complete with the required outcomes.\n")
        return
    event = os.environ.get("GITHUB_EVENT_NAME", "")
    payload = None
    if event == "pull_request":
        try:
            payload = json.loads(
                Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8")
            )
        except (KeyError, OSError, ValueError):
            pass
    full = "true" if full_validation(event, payload) else "false"
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with Path(output).open("a", encoding="utf-8") as stream:
            stream.write(f"full={full}\n")
    print("Validation mode: " + ("full" if full == "true" else "documentation"))


if __name__ == "__main__":
    main()

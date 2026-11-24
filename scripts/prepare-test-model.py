# SPDX-License-Identifier: AGPL-3.0-only
"""Explicitly download and verify the pinned public CPU recognition-test model."""

import argparse
import os
from pathlib import Path

from recognition import manifest, verify_files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=os.environ.get("TAYS_TEST_MODEL_DIR"),
        required=not os.environ.get("TAYS_TEST_MODEL_DIR"),
    )
    args = parser.parse_args()
    from type_as_you_speak.privacy import configure_environment

    configure_environment()
    from huggingface_hub import hf_hub_download

    model = manifest()["model"]
    for name, checksum in model["files"].items():
        try:
            verify_files(args.output, {name: checksum})
            continue
        except ValueError:
            pass
        hf_hub_download(
            model["repo_id"],
            filename=name,
            revision=model["revision"],
            local_dir=args.output,
            token=False,
            force_download=(args.output / name).exists(),
        )
    verify_files(args.output, model["files"])
    print(f"Verified CPU test model {model['repo_id']} at {model['revision']}")


if __name__ == "__main__":
    main()

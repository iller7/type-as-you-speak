# SPDX-FileCopyrightText: 2026 Faizal Sahebdin
# SPDX-License-Identifier: AGPL-3.0-only
"""Enable `python -m type_as_you_speak …` — runs the same `tays` CLI."""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())

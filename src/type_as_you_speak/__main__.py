"""Enable `python -m type_as_you_speak …` — runs the same `tays` CLI."""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())

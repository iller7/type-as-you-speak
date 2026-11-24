#!/usr/bin/env bash
# Run with the target distro's Python; its native ABI determines wheel selection.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
OUT="${1:-dist/wheelhouse}"
if [ -e "$OUT" ]; then
  echo "Refusing to mix dependencies with an existing wheelhouse: $OUT" >&2
  exit 1
fi
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
uv export --locked --no-dev --extra gui --no-emit-project --output-file "$OUT/requirements.txt" >/dev/null
"$PY" -m pip download --only-binary=:all: --require-hashes -r "$OUT/requirements.txt" -d "$OUT"
uv run --locked python -m build --no-isolation --wheel --outdir "$OUT/app"
mv "$OUT"/app/*.whl "$OUT/"
rmdir "$OUT/app"

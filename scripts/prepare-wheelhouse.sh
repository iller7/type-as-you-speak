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
EXPORT_ARGS=()
if [ "${TAYS_NATIVE_ONNX:-0}" = 1 ]; then
  EXPORT_ARGS+=(--no-emit-package onnxruntime)
fi
uv export --locked --no-dev --extra gui --no-emit-project "${EXPORT_ARGS[@]}" --output-file "$OUT/requirements.txt" >/dev/null
# The lock export is complete; do not re-resolve a distro-supplied provider.
"$PY" -m pip download --no-deps --only-binary=:all: --require-hashes -r "$OUT/requirements.txt" -d "$OUT"
uv run --locked python -m build --no-isolation --wheel --outdir "$OUT/app"
mv "$OUT"/app/*.whl "$OUT/"
rmdir "$OUT/app"

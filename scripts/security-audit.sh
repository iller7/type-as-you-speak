#!/usr/bin/env bash
# Audit an installed bundle, or install one wheel into a temporary audit target.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
if [ -d "${1:-}" ]; then
  exec "$PY" scripts/audit.py "$@"
fi
shopt -s nullglob
wheels=(dist/*.whl)
if [ "${#wheels[@]}" -ne 1 ]; then
  echo 'Expected exactly one wheel in dist/; clean dist/ and run uv build --locked.' >&2
  exit 1
fi
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
uv export --locked --no-dev --extra gui --no-emit-project --output-file "$STAGE/requirements.txt" >/dev/null
"$PY" -m pip install --only-binary=:all: --require-hashes --target "$STAGE/site-packages" -r "$STAGE/requirements.txt"
"$PY" -m pip install --no-deps --target "$STAGE/site-packages" "${wheels[0]}"
"$PY" scripts/audit.py "$STAGE/site-packages"

#!/usr/bin/env bash
# Security audit for the release artifact.
#
# Installs the built wheel into a throwaway venv — i.e. the exact dependency
# tree that ships inside the .deb — then runs pip-audit over it.
#
# Exit codes:
#   0 — no vulnerabilities, or only low/moderate advisories (reported, not blocking)
#   1 — HIGH or CRITICAL vulnerability found (release/CI fails)
#
# If a low/moderate advisory is a false positive for this project, ignore it
# explicitly (reviewed, deliberate):
#   python -m pip_audit -i <VULN-ID> ...
set -euo pipefail
cd "$(dirname "$0")/.."

WHEEL="$(ls dist/*.whl 2>/dev/null | head -n1 || true)"
[ -n "$WHEEL" ] || { echo "::error::no wheel in dist/ — run 'python -m build' first"; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

python3 -m venv "$TMP/venv"
PY="$TMP/venv/bin/python"
"$PY" -m pip install -q --no-cache-dir --no-warn-script-location "$WHEEL"
"$PY" -m pip install -q --no-cache-dir pip-audit

REPORT="$TMP/report.json"
if "$PY" -m pip_audit -f json -o "$REPORT"; then
  echo "pip-audit: no known vulnerabilities in $(basename "$WHEEL")"
  exit 0
fi

# pip-audit exits non-zero when it finds vulnerabilities — gate on severity.
"$PY" - "$REPORT" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1]))
vulns = d.get("vulnerabilities", [])
print(json.dumps(vulns, indent=2))
bad = [v for v in vulns if v.get("severity") in ("HIGH", "CRITICAL")]
if bad:
    print(f"FAIL: {len(bad)} HIGH/CRITICAL vulnerability(ies) in the shipped dependency tree")
    sys.exit(1)
print(f"WARN: {len(vulns)} low/moderate advisory(ies) — not blocking; review the list above")
EOF

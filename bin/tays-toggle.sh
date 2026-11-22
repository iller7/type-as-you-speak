#!/usr/bin/env bash
# type-as-you-speak — Dictation-key toggle.
#
# One key press:
#   not running  -> start a live session (mutes output, types as you speak)
#   already going -> stop it (commits pending text, unmutes)
#
# It is written to work when launched by a background agent with a stripped
# environment (OpenLogi, a KDE "run command" shortcut, …): it restores a
# known-good PATH / runtime dir / Wayland display first, then hands off to the
# real logic in the `tays` CLI — so there is a single source of truth.
set -u

# ---- known-good environment --------------------------------------------------
export PATH="$HOME/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin${PATH:+:$PATH}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
if [ -z "${WAYLAND_DISPLAY:-}" ]; then
  for s in "$XDG_RUNTIME_DIR"/wayland-*; do
    [ -S "$s" ] && export WAYLAND_DISPLAY="${s##*/}" && break
  done
fi

# ---- locate the tays CLI -----------------------------------------------------
# 1) explicit override, 2) on PATH, 3) the default install.sh venv.
TAYS="${TAYS:-}"
if [ -z "$TAYS" ]; then
  TAYS="$(command -v tays 2>/dev/null || true)"
fi
if [ -z "$TAYS" ]; then
  TAYS="$HOME/.local/share/type-as-you-speak/venv/bin/tays"
fi

if [ ! -x "$TAYS" ]; then
  echo "type-as-you-speak: 'tays' not found (looked on PATH and in the venv)." >&2
  echo "  Run ./install.sh first, or set TAYS=/path/to/tays" >&2
  exit 1
fi

exec "$TAYS" toggle

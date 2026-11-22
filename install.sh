#!/usr/bin/env bash
# type-as-you-speak — installer
# -----------------------------
# Sets up everything you need to run `tays` on this machine:
#   1. checks the OS prerequisites (and prints the exact fix if one is missing)
#   2. creates a venv and installs the Python package (faster-whisper, …)
#   3. puts `tays` on your PATH (~/.local/bin/tays)
#   4. makes sure the ydotool daemon (a systemd *user* service) is running
#   5. writes a sample config and installs the Dictation-key toggle script
#
# It is idempotent — run it again any time to update to the latest code.
# It does NOT use sudo: OS packages are reported, not installed.
#
# Usage:
#   ./install.sh              # everything
#   ./install.sh --no-daemon  # skip enabling the ydotool daemon (I'll do it myself)
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_ROOT="${TAYS_HOME:-$HOME/.local/share/type-as-you-speak}"
VENV="$INSTALL_ROOT/venv"
BIN_DIR="$HOME/.local/bin"
BIN_LINK="$BIN_DIR/tays"
ENABLE_DAEMON=1
[ "${1:-}" = "--no-daemon" ] && ENABLE_DAEMON=0

say()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m  ok\033[0m  %s\n' "$*"; }
warn() { printf '\033[1;33m  !!\033[0m  %s\n' "$*"; }
fail() { printf '\033[1;31m  x\033[0m  %s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }

echo "type-as-you-speak — installer"
echo "  repo:        $SCRIPT_DIR"
echo "  install dir: $INSTALL_ROOT"
echo

# ---- 1. OS prerequisites ------------------------------------------------------
say "Checking system prerequisites"

# Python 3.11+ (needed for tomllib in the config reader)
PY="$(command -v python3.12 2>/dev/null || command -v python3.13 2>/dev/null || command -v python3.14 2>/dev/null || command -v python3 2>/dev/null || true)"
if [ -z "$PY" ]; then
  fail "python3 not found — install Python 3.11+ and re-run"
  exit 1
fi
PYVER="$("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo 0)"
PYNUM="$(echo "$PYVER" | awk -F. '{print $1*100+$2}')"
if [ "${PYNUM:-0}" -ge 311 ]; then ok "Python $PYVER ($PY)"; else
  fail "Python $PYVER is too old — need 3.11+"
  exit 1
fi

# CUDA GPU present? (decides whether we pull the NVIDIA runtime libraries)
HAVE_GPU=0
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then
  HAVE_GPU=1
  ok "NVIDIA GPU detected ($(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1))"
elif [ -d /proc/driver/nvidia ]; then
  HAVE_GPU=1
  ok "NVIDIA GPU driver present"
else
  say "no CUDA GPU detected — transcription will run on CPU (slower, works anywhere)"
fi

# A GUI session (Wayland or X11). ydotool types into the focused window on
# both; only the clipboard-fallback tool (checked below) differs.
RT="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
if [ -n "${WAYLAND_DISPLAY:-}" ] || ls "$RT"/wayland-* >/dev/null 2>&1 \
   || [ "${XDG_SESSION_TYPE:-}" = "wayland" ]; then
  ok "Wayland session detected"
  CLIP_EXE="wl-copy"; CLIP_PKG="wl-clipboard"
elif [ -n "${DISPLAY:-}" ] || [ "${XDG_SESSION_TYPE:-}" = "x11" ]; then
  ok "X11 session detected"
  CLIP_EXE="xclip"; CLIP_PKG="xclip"
else
  warn "no GUI session found (Wayland or X11) — this types into the focused window,"
  warn "so run it from inside your desktop session."
  CLIP_EXE="wl-copy"; CLIP_PKG="wl-clipboard"
fi

# Required commands
for exe in ffmpeg pactl; do
  if have "$exe"; then ok "$exe"
  else fail "$exe missing"; case "$exe" in
    ffmpeg) echo "         install:  apt install ffmpeg   |   dnf install ffmpeg";;
    pactl)  echo "         install:  apt install pipewire-pulse   |   pulseaudio";;
  esac; fi
done

YDOTOOL_MISSING=0
if have ydotool; then ok "ydotool"; else
  YDOTOOL_MISSING=1
  fail "ydotool missing — keystroke injection needs it."
  echo "         install:  apt install ydotool   |   dnf install ydotool"
fi
if have "$CLIP_EXE"; then ok "$CLIP_EXE (clipboard fallback)"
else warn "$CLIP_EXE missing — clipboard fallback won't work (apt install $CLIP_PKG)"; fi
if have notify-send; then ok "notify-send (notifications)"
else warn "notify-send missing — you just won't get notifications"; fi

# ---- 2. venv + package --------------------------------------------------------
say "Setting up the Python environment ($VENV)"
if [ ! -x "$VENV/bin/python" ]; then
  "$PY" -m venv "$VENV"
fi
# Install the package in EDITABLE mode: the venv holds only the dependencies,
# and `tays` runs the code straight from this repo (single source of truth).
# That means editing the repo — or just `git pull` — updates the tool
# immediately, with no code copy to drift out of sync.
"$VENV/bin/python" -m pip install --quiet --upgrade pip 2>/dev/null || true
"$VENV/bin/python" -m pip install --quiet -e "$SCRIPT_DIR" || {
  fail "failed to install the package into the venv"; exit 1; }
"$VENV/bin/tays" --version >/dev/null 2>&1 || {
  fail "the 'tays' command failed to run after install"; exit 1; }
ok "installed type-as-you-speak ($("$VENV/bin/tays" --version 2>/dev/null | sed 's/^.* //')), editable from $SCRIPT_DIR"

# GPU runtime: ctranslate2's CUDA build expects the NVIDIA cuBLAS / cuDART /
# nvRTC libraries, but faster-whisper does not declare them as dependencies —
# so a plain `pip install faster-whisper` gives a GPU build that can't run
# (missing libcublas.so.12). Install the runtime wheels only when a GPU is
# actually present (CPU-only machines skip ~1 GB of CUDA libraries).
if [ "$HAVE_GPU" -eq 1 ]; then
  say "Installing NVIDIA CUDA runtime libraries"
  if "$VENV/bin/python" -m pip install --quiet \
       "nvidia-cublas-cu12" "nvidia-cuda-runtime-cu12" "nvidia-cuda-nvrtc-cu12"; then
    ok "CUDA runtime libraries installed (GPU transcription enabled)"
  else
    warn "could not install the CUDA runtime wheels — GPU transcription may fail."
    warn "  See README > Troubleshooting, or run the install on a CUDA GPU box."
  fi
fi

# ---- 3. put `tays` on PATH ----------------------------------------------------
mkdir -p "$BIN_DIR"
if [ -e "$BIN_LINK" ] && [ "$BIN_LINK" -ef "$VENV/bin/tays" ]; then
  ok "`tays` already linked at $BIN_LINK"
else
  ln -sf "$VENV/bin/tays" "$BIN_LINK"
  ok "linked $BIN_LINK -> $VENV/bin/tays"
  case ":$PATH:" in
    *":$BIN_DIR:"*) : ;;
    *) warn "$BIN_DIR is not on your PATH — add it to your shell profile.";;
  esac
fi

# ---- 4. ydotool daemon (systemd user service) ---------------------------------
# ydotool injects keystrokes through a user-scoped daemon. This is the
# documented way it works, and it is a *user* service (not a system daemon).
if [ "$ENABLE_DAEMON" -eq 1 ]; then
  say "Ensuring the ydotool daemon is running (needed to inject keystrokes)"
  if pgrep -x ydotoold >/dev/null 2>&1; then
    ok "ydotoold is already running"
  elif [ "$YDOTOOL_MISSING" -eq 1 ]; then
    warn "skipped — install ydotool first (see above), then start its daemon."
  elif systemctl --user cat ydotoold >/dev/null 2>&1; then
    systemctl --user enable --now ydotoold >/dev/null 2>&1 || true
    if pgrep -x ydotoold >/dev/null 2>&1; then
      ok "ydotoold is running"
    else
      warn "ydotoold enabled but not running — run: systemctl --user start ydotoold"
    fi
  else
    # no daemon and no unit: create + start a standard user unit
    UNIT_DIR="$HOME/.config/systemd/user"
    mkdir -p "$UNIT_DIR"
    YDD="$(command -v ydotoold || echo /usr/bin/ydotoold)"
    cat > "$UNIT_DIR/ydotoold.service" <<EOF
[Unit]
Description=ydotool daemon (virtual input device)
After=graphical.target

[Service]
ExecStart=${YDD}
Restart=on-failure

[Install]
WantedBy=graphical.target
EOF
    systemctl --user daemon-reload
    systemctl --user enable --now ydotoold >/dev/null 2>&1 || true
    if pgrep -x ydotoold >/dev/null 2>&1; then
      ok "created + started ydotoold user service"
    else
      warn "could not start ydotoold — make sure your user is in the 'input' group:"
      echo "         sudo usermod -aG input \$USER     # then log out and back in"
      echo "         systemctl --user enable --now ydotoold"
    fi
  fi
fi

# ---- 5. config + keybind helper ----------------------------------------------
say "Installing config and keybind helper"
CFG_DIR="$HOME/.config/type-as-you-speak"
CFG_FILE="$CFG_DIR/config.toml"
if [ ! -f "$CFG_FILE" ] && [ -f "$SCRIPT_DIR/config/default.toml" ]; then
  mkdir -p "$CFG_DIR"
  cp "$SCRIPT_DIR/config/default.toml" "$CFG_FILE"
  ok "wrote sample config -> $CFG_FILE"
else
  ok "config present at $CFG_FILE (left untouched)"
fi

TOGGLE_SRC="$SCRIPT_DIR/bin/tays-toggle.sh"
TOGGLE_DST="$BIN_DIR/tays-toggle.sh"
if [ -f "$TOGGLE_SRC" ]; then
  cp "$TOGGLE_SRC" "$TOGGLE_DST"
  chmod +x "$TOGGLE_DST"
  ok "installed Dictation-key helper -> $TOGGLE_DST"
fi

# ---- done ---------------------------------------------------------------------
echo
say "Done. Try it now:"
echo
echo "    tays start        # run a live session (mutes output; Ctrl-C to stop)"
echo "    tays status       # is it running, on which model?"
echo "    tays setup        # re-check requirements + enable the daemon"
echo
echo "  Bind your Dictation key to run:   tays toggle"
echo "    OpenLogi: KeyDictation action -> run command: tays toggle"
echo "    KDE:     System Settings > Keyboard > Custom shortcut > 'tays toggle'"
echo
echo "  To update later: git pull  (it's an editable install, so new code applies immediately)"
echo "  Re-run ./install.sh only if you also want to refresh the dependencies."

"""The `tays` command-line interface.

Commands
  start   Run a live dictation session in the foreground (blocking). Mutes
          audio output first; unmutes when the session ends.
  stop    Stop the running session (it commits pending text, then exits).
  toggle  One-key behaviour — stop if running, else start a detached session.
          This is the command to bind to your Dictation key.
  status  Show whether a session is running, on which model/device, and the
          tail of the session log.
  setup   Check system requirements (GUI session, ydotool, deps), enable the
          ydotool daemon, and drop a sample config file for you to edit.

The session is always managed via a PID file in the XDG state dir
(~/.local/state/type-as-you-speak/live.pid), so start/stop/status are
consistent no matter how `tays` was launched.
"""
import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from . import __version__
from . import config as _config


# ---- locations ----------------------------------------------------------------
def _state_dir() -> Path:
    xdg = os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state"))
    d = Path(xdg) / "type-as-you-speak"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _pidfile() -> Path:
    return _state_dir() / "live.pid"


def _logfile() -> Path:
    return _state_dir() / "live.log"


# ---- environment (safe when launched from a trimmed agent) --------------------
def _prepare_env() -> None:
    """Restore a known-good runtime so ffmpeg (Pulse), ydotool and wl-copy all
    work even when we're started by a background agent with a stripped env."""
    os.environ.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    if not os.environ.get("WAYLAND_DISPLAY"):
        rt = os.environ.get("XDG_RUNTIME_DIR", "")
        for sock in sorted(Path(rt).glob("wayland-*")):
            if sock.is_socket():
                os.environ["WAYLAND_DISPLAY"] = sock.name
                break
    os.environ.setdefault(
        "YDOTOOL_SOCKET", f"{os.environ['XDG_RUNTIME_DIR']}/.ydotool_socket")
    _ensure_ydotool_daemon()


def _ensure_ydotool_daemon() -> None:
    """Make sure the ydotool daemon (ydotoold) is running — keystroke injection
    goes through it. Works without systemd: if it isn't running we start it
    detached. A no-op when the daemon is already up (e.g. the install.sh user
    service), and skipped entirely in dry-run mode (no typing happens then)."""
    if os.environ.get("DICTATE_DRY_RUN") == "1":
        return
    if not shutil.which("ydotool"):
        return  # typing unavailable anyway; nothing to start
    try:
        p = subprocess.run(["pgrep", "-x", "ydotoold"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=5)
        if p.returncode == 0:
            return
    except Exception:
        pass
    exe = shutil.which("ydotoold")
    if not exe:
        _log_line("ydotool present but ydotoold daemon not found — typing unavailable")
        return
    try:
        with open(_logfile(), "ab") as log:
            subprocess.Popen([exe], stdout=log, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, start_new_session=True)
        sock = Path(os.environ["XDG_RUNTIME_DIR"]) / ".ydotool_socket"
        for _ in range(50):
            if sock.exists():
                _log_line("started ydotoold daemon (detached)")
                return
            time.sleep(0.1)
        _log_line("started ydotoold; socket not up yet — will retry on next run")
    except Exception as e:
        _log_line(f"could not start ydotoold daemon: {e!r}")


def _log_line(msg: str) -> None:
    try:
        with open(_logfile(), "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}\n")
    except OSError:
        pass


# ---- audio output mute (while the mic is live, keep output silent) ------------
def _dry() -> bool:
    return os.environ.get("DICTATE_DRY_RUN") == "1"


def _mute(mute: bool) -> None:
    if mute and _dry():
        return  # dry-run: no side effects (don't mute the user's audio)
    try:
        subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@",
                        "1" if mute else "0"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=5)
    except Exception:
        pass


def _notify(summary: str, body: str) -> None:
    if _dry() or not shutil.which("notify-send"):
        return
    try:
        subprocess.run(["notify-send", "-a", "type-as-you-speak",
                        "-i", "audio-microphone", summary, body],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=5)
    except Exception:
        pass


# ---- session process management -----------------------------------------------
def _read_pid() -> int | None:
    try:
        return int(_pidfile().read_text().strip())
    except (OSError, ValueError):
        return None


def _alive(pid: int) -> bool:
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _is_running() -> tuple[bool, int | None]:
    pid = _read_pid()
    if _alive(pid):
        return True, pid
    if pid is not None:
        _remove_pid()  # stale
    return False, None


def _write_pid(pid: int) -> None:
    _state_dir()
    _pidfile().write_text(f"{pid}\n")


def _remove_pid() -> None:
    try:
        _pidfile().unlink()
    except OSError:
        pass


def _log_model_line() -> str:
    """Return the most recent 'model: …' line from the log (which model/device)."""
    try:
        with open(_logfile(), "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return "(no log yet)"
    for line in reversed(lines):
        if "model:" in line:
            return line.strip()
    return "(model line not found yet)"


def _log_tail(n: int = 6) -> list[str]:
    try:
        with open(_logfile(), "r", encoding="utf-8", errors="replace") as f:
            return [l.rstrip("\n") for l in f.readlines()][-n:]
    except OSError:
        return []


# ---- commands -----------------------------------------------------------------
def cmd_start(_args) -> int:
    _prepare_env()
    if getattr(_args, "model", None):
        # Per-run model override. Must be set BEFORE the engine is imported —
        # the engine reads its config (and DICTATE_MODEL) at import time.
        os.environ["DICTATE_MODEL"] = _args.model
    _write_pid(os.getpid())
    _log_line(f"START (foreground) pid={os.getpid()}")
    _mute(True)
    try:
        from . import engine
        return engine.main()
    finally:
        _remove_pid()
        _mute(False)  # engine already unmutes on exit; idempotent safety net


def cmd_stop(_args) -> int:
    running, pid = _is_running()
    if not running:
        print("type-as-you-speak: not running")
        _mute(False)
        return 0
    _log_line(f"STOP (manual) session_pid={pid}")
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    for _ in range(60):  # up to 6 s for it to commit pending text and exit
        if not _alive(pid):
            break
        time.sleep(0.1)
    if _alive(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    _remove_pid()
    _mute(False)
    _notify("Dictation", "Stopped — output un-muted.")
    print("type-as-you-speak: stopped")
    return 0


def cmd_toggle(_args) -> int:
    _prepare_env()
    running, _pid = _is_running()
    if running:
        return cmd_stop(_args)

    # Start a detached session so this keypress command returns immediately.
    env = dict(os.environ)
    if getattr(_args, "model", None):
        env["DICTATE_MODEL"] = _args.model   # the engine picks this up via DICTATE_MODEL
    try:
        out = open(_logfile(), "ab")
    except OSError as e:
        print(f"type-as-you-speak: cannot open log: {e}", file=sys.stderr)
        return 1
    try:
        child = subprocess.Popen(
            [sys.executable, "-m", "type_as_you_speak", "start"],
            stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            start_new_session=True,
            env=env,
        )
    except Exception as e:
        print(f"type-as-you-speak: failed to launch session: {e!r}",
              file=sys.stderr)
        return 1
    finally:
        out.close()

    time.sleep(1.2)
    if child.poll() is not None:
        _mute(False)  # it may have muted before dying; be safe
        print(f"type-as-you-speak: session failed to start "
              f"(exit {child.returncode}); see {_logfile()}", file=sys.stderr)
        return 1
    _log_line(f"START (detached) child_pid={child.pid}")
    _notify("Listening…",
            "Speak now — it types as you talk; press the key again to stop.")
    print("Listening… speak now — it types as you talk. Press the key again to stop.")
    return 0


def cmd_status(_args) -> int:
    running, pid = _is_running()
    if not running:
        print("type-as-you-speak: not running")
        return 1
    print(f"type-as-you-speak: running (pid {pid})")
    print(f"  {_log_model_line()}")
    tail = _log_tail()
    if tail:
        print("  recent log:")
        for line in tail:
            print(f"    {line}")
    return 0


def _session() -> str:
    """'wayland', 'x11', or 'none' — which display server we're in (if any).

    ydotool types into the focused window on both, so this only drives the
    clipboard-fallback tool (wl-copy vs xclip) and the wording of the check."""
    if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland":
        return "wayland"
    rt = os.environ.get("XDG_RUNTIME_DIR", "")
    if rt and any(p.is_socket() for p in Path(rt).glob("wayland-*")):
        return "wayland"
    if os.environ.get("DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "x11":
        return "x11"
    return "none"


def cmd_setup(_args) -> int:
    print(f"type-as-you-speak {__version__} — setup check\n")

    sess = _session()
    checks: list[tuple[str, bool, str]] = []
    checks.append(("GUI session (Wayland or X11)", sess != "none",
                   "run this inside a desktop session (Wayland or X11)"))
    for name, exe, hint in (
        ("ffmpeg", "ffmpeg", "apt install ffmpeg / dnf install ffmpeg"),
        ("PulseAudio (pactl)", "pactl", "pipewire-pulse or pulseaudio"),
        ("ydotool (key typing)", "ydotool", "apt install ydotool / dnf install ydotool"),
    ):
        path = shutil.which(exe)
        checks.append((name, bool(path), hint if not path else ""))
    # The clipboard-fallback tool depends on the desktop session.
    if sess == "wayland":
        clip_name, clip_exe, clip_hint = ("wl-copy (clipboard fallback)", "wl-copy",
                                          "apt install wl-clipboard")
    elif sess == "x11":
        clip_name, clip_exe, clip_hint = ("xclip (clipboard fallback)", "xclip",
                                          "apt install xclip")
    else:
        clip_name, clip_exe, clip_hint = ("clipboard (wl-copy or xclip)", "wl-copy",
                                          "wl-clipboard (Wayland) or xclip (X11)")
    clip_ok = bool(shutil.which(clip_exe)) or (sess == "none" and bool(shutil.which("xclip")))
    checks.append((clip_name, clip_ok, clip_hint if not clip_ok else ""))
    checks.append(("notify-send (desktop notifications)", bool(shutil.which("notify-send")),
                   "part of most desktops (libnotify)"))

    for label, ok, hint in checks:
        mark = "ok  " if ok else "MISS"
        line = f"  [{mark}] {label}"
        if hint:
            line += f"  —  {hint}"
        print(line)

    # GPU / model info (informational)
    print()
    model = _config.load_config()["model_name"]
    hub = Path(os.environ.get("HF_HOME",
                              os.path.expanduser("~/.cache/huggingface"))) / "hub"
    mdir = hub / f"models--Systran--faster-whisper-{model}"
    if mdir.exists():
        print(f"  [ok  ] Whisper model '{model}' is cached")
    else:
        print(f"  [--  ] Whisper model '{model}' not cached yet "
              f"(downloads ~1.5 GB on first run)")

    # ydotool daemon — required for key injection. It may be a systemd *user*
    # service or started by your compositor/login; all we need is that it's
    # RUNNING (and that we're in the 'input' group).
    print()
    daemon_running = False
    try:
        p = subprocess.run(["pgrep", "-x", "ydotoold"],
                           capture_output=True, text=True, timeout=5)
        daemon_running = (p.returncode == 0)
    except Exception:
        daemon_running = False
    in_input = False
    try:
        in_input = "input" in subprocess.run(
            ["id", "-nG"], capture_output=True, text=True,
            timeout=5).stdout.split()
    except Exception:
        in_input = False

    if daemon_running:
        print("  [ok  ] ydotool daemon (ydotoold) is running")
    else:
        print("  [MISS] ydotool daemon (ydotoold) is not running")
        print("         start it however your setup does (a systemd user service,")
        print("         a compositor autostart, …), or enable one:")
        print("           systemctl --user enable --now ydotoold")
    if not in_input:
        print("         also add yourself to the 'input' group: sudo usermod -aG input $USER")
        print("         (then log out and back in)")
    else:
        print("  [ok  ] user is in the 'input' group")

    # Drop a sample config file if the user doesn't have one yet
    ucfg = _config.user_config_path()
    if not ucfg.is_file():
        sample = Path(__file__).resolve().parents[2] / "config" / "default.toml"
        try:
            ucfg.parent.mkdir(parents=True, exist_ok=True)
            ucfg.write_text(sample.read_text() if sample.is_file()
                            else _sample_config_text())
            print(f"\n  [ok  ] wrote sample config -> {ucfg}\n"
                  f"          (edit it to change model, device, lag, phrases, …)")
        except OSError as e:
            print(f"\n  [--  ] could not write sample config: {e}")
    else:
        print(f"\n  [ok  ] config present -> {ucfg}")

    # Drop a starter hotwords file next to the config if the user has none
    hotwords_path = ucfg.parent / "hotwords.txt"
    if not hotwords_path.is_file():
        sample = Path(__file__).resolve().parents[2] / "config" / "hotwords.example.txt"
        if sample.is_file():
            try:
                hotwords_path.write_text(sample.read_text())
                print(f"  [ok  ] starter hotwords -> {hotwords_path}")
                print(f"          (enable it with `hotwords_file` in your config)")
            except OSError:
                pass
    elif hotwords_path.is_file():
        print(f"  [ok  ] hotwords file present -> {hotwords_path}")

    print("\nKeybind: bind your Dictation key to a *toggle* (press to start, press again to stop).")
    print("  Run `tays keybind` for copy-paste steps for your desktop (KDE/GNOME/Sway/…).")
    print(f"\nThen just try:  tays start   (or:  tays status)")
    return 0


def _sample_config_text() -> str:
    import textwrap
    lines = ["# type-as-you-speak — sample config", ""]
    for key, val in _config.DEFAULTS.items():
        if key == "hallucination_tails":
            lines.append("hallucination_tails = [")
            lines += [f"    {v!r}," for v in val]
            lines.append("]")
        else:
            lines.append(f"{key} = {val!r}")
    return "\n".join(lines) + "\n"


# ---- keybind helper -----------------------------------------------------------
_DE_ALIASES = {
    "kde":      ("kde", "plasma"),
    "gnome":    ("gnome",),
    "sway":     ("sway",),
    "hyprland": ("hyprland",),
    "xfce":     ("xfce",),
}


def _detect_de() -> str:
    """Best-guess desktop environment from the standard env vars."""
    raw = (os.environ.get("XDG_CURRENT_DESKTOP")
           or os.environ.get("DESKTOP_SESSION") or "").lower()
    raw = raw.replace("-", "").replace("_", "").replace(".", "")
    for de, names in _DE_ALIASES.items():
        if any(n in raw for n in names):
            return de
    return "generic"


def _toggle_command() -> str:
    """The single command to bind to a key. Prefer the env-safe wrappers your
    setup already provides, else fall back to the CLI."""
    home = os.path.expanduser("~")
    for cand in (f"{home}/.local/bin/dictate.sh", f"{home}/.local/bin/tays-toggle.sh"):
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return "tays toggle"


_KEYBIND_STEPS = {
    "kde": (
        "1. System Settings → **Keyboard** → **Global Shortcuts** → **Custom Shortcuts**.\n"
        "2. **Add New…** → **Global/Window Shortcut** (name it “Dictation”).\n"
        "3. **Shortcut** tab → *Record Shortcut* → press your key or combo (e.g. `Ctrl+M`,\n"
        "   or a single key). It's a *run-command* binding, so it won't type into your window.\n"
        "4. **Action** tab → **Run command/URL** → paste:\n\n"
        "         {cmd}\n\n"
        "5. OK / Apply. Done — one press starts, the next stops."
    ),
    "gnome": (
        "GNOME has no built-in “run command” shortcut — install the **Custom Shortcut**\n"
        "extension (GNOME Extensions site), then add:\n"
        "  • Command:  {cmd}\n"
        "  • Shortcut: your key/combo (e.g. `Ctrl+M`)\n"
        "It's a run-command binding, so nothing gets typed into your window."
    ),
    "sway": (
        "In your Sway config (usually `~/.config/sway/config`), add:\n\n"
        "         bindsym ctrl+m exec {cmd}\n\n"
        "then reload with `swmsg -reload`."
    ),
    "hyprland": (
        "In your Hyprland config (`~/.config/hypr/hyprland.conf`), add:\n\n"
        "         bind = CTRL + M, exec, {cmd}\n\n"
        "then `hyprctl reload`."
    ),
    "xfce": (
        "In **Settings → Keyboard → Application Shortcuts**, click **Add**, press your\n"
        "key/combo, and set the command to:\n\n"
        "         {cmd}\n\n"
        "OK. One press starts, the next stops."
    ),
    "generic": (
        "Any environment that can run a command on a key press — bind this command to\n"
        "your Dictation key:\n\n"
        "         {cmd}\n\n"
        "Examples: **OpenLogi** (Logi devices) → set the key's action to *Run Shell\n"
        "Command* with the above; your compositor's global hotkey; or a global-hotkey\n"
        "tool. It's a run-command binding, so it won't type into your window. Press\n"
        "once to start, again to stop."
    ),
}


def cmd_keybind(args) -> int:
    de = (args.de or _detect_de()).lower()
    if de not in _KEYBIND_STEPS:
        de = "generic"
    cmd = _toggle_command()
    print("Bind this command to your Dictation key (a *toggle*: press to start,")
    print("press again to stop):\n")
    print(f"    {cmd}\n")
    print(f"### {de.upper()} ###\n")
    print(_KEYBIND_STEPS[de].format(cmd=cmd))
    print("\n(Use `tays keybind --de <kde|gnome|sway|hyprland|xfce|generic>` to target a specific one.)")
    return 0


# ---- models listing ------------------------------------------------------------
_MODELS = [
    ("tiny.en",        "75 MB",  "fastest, weakest — quick drafts or very low power"),
    ("base.en",        "145 MB", "light and fast, noticeably rougher accuracy"),
    ("small.en",       "484 MB", "good everyday balance — the default for most people"),
    ("medium.en",      "1.5 GB", "very good accuracy; best quality-per-size for English"),
    ("large-v3-turbo", "1.6 GB", "top-tier accuracy and still fast; needs more VRAM"),
    ("large-v3",       "3 GB",   "highest accuracy, slowest and heaviest"),
]


def cmd_models(_args) -> int:
    cur = _config.load_config()["model_name"]
    print(f"Current model: {cur}\n")
    print(f"  {'MODEL':16} {'SIZE':>8}   notes")
    print("  " + "-" * 60)
    for name, size, note in _MODELS:
        mark = "   * (current)" if name == cur else ""
        print(f"  {name:16} {size:>8}   {note}{mark}")
    print("\n  Change it:")
    print('    per run:     tays start --model <name>')
    print('    permanently: model_name = "<name>"   in   ~/.config/type-as-you-speak/config.toml')
    print("  (The .en models are English-only: fastest and most accurate for English.)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tays",
        description="type-as-you-speak — Mac-like type-as-you-speak dictation "
                    "for Linux (Wayland & X11).",
    )
    p.add_argument("--version", action="version",
                   version=f"type-as-you-speak {__version__}")
    sub = p.add_subparsers(dest="cmd")
    st = sub.add_parser("start", help="run a live session in the foreground")
    st.add_argument("--model", default=None, metavar="NAME",
                    help="model for this run (e.g. small.en, medium.en) — overrides your config")
    st.set_defaults(func=cmd_start)
    sub.add_parser("stop", help="stop the running session").set_defaults(func=cmd_stop)
    tg = sub.add_parser("toggle", help="stop if running, else start (bind to a key)")
    tg.add_argument("--model", default=None, metavar="NAME",
                    help="model for the session you start (ignored when stopping)")
    tg.set_defaults(func=cmd_toggle)
    sub.add_parser("status", help="show session state and the model in use").set_defaults(func=cmd_status)
    sub.add_parser("setup", help="check requirements, enable ydotool, write sample config").set_defaults(func=cmd_setup)
    sub.add_parser("models", help="list the available Whisper models and sizes").set_defaults(func=cmd_models)
    kb = sub.add_parser("keybind", help="print the steps to bind a Dictation key for your desktop")
    kb.add_argument("--de", default=None, metavar="DE",
                    help="target desktop: kde|gnome|sway|hyprland|xfce|generic (default: auto-detect)")
    kb.set_defaults(func=cmd_keybind)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not getattr(args, "func", None):
        build_parser().print_help()
        return 0
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())

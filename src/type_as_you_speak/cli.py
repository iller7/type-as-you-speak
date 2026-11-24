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
import json
import os
import re
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
    d.mkdir(mode=0o700, parents=True, exist_ok=True)
    d.chmod(0o700)
    return d


def _pidfile() -> Path:
    return _state_dir() / "live.pid"


def _logfile() -> Path:
    path = _state_dir() / "live.log"
    path.touch(mode=0o600, exist_ok=True)
    path.chmod(0o600)
    return path


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


# ---- audio output ducking (keep background audible but quiet while mic is live)
def _dry() -> bool:
    return os.environ.get("DICTATE_DRY_RUN") == "1"


def _mute(mute: bool) -> None:
    """Legacy hard mute — only used when duck_volume_pct = 0."""
    if mute and _dry():
        return  # dry-run: no side effects (don't touch the user's audio)
    try:
        subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@",
                        "1" if mute else "0"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=5)
    except Exception:
        pass


def _duck_state_file() -> Path:
    return _state_dir() / "duck.json"


def _read_duck_state() -> dict | None:
    try:
        return json.loads(_duck_state_file().read_text())
    except (OSError, ValueError):
        return None


def _write_duck_state(st: dict) -> None:
    try:
        _state_dir().mkdir(parents=True, exist_ok=True)
        _duck_state_file().write_text(json.dumps(st))
    except OSError:
        pass


def _clear_duck_state() -> None:
    try:
        _duck_state_file().unlink()
    except OSError:
        pass


def _sink_volume_pct() -> int | None:
    try:
        out = subprocess.run(["pactl", "get-sink-volume", "@DEFAULT_SINK@"],
                             capture_output=True, text=True, timeout=5).stdout
        m = re.search(r"(\d+)%", out)
        return int(m.group(1)) if m else None
    except Exception:
        return None


def _sink_muted() -> bool:
    try:
        out = subprocess.run(["pactl", "get-sink-mute", "@DEFAULT_SINK@"],
                             capture_output=True, text=True, timeout=5).stdout
        return "yes" in out
    except Exception:
        return False


def _sink_set_volume(pct: int) -> None:
    try:
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{pct}%"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=5)
    except Exception:
        pass


def _ramp_volume(target_pct: int, ramp_ms: int) -> None:
    """Step the default sink's volume toward the target — a perceptually
    smooth fade rather than a jump (pactl has no native fade)."""
    cur = _sink_volume_pct()
    if cur is None or abs(cur - target_pct) < 1:
        return
    steps = max(2, min(12, int(ramp_ms) // 40))
    per = max(int(ramp_ms) / steps / 1000.0, 0.01)
    for i in range(1, steps + 1):
        _sink_set_volume(round(cur + (target_pct - cur) * i / steps))
        time.sleep(per)


def _duck_cfg() -> tuple[int, int]:
    cfg = _config.load_config()
    return (int(cfg.get("duck_volume_pct", 5)),
            int(cfg.get("duck_ramp_ms", 400)))


def _duck_on(pid: int) -> None:
    """Lower background audio for the duration of a session (ducking).
    duck_volume_pct = 0 keeps the legacy hard-mute behaviour. The previous
    volume is saved (state file, before the ramp) so a hard-killed session
    can still be undone — see _duck_restore_stale."""
    if _dry():
        return  # dry-run: no side effects on the user's audio
    st = _read_duck_state()
    if st and st.get("pid") and st["pid"] != pid and _alive(st["pid"]):
        return  # another live session already owns the duck state
    target, ramp = _duck_cfg()
    if target <= 0:
        _mute(True)
        _write_duck_state({"legacy_mute": True, "pid": pid})
        return
    if _sink_muted():
        return  # already silent — nothing to duck, nothing to restore
    cur = _sink_volume_pct()
    if cur is None or cur <= target:
        return  # no sink, or already quieter than the duck level
    _write_duck_state({"volume_pct": cur, "pid": pid})
    _ramp_volume(target, ramp)
    _log_line(f"ducked output to {target}% (was {cur}%)")


def _restore_duck(st: dict) -> None:
    if st.get("legacy_mute"):
        _mute(False)
    else:
        _, ramp = _duck_cfg()
        _ramp_volume(int(st["volume_pct"]), ramp)
    _clear_duck_state()


def _duck_off() -> None:
    """Restore background audio after a session ends (no-op if nothing ducked)."""
    if _dry():
        return
    st = _read_duck_state()
    if st is None:
        return
    pid = st.get("pid")
    if pid is not None and pid != os.getpid() and _alive(pid):
        return  # a live session still owns the duck state
    _restore_duck(st)
    _log_line("output volume restored")


def _duck_restore_stale() -> None:
    """A hard-killed session can leave the output ducked. On the next start,
    if the state file points at a dead session, restore the volume first."""
    if _dry():
        return
    st = _read_duck_state()
    if st is None:
        return
    pid = st.get("pid")
    if pid is not None and _alive(pid):
        return  # a live session owns it
    _log_line("restoring ducked volume left by a dead session")
    _restore_duck(st)


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
    try:
        (_state_dir() / "live.json").unlink()
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
def _gpu_name() -> str | None:
    """Human-readable GPU name, if a driver exposes one (NVIDIA first, then
    AMD via lspci) — for the descriptive status line."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5).stdout.strip().splitlines()
        if out and out[0].strip():
            return out[0].strip()
    except Exception:
        pass
    try:
        out = subprocess.run(["lspci"], capture_output=True, text=True, timeout=5).stdout
        for line in out.splitlines():
            if re.search(r"VGA|3D controller|Display controller", line) \
                    and re.search(r"AMD|ATI", line):
                return line.split(":", 2)[-1].strip()
    except Exception:
        pass
    return None


def _cpu_name() -> str | None:
    """Human-readable CPU name (e.g. 'AMD Ryzen 9 9950X') — for the
    descriptive status line when the session runs on the CPU, mirroring
    _gpu_name() on the GPU side."""
    try:
        with open("/proc/cpuinfo", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.lower().startswith("model name"):
                    name = line.split(":", 1)[1].strip()
                    if name:
                        return name
    except OSError:
        pass
    try:
        out = subprocess.run(["lscpu"], capture_output=True, text=True,
                             timeout=5).stdout
        for line in out.splitlines():
            if line.lower().startswith("model name"):
                name = line.split(":", 1)[1].strip()
                if name:
                    return name
    except Exception:
        pass
    return None


def _read_live_state(pid: int | None) -> dict | None:
    """What the running session actually loaded (model/device) — engine.py
    writes it; only trusted when its pid matches the live one."""
    try:
        st = json.loads((_state_dir() / "live.json").read_text())
        if st.get("pid") == pid:
            return st
    except (OSError, ValueError):
        pass
    return None


def _status_dict() -> dict:
    """Machine-readable session state — the contract GUIs and desktop
    applets consume (via `tays status --json`)."""
    running, pid = _is_running()
    cfg = _config.load_config()
    st = {
        "app": "type-as-you-speak",
        "version": __version__,
        "running": running,
        "pid": pid if running else None,
        "state": "listening" if running else "stopped",
        "model": cfg["model_name"],
        "device": cfg["device"],
    }
    if running:
        live = _read_live_state(pid)
        if live:
            if live.get("model"):
                st["model"] = live["model"]
            if live.get("device"):
                st["device"] = live["device"]
            if st["device"] in ("cuda", "rocm"):
                gpu = _gpu_name()
                if gpu:
                    st["gpu"] = gpu
    cpu = _cpu_name()
    if cpu:
        st["cpu"] = cpu
    return st


def cmd_start(_args) -> int:
    _prepare_env()
    running, running_pid = _is_running()
    if running:
        # Single-instance: a second engine would listen to the same mic and
        # both would type into the focused window — everything typed twice.
        # (Observed: two sessions interleaved in live.log, phrases stamped
        # 2-3x each.) The correct action is 'tays stop' or 'tays toggle'.
        if getattr(_args, "json", False):
            print(json.dumps(_status_dict()))
        else:
            print(f"type-as-you-speak: already running (pid {running_pid}) "
                  f"— use 'tays stop' first")
        return 0
    if getattr(_args, "model", None):
        # Per-run model override. Must be set BEFORE the engine is imported —
        # the engine reads its config (and DICTATE_MODEL) at import time.
        os.environ["DICTATE_MODEL"] = _args.model
    _write_pid(os.getpid())
    _log_line(f"START (foreground) pid={os.getpid()}")
    _duck_restore_stale()   # a hard-killed session may have left output ducked
    _duck_on(os.getpid())
    try:
        from . import engine
        return engine.main()
    finally:
        _remove_pid()
        _duck_off()  # engine already restores on exit; idempotent safety net


def cmd_stop(_args) -> int:
    as_json = getattr(_args, "json", False)
    running, pid = _is_running()
    if not running:
        _duck_off()
        if as_json:
            print(json.dumps(_status_dict()))
        else:
            print("type-as-you-speak: not running")
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
    _duck_off()
    if as_json:
        print(json.dumps(_status_dict()))
        return 0
    _notify("Dictation", "Stopped — output volume restored.")
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
        _duck_off()  # it may have ducked before dying; be safe
        print(f"type-as-you-speak: session failed to start "
              f"(exit {child.returncode}); see {_logfile()}", file=sys.stderr)
        if getattr(_args, "json", False):
            print(json.dumps(_status_dict()))
        return 1
    _log_line(f"START (detached) child_pid={child.pid}")
    if getattr(_args, "json", False):
        print(json.dumps(_status_dict()))
        return 0
    _notify("Listening…",
            "Speak now — it types as you talk; press the key again to stop.")
    print("Listening… speak now — it types as you talk. Press the key again to stop.")
    return 0


def cmd_status(_args) -> int:
    as_json = getattr(_args, "json", False)
    if as_json:
        # Machine contract: stdout is JSON only; exit 0 regardless of state
        # (consumers key off the "running" field, not the exit code).
        print(json.dumps(_status_dict()))
        return 0
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
        print("         check /dev/uinput permissions and the distro ydotool service.")
        print("         Prefer a narrowly scoped udev rule; see SECURITY.md before granting input access.")
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


def cmd_gui(_args) -> int:
    """Open the settings window. The GUI is an optional extra so the core
    stays lean — if its dependencies are missing, say so and point at the fix.

    ``--detach`` (used by the Plasma applet) launches the window in its own
    session and returns immediately, so the caller isn't held open for the
    lifetime of the window."""
    if getattr(_args, "detach", False):
        try:
            out = open(_state_dir() / "gui.log", "ab")
            subprocess.Popen(
                [sys.executable, "-m", "type_as_you_speak", "gui"],
                stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                start_new_session=True)
            return 0
        except Exception as e:
            print(f"type-as-you-speak: failed to launch GUI: {e!r}",
                  file=sys.stderr)
            return 1
    try:
        from . import gui
    except ImportError as e:
        missing = e.name or "PySide6"
        print("The settings GUI needs the 'gui' extra "
              f"(missing: {missing}).", file=sys.stderr)
        print("Install it with:  pip install 'type-as-you-speak[gui]'",
              file=sys.stderr)
        print("Or edit the config directly: "
              f"{_config.user_config_path()}", file=sys.stderr)
        return 1
    return gui.main()


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
    sp = sub.add_parser("stop", help="stop the running session")
    sp.add_argument("--json", action="store_true",
                    help="print machine-readable JSON status on stdout")
    sp.set_defaults(func=cmd_stop)
    tg = sub.add_parser("toggle", help="stop if running, else start (bind to a key)")
    tg.add_argument("--model", default=None, metavar="NAME",
                    help="model for the session you start (ignored when stopping)")
    tg.add_argument("--json", action="store_true",
                    help="print machine-readable JSON status on stdout")
    tg.set_defaults(func=cmd_toggle)
    spst = sub.add_parser("status", help="show session state and the model in use")
    spst.add_argument("--json", action="store_true",
                      help="print machine-readable JSON status on stdout")
    spst.set_defaults(func=cmd_status)
    sub.add_parser("setup", help="check requirements, enable ydotool, write sample config").set_defaults(func=cmd_setup)
    sub.add_parser("models", help="list the available Whisper models and sizes").set_defaults(func=cmd_models)
    gp = sub.add_parser("gui", help="open the settings window (optional 'gui' extra)")
    gp.add_argument("--detach", action="store_true",
                    help="launch the window in its own session and return immediately (used by the panel applet)")
    gp.set_defaults(func=cmd_gui)
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
    if sys.platform != "linux" and args.cmd in {"start", "stop", "toggle", "status", "setup", "keybind"}:
        print("Desktop integration currently requires Linux. macOS and Windows are not supported yet.", file=sys.stderr)
        return 2
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())

"""Optional settings GUI — ``tays gui``.

A single window to pick the model and every other option instead of editing
config.toml by hand:

  * session panel — live status (polled from ``tays status --json``, showing
    the EXACT runtime device, e.g. "small.en on NVIDIA GeForce RTX 5090
    (CUDA)") and a start/stop button (drives ``tays toggle`` as a subprocess,
    so the engine always runs in its own process, exactly like the CLI);
  * General tab — Model & device (with downloaded marks + Download button,
    Auto / GPU-CUDA / GPU-ROCm(AMD) / CPU radios), Background audio ducking,
    Corrections (hotwords inline + file, hallucination tails);
  * Advanced tab — Typing & pacing, Decode stability.

Every field carries a hover tooltip AND a context-help line in the window's
status bar (shown as you hover — robust across desktops). Saving writes
``~/.config/type-as-you-speak/config.toml`` with ``tomlkit`` in a way that
preserves the file's existing comments and layout. Requires the optional
``gui`` extra (PySide6 + tomlkit); the core stays lean.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QEvent, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QIcon, Qt
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPushButton, QPlainTextEdit, QRadioButton,
    QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

import tomlkit

from . import __version__
from . import cli
from .config import load_config, user_config_path

# Spin-box ranges (key -> (min, max, single-step)).
_SPIN_INT = {
    "cpu_threads": (1, 32, 1),
    "type_ms": (1, 50, 1),
    "duck_volume_pct": (0, 100, 1),
    "duck_ramp_ms": (0, 5000, 50),
    "no_repeat_ngram_size": (0, 5, 1),
}
_SPIN_FLOAT = {
    "commit_lag_s": (0.1, 5.0, 0.1),
    "transcribe_every_s": (0.3, 3.0, 0.1),
}

# Language picker entries: (code stored in config, native name, flag).
LANGUAGES = [
    ("auto", "Auto-detect", "🌐"),
    ("en", "English", "🇬🇧"),
    ("de", "Deutsch", "🇩🇪"),
    ("fr", "Français", "🇫🇷"),
    ("es", "Español", "🇪🇸"),
    ("it", "Italiano", "🇮🇹"),
    ("pt", "Português", "🇵🇹"),
    ("nl", "Nederlands", "🇳🇱"),
    ("pl", "Polski", "🇵🇱"),
    ("ru", "Русский", "🇷🇺"),
    ("uk", "Українська", "🇺🇦"),
    ("zh", "中文", "🇨🇳"),
    ("ja", "日本語", "🇯🇵"),
    ("ko", "한국어", "🇰🇷"),
    ("hi", "हिन्दी", "🇮🇳"),
    ("ar", "العربية", "🇸🇦"),
    ("tr", "Türkçe", "🇹🇷"),
    ("sv", "Svenska", "🇸🇪"),
    ("da", "Dansk", "🇩🇰"),
    ("no", "Norsk", "🇳🇴"),
    ("fi", "Suomi", "🇫🇮"),
    ("cs", "Čeština", "🇨🇿"),
    ("hu", "Magyar", "🇭🇺"),
    ("ro", "Română", "🇷🇴"),
    ("el", "Ελληνικά", "🇬🇷"),
    ("he", "עברית", "🇮🇱"),
    ("vi", "Tiếng Việt", "🇻🇳"),
    ("th", "ไทย", "🇹🇭"),
    ("id", "Bahasa Indonesia", "🇮🇩"),
    ("ms", "Bahasa Melayu", "🇲🇾"),
    ("tl", "Filipino", "🇵🇭"),
    ("ca", "Català", "🇦🇩"),
    ("et", "Eesti", "🇪🇪"),
    ("lv", "Latviešu", "🇱🇻"),
    ("lt", "Lietuvių", "🇱🇹"),
    ("sk", "Slovenčina", "🇸🇰"),
    ("sl", "Slovenščina", "🇸🇮"),
    ("hr", "Hrvatski", "🇭🇷"),
    ("sr", "Srpski", "🇷🇸"),
    ("bg", "Български", "🇧🇬"),
    ("fa", "فارسی", "🇮🇷"),
    ("pa", "ਪੰਜਾਬੀ", "🇮🇳"),
    ("ta", "தமிழ்", "🇮🇳"),
    ("te", "తెలుగు", "🇮🇳"),
    ("bn", "বাংলা", "🇧🇩"),
    ("my", "မြန်မာ", "🇲🇲"),
    ("km", "ខ្មែរ", "🇰🇭"),
    ("ne", "नेपाली", "🇳🇵"),
    ("sw", "Kiswahili", "🇰🇪"),
    ("af", "Afrikaans", "🇿🇦"),
    ("sq", "Shqip", "🇦🇱"),
    ("is", "Íslenska", "🇮🇸"),
    ("mt", "Malti", "🇲🇹"),
    ("gl", "Galego", "🇬🇱"),
    ("eu", "Euskara", "🇪🇺"),
]


def _lang_display(code: str) -> str | None:
    for c, native, flag in LANGUAGES:
        if c == code:
            return f"{flag} Auto-detect" if c == "auto" else f"{flag} {native} ({c})"
    return None


def _lang_code(text: str) -> str:
    t = text.strip()
    for c, native, flag in LANGUAGES:
        disp = f"{flag} Auto-detect" if c == "auto" else f"{flag} {native} ({c})"
        if t == disp:
            return c
    m = re.search(r"\(([a-z]{2,3})\)\s*$", t)
    return m.group(1) if m else (t or "auto")


# Hover explanations for every field (grounded in the README). Also shown in
# the window's status bar as you hover (context-sensitive help).
TIPS = {
    "model_name": ("Whisper model: larger = more accurate but slower. The .en "
                   "models are English-only and the fastest for English. "
                   "'Not downloaded' models are fetched on demand — use the "
                   "Download button."),
    "device": ("auto: use the GPU if a model fits, else CPU.  "
               "cuda: force the NVIDIA GPU.  rocm: force an AMD GPU.  "
               "cpu: never touch the GPU — less VRAM and smaller per-round "
               "CPU spikes (useful when the GPU is busy, e.g. Ollama)."),
    "device_rocm": ("AMD GPU via ROCm. Needs CTranslate2's ROCm wheel — the "
                    "standard pip install is CUDA/CPU only (see the "
                    "CTranslate2 releases page for the ROCm build)."),
    "language": ("Force a language, or Auto-detect per session. Picking the "
                 "right one improves accuracy and speed."),
    "cpu_threads": ("CPU threads for the model (CTranslate2). Raise if "
                    "transcription is slow; lower to cap the per-round CPU "
                    "spike."),
    "type_ms": ("Milliseconds per key when typing. Raise to ~10 if an app "
                "drops characters."),
    "commit_lag_s": ("How much recent audio to hold uncommitted so words can "
                     "finalise with full context (the Mac-like behaviour)."),
    "transcribe_every_s": ("How often to re-transcribe the pending audio "
                           "while you keep talking."),
    "duck_volume_pct": ("Background-audio level while the mic is live, as % "
                        "of the sink volume. 0 = the old hard-mute."),
    "duck_ramp_ms": ("Fade time (ms) of the volume dip and restore — the "
                     "smoothness of the duck."),
    "no_repeat_ngram_size": ("Block repeated N-grams to suppress repetition "
                             "loops under GPU contention. 0 = off."),
    "condition_on_previous_text": ("Let Whisper use earlier segments as "
                                   "context. Off avoids re-emitted phrases; "
                                   "on can add coherence."),
    "hotwords": ("Comma-separated words to bias the decoder toward — names, "
                 "jargon, product names."),
    "hotwords_file": ("A text file of hotwords (one per line, '#' comments) — "
                      "shareable; combined with the inline list."),
    "hallucination_tails": ("Trailing phrases Whisper may hallucinate over "
                            "trailing silence. A matching tail is stripped "
                            "before typing."),
}


def _icon() -> QIcon | None:
    """The project icon (repo ``data/icons/``), when we can find it."""
    here = Path(__file__).resolve()
    for base in (here.parents[2], here.parents[1]):
        p = base / "data" / "icons" / "type-as-you-speak.svg"
        if p.is_file():
            return QIcon(str(p))
    return None


def _hf_hub_dir() -> Path:
    """Where faster-whisper/Hugging Face caches model weights."""
    if os.environ.get("HF_HUB_CACHE"):
        return Path(os.environ["HF_HUB_CACHE"]).expanduser()
    home = os.environ.get("HF_HOME") or os.path.expanduser("~/.cache/huggingface")
    return Path(home) / "hub"


def _model_repo(name: str) -> str:
    """Hugging Face repo a model name resolves to — from faster-whisper's
    own mapping, so names like large-v3-turbo (mobiuslabsgmbh/…) are handled
    correctly. A full 'owner/repo' entered by the user passes through."""
    try:
        from faster_whisper.utils import _MODELS
        if name in _MODELS:
            return _MODELS[name]
    except Exception:
        pass
    return name if "/" in name else f"Systran/faster-whisper-{name}"


def _model_available(name: str) -> bool:
    owner, _, repo = _model_repo(name).partition("/")
    d = _hf_hub_dir() / f"models--{owner}--{repo}"
    return (d / "snapshots").is_dir()


def _nvidia_gpu() -> str | None:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5).stdout.strip().splitlines()
        return out[0].strip() if out and out[0].strip() else None
    except Exception:
        return None


def _amd_gpu() -> str | None:
    """A short name for an AMD GPU, if one is present (rocm-smi, then lspci)."""
    try:
        out = subprocess.run(["rocm-smi", "--showproductname"],
                             capture_output=True, text=True, timeout=8).stdout
        m = re.search(r"Card\[\d+\]\s*-\s*(.+)", out)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    try:
        out = subprocess.run(["lspci"], capture_output=True, text=True,
                             timeout=5).stdout
        for line in out.splitlines():
            if re.search(r"VGA|3D controller|Display controller", line) \
                    and re.search(r"AMD|ATI", line):
                name = line.split(":", 2)[-1].strip()
                brackets = re.findall(r"\[([^\]]+)\]", name)
                return brackets[-1] if brackets else name
    except Exception:
        pass
    return None


def _model_of(text: str) -> str:
    """'small.en  (484 MB) — downloaded' -> 'small.en'."""
    return text.split("  (")[0].split(" — ")[0].strip()


class SettingsWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"type-as-you-speak {__version__} — settings")
        icon = _icon()
        if icon:
            self.setWindowIcon(icon)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # ---- session panel --------------------------------------------------
        self.status_label = QLabel()
        self.session_btn = QPushButton()
        self.session_btn.clicked.connect(self._session_clicked)
        sess = QHBoxLayout()
        sess.addWidget(self.status_label, 1)
        sess.addWidget(self.session_btn)
        root.addLayout(sess)

        # ---- settings (two tabs) --------------------------------------------
        # key -> widget; populated by the builders below.
        self._fields: dict[str, QWidget] = {}
        # widget -> context-help text (status bar on hover)
        self._tips: dict[QWidget, str] = {}

        # model download state (background thread; polled by the status timer)
        self._dl_thread: threading.Thread | None = None
        self._dl_result: tuple[bool, str] | None = None
        self._dl_name = ""
        self._dl_line = ""

        general = QWidget()
        gl = QVBoxLayout(general)
        gl.addWidget(self._model_group())
        gl.addWidget(self._audio_group())
        gl.addWidget(self._corrections_group())
        gl.addStretch(1)

        advanced = QWidget()
        al = QVBoxLayout(advanced)
        al.addWidget(self._timing_group())
        al.addWidget(self._decode_group())
        al.addStretch(1)

        tabs = QTabWidget()
        tabs.addTab(general, "General")
        tabs.addTab(advanced, "Advanced")
        root.addWidget(tabs, 1)

        # ---- actions ----------------------------------------------------------
        actions = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save)
        self.revert_btn = QPushButton("Revert")
        self.revert_btn.clicked.connect(self.reload)
        self.open_btn = QPushButton("Open config file")
        self.open_btn.clicked.connect(self._open_config_file)
        actions.addStretch(1)
        for b in (self.revert_btn, self.open_btn, self.save_btn):
            actions.addWidget(b)
        root.addLayout(actions)

        hint = QLabel(
            "Changes take effect for the next session — stop and start the "
            "session to apply them.  Hover any field for an explanation.")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.reload()
        self._update_status()

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._update_status)
        self._timer.start()

    # ---- context help (status bar) + tooltips --------------------------------
    def _register(self, w: QWidget, tip: str) -> None:
        """Wire a widget for context-sensitive help: status-bar line on hover
        (robust across desktops) plus the native tooltip."""
        w.setAttribute(Qt.WA_Hover, True)
        w.installEventFilter(self)
        if tip:
            self._tips[w] = tip
            w.setToolTip(tip)

    def eventFilter(self, obj, ev) -> bool:
        if ev.type() == QEvent.Type.Enter:
            tip = self._tips.get(obj)
            if tip:
                self.statusBar().showMessage(tip)
        return super().eventFilter(obj, ev)

    # ---- widget builders ------------------------------------------------------
    def _line(self, key: str) -> QLineEdit:
        w = QLineEdit(str(load_config().get(key, "")))
        self._register(w, TIPS.get(key, ""))
        self._fields[key] = w
        return w

    def _spin(self, key: str) -> QSpinBox:
        lo, hi, step = _SPIN_INT[key]
        w = QSpinBox()
        w.setRange(lo, hi)
        w.setSingleStep(step)
        w.setValue(int(load_config().get(key, lo)))
        self._register(w, TIPS.get(key, ""))
        self._fields[key] = w
        return w

    def _dspin(self, key: str) -> QDoubleSpinBox:
        lo, hi, step = _SPIN_FLOAT[key]
        w = QDoubleSpinBox()
        w.setRange(lo, hi)
        w.setSingleStep(step)
        w.setDecimals(2)
        w.setValue(float(load_config().get(key, lo)))
        self._register(w, TIPS.get(key, ""))
        self._fields[key] = w
        return w

    # ---- model picker: availability + download --------------------------------
    def _selected_model(self) -> str:
        return _model_of(self.model_combo.currentText())

    def _refresh_model_marks(self) -> None:
        """Rebuild the model list with downloaded / not-downloaded marks."""
        cur = self._selected_model()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for name, size, _note in cli._MODELS:
            mark = " — downloaded" if _model_available(name) else " — not downloaded"
            self.model_combo.addItem(f"{name}  ({size}){mark}")
        if cur:
            texts = [self.model_combo.itemText(i) for i in range(self.model_combo.count())]
            if not any(_model_of(t) == cur for t in texts):
                mark = " — downloaded" if _model_available(cur) else " — not downloaded"
                self.model_combo.addItem(f"{cur}{mark}")
            for i in range(self.model_combo.count()):
                if _model_of(self.model_combo.itemText(i)) == cur:
                    self.model_combo.setCurrentIndex(i)
                    break
        self.model_combo.blockSignals(False)
        self._update_download_btn()

    def _update_download_btn(self) -> None:
        name = self._selected_model()
        if self._dl_thread is not None and self._dl_thread.is_alive():
            self.dl_btn.setEnabled(False)
            self.dl_btn.setText("Downloading…")
        elif _model_available(name):
            self.dl_btn.setEnabled(False)
            self.dl_btn.setText("Ready ✓")
        else:
            self.dl_btn.setEnabled(True)
            self.dl_btn.setText("Download")

    def _download_clicked(self) -> None:
        name = self._selected_model()
        if not name or (self._dl_thread is not None and self._dl_thread.is_alive()):
            return
        self._dl_name = name
        self._dl_result = None
        self._dl_line = f"Downloading {name}…"
        self.dl_btn.setEnabled(False)
        self.dl_btn.setText("Downloading…")
        self._dl_thread = threading.Thread(
            target=self._download_worker, args=(name,), daemon=True)
        self._dl_thread.start()

    def _download_worker(self, name: str) -> None:
        """Fetch the model into the Hugging Face cache (and validate it by
        loading on CPU). Runs in a background thread; the status timer polls
        _dl_line / _dl_result. Full output is also appended to
        model-download.log (state dir) so failures leave evidence."""
        code = ("from faster_whisper import WhisperModel; "
                f"WhisperModel({name!r}, device='cpu', compute_type='int8')")
        lines: list[str] = []
        try:
            p = subprocess.Popen([sys.executable, "-c", code],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True)
            assert p.stdout is not None
            for line in p.stdout:
                if line.strip():
                    self._dl_line = line.strip()
                    lines.append(line.rstrip())
            p.wait(timeout=3600)
            self._log_download(name, p.returncode, lines)
            tail = [l for l in (self._dl_line or "").splitlines() if l.strip()]
            if p.returncode == 0:
                self._dl_result = (True, "done")
            else:
                self._dl_result = (False, (tail[-1] if tail else "download failed"))
        except Exception as e:
            self._log_download(name, -1, lines + [repr(e)])
            self._dl_result = (False, repr(e))

    def _log_download(self, name: str, exit_code: int, lines: list[str]) -> None:
        import datetime
        try:
            d = cli._state_dir()
            d.mkdir(parents=True, exist_ok=True)
            with open(d / "model-download.log", "a", encoding="utf-8") as f:
                f.write(f"\n=== {datetime.datetime.now().isoformat(timespec='seconds')}"
                        f" model={name!r} exit={exit_code} ===\n")
                for l in lines[-50:]:
                    f.write(l + "\n")
        except Exception:
            pass

    def _model_group(self) -> QGroupBox:
        g = QGroupBox("Model & device")
        f = QFormLayout(g)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self._register(self.model_combo, TIPS["model_name"])
        self.model_combo.currentTextChanged.connect(lambda _t: self._update_download_btn())
        self._fields["model_name"] = self.model_combo

        self.dl_btn = QPushButton("Download")
        self.dl_btn.setToolTip(
            "Download the selected model (stored in the Hugging Face cache; "
            "the session would also fetch it on first use).")
        self.dl_btn.clicked.connect(self._download_clicked)
        self.model_label = QLabel("")
        self.model_label.setWordWrap(True)
        mh = QHBoxLayout()
        mh.addWidget(self.model_combo, 1)
        mh.addWidget(self.dl_btn)
        f.addRow("Model:", mh)
        f.addRow("", self.model_label)
        self._refresh_model_marks()

        # device: radio buttons; each vendor option is offered only when that
        # vendor's GPU is actually present, otherwise greyed out with a reason.
        self._dev_btns: dict[str, QRadioButton] = {}
        self._dev_group = QButtonGroup(self)
        dev_cfg = str(load_config().get("device", "auto"))
        nv = _nvidia_gpu()
        amd = _amd_gpu()
        options: list[tuple[str, str, str]] = [("auto", "Auto", TIPS["device"])]
        if nv:
            options.append(("cuda", f"GPU — CUDA ({nv})", TIPS["device"]))
        else:
            options.append(("cuda", "GPU — CUDA (NVIDIA)",
                            "No NVIDIA GPU detected — unavailable on this machine."))
        if amd:
            options.append(("rocm", f"GPU — ROCm ({amd})", TIPS["device_rocm"]))
        else:
            options.append(("rocm", "GPU — ROCm (AMD)",
                            "No AMD GPU detected — unavailable on this machine."))
        options.append(("cpu", "CPU", TIPS["device"]))
        dev_row = QHBoxLayout()
        for key, label, tip in options:
            rb = QRadioButton(label)
            self._register(rb, tip)
            self._dev_group.addButton(rb)
            self._dev_btns[key] = rb
            dev_row.addWidget(rb)
        self._dev_btns["cuda"].setEnabled(bool(nv))
        self._dev_btns["rocm"].setEnabled(bool(amd))
        target = dev_cfg if dev_cfg in self._dev_btns and self._dev_btns[dev_cfg].isEnabled() else "auto"
        self._dev_btns[target].setChecked(True)
        f.addRow("Device:", dev_row)

        self.lang_combo = QComboBox()
        self.lang_combo.setEditable(True)
        self._register(self.lang_combo, TIPS["language"])
        self.lang_combo.addItems(
            [f"{flag} Auto-detect" if c == "auto" else f"{flag} {native} ({c})"
             for c, native, flag in LANGUAGES])
        lang = str(load_config().get("language", "auto"))
        disp = _lang_display(lang)
        if disp is None:
            self.lang_combo.insertItem(0, lang)
            self.lang_combo.setCurrentText(lang)
        else:
            self.lang_combo.setCurrentText(disp)
        self._fields["language"] = self.lang_combo
        f.addRow("Language:", self.lang_combo)

        f.addRow("CPU threads:", self._spin("cpu_threads"))
        return g

    def _timing_group(self) -> QGroupBox:
        g = QGroupBox("Typing & pacing")
        f = QFormLayout(g)
        f.addRow("Type speed (ms/key):", self._spin("type_ms"))
        f.addRow("Commit lag (s):", self._dspin("commit_lag_s"))
        f.addRow("Transcribe every (s):", self._dspin("transcribe_every_s"))
        return g

    def _audio_group(self) -> QGroupBox:
        g = QGroupBox("Background audio while dictating")
        f = QFormLayout(g)
        f.addRow("Duck level (%, 0 = hard mute):", self._spin("duck_volume_pct"))
        f.addRow("Fade time (ms):", self._spin("duck_ramp_ms"))
        return g

    def _decode_group(self) -> QGroupBox:
        g = QGroupBox("Decode stability")
        f = QFormLayout(g)
        f.addRow("No-repeat N-gram size (0 = off):", self._spin("no_repeat_ngram_size"))
        w = QCheckBox("Condition on previous text")
        w.setChecked(bool(load_config().get("condition_on_previous_text", False)))
        self._register(w, TIPS["condition_on_previous_text"])
        self._fields["condition_on_previous_text"] = w
        f.addRow(w)
        return g

    def _corrections_group(self) -> QGroupBox:
        g = QGroupBox("Corrections")
        f = QFormLayout(g)
        f.addRow("Hotwords (comma-separated):", self._line("hotwords"))

        hf = QHBoxLayout()
        self.hotwords_file_edit = self._line("hotwords_file")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_hotwords_file)
        editor = QPushButton("Open in editor")
        editor.clicked.connect(lambda: self._open_file(self.hotwords_file_edit.text()))
        hf.addWidget(self.hotwords_file_edit, 1)
        hf.addWidget(browse)
        hf.addWidget(editor)
        f.addRow("Hotwords file:", hf)

        w = QPlainTextEdit()
        w.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        w.setPlainText("\n".join(load_config().get("hallucination_tails", [])))
        self._register(w, TIPS["hallucination_tails"])
        self._fields["hallucination_tails"] = w
        f.addRow("Hallucination tails (one per line):", w)
        return g

    # ---- values <-> widgets ----------------------------------------------------
    def _value_for(self, key: str, widget: QWidget):
        if isinstance(widget, QComboBox):
            text = widget.currentText().strip()
            if key == "model_name":
                return _model_of(text)
            if key == "language":
                return _lang_code(text)
            return text
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QPlainTextEdit):
            return [l.strip() for l in widget.toPlainText().splitlines() if l.strip()]
        if isinstance(widget, QDoubleSpinBox):
            return round(widget.value(), 2)
        if isinstance(widget, QSpinBox):
            return widget.value()
        return widget.text().strip()

    def _set_widget(self, key: str, widget: QWidget, value) -> None:
        if isinstance(widget, QComboBox):
            if key == "model_name":
                widget.setEditText(str(value))
                self._refresh_model_marks()   # re-apply availability marks
                return
            if key == "language":
                disp = _lang_display(str(value))
                widget.setEditText(disp or str(value))
                return
            widget.setEditText(str(value))
            return
        if isinstance(widget, QCheckBox):
            widget.setChecked(bool(value))
            return
        if isinstance(widget, QPlainTextEdit):
            widget.setPlainText("\n".join(value) if isinstance(value, list)
                                else str(value))
            return
        if isinstance(widget, QDoubleSpinBox):
            widget.setValue(float(value))
            return
        if isinstance(widget, QSpinBox):
            widget.setValue(int(value))
            return
        widget.setText(str(value))

    def _device_value(self) -> str:
        for key, btn in self._dev_btns.items():
            if btn.isChecked():
                return key
        return "auto"

    def _set_device(self, value: str) -> None:
        if value in self._dev_btns and self._dev_btns[value].isEnabled():
            self._dev_btns[value].setChecked(True)
        else:
            self._dev_btns["auto"].setChecked(True)

    def reload(self) -> None:
        """Refresh every widget from the current config (file + defaults)."""
        cfg = load_config()
        for key, widget in self._fields.items():
            if key in cfg:
                self._set_widget(key, widget, cfg[key])
        self._set_device(str(cfg.get("device", "auto")))
        self.statusBar().showMessage("Settings reloaded from config.")

    # ---- save / revert / open ---------------------------------------------------
    def save(self) -> None:
        path = user_config_path()
        try:
            if path.is_file():
                doc = tomlkit.parse(path.read_text())
            else:
                # No file yet: seed the full sample (all keys, with comments),
                # then apply the values below.
                doc = tomlkit.parse(cli._sample_config_text())
            for key, widget in self._fields.items():
                doc[key] = self._value_for(key, widget)
            doc["device"] = self._device_value()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(tomlkit.dumps(doc))
        except Exception as e:
            QMessageBox.critical(self, "Save failed",
                                 f"Could not write {path}:\n{e}")
            return
        self.statusBar().showMessage(
            f"Saved to {path} — applies to the next session.")

    def _open_config_file(self) -> None:
        self._open_file(str(user_config_path()))

    def _open_file(self, path: str) -> None:
        if not path or not Path(path).is_file():
            QMessageBox.information(self, "Open", "No such file.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).expanduser())))

    def _browse_hotwords_file(self) -> None:
        start = self.hotwords_file_edit.text().strip() or str(Path.home())
        p = QFileDialog.getOpenFileName(
            self, "Choose a hotwords file", start,
            "Text files (*.txt);;All files (*)")
        if p:
            self.hotwords_file_edit.setText(p[0])

    # ---- session control -----------------------------------------------------
    def _tays(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "type_as_you_speak", *args],
            capture_output=True, text=True, timeout=30,
        )

    def _status_line(self, st: dict) -> str:
        model = st.get("model", "?")
        dev = str(st.get("device", "?"))
        if st.get("running"):
            gpu = st.get("gpu")
            if gpu:
                on = f"{gpu} ({dev.upper()})"
            elif dev == "cpu":
                on = "CPU (int8)"
            else:
                on = dev.upper()
            return f"● Listening — {model} on {on} (pid {st.get('pid')})"
        return f"● Stopped — {model} (device: {dev})"

    def _update_status(self) -> None:
        # model download progress (background thread)
        if self._dl_thread is not None:
            if self._dl_thread.is_alive():
                if self._dl_line:
                    self.model_label.setText(self._dl_line)
                self._update_download_btn()
            else:
                # Consume exactly ONCE — leaving _dl_thread set would make the
                # next tick re-run this branch with _dl_result already cleared
                # and overwrite the real message with "unknown error".
                self._dl_thread = None
                ok, msg = self._dl_result or (
                    False, "unknown error — see model-download.log in "
                          "~/.local/state/type-as-you-speak/")
                self._dl_result = None
                self.model_label.setText(
                    f"Downloaded {self._dl_name} ✓ — ready to use"
                    if ok else f"Download failed: {msg}")
                self._refresh_model_marks()
        try:
            p = self._tays("status", "--json")
            st = json.loads(p.stdout)
        except Exception:
            self.status_label.setText("status: (unavailable)")
            return
        self.status_label.setText(self._status_line(st))
        self.session_btn.setText("Stop" if st.get("running") else "Start")

    def _session_clicked(self) -> None:
        try:
            p = self._tays("toggle")
            detail = (p.stdout or p.stderr).strip().splitlines()
            if detail:
                self.statusBar().showMessage(detail[-1])
        except Exception as e:
            QMessageBox.warning(self, "Session", f"toggle failed: {e!r}")
        self._update_status()


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    win = SettingsWindow()
    win.resize(700, 760)
    win.show()
    return app.exec()

"""Optional settings GUI — ``tays gui``.

A single window to pick the model and every other option instead of editing
config.toml by hand:

  * session panel — live status (polled from ``tays status --json``, showing
    the EXACT runtime device, e.g. "medium.en on NVIDIA GeForce RTX 5090
    (CUDA)") and a start/stop button (drives ``tays toggle`` as a subprocess,
    so the engine always runs in its own process, exactly like the CLI);
  * General tab — Model & device (downloaded marks + Download button,
    Auto / GPU-CUDA / GPU-ROCm / CPU radios gated on what the installed
    CTranslate2 build can actually use), Background audio ducking;
  * Corrections tab — hotwords (inline + file, with the file's contents shown
    in an editable area below), hallucination tails (inline + file, same
    treatment);
  * Advanced tab — Typing & pacing, Decode stability.

Every field carries a hover tooltip AND a context-help line in the window's
status bar (shown as you hover — robust across desktops). Language is a
dropdown of flags + native names; picking a non-English language warns about
English-only (.en) models and switches to their multilingual twin when that
is already downloaded.

User-facing strings go through QObject.tr() so the window is translatable
once .ts/.qm files are added.

Saving writes ``~/.config/type-as-you-speak/config.toml`` with ``tomlkit`` in
a way that preserves the file's existing comments and layout, and writes the
hotwords / tails files when their contents have been edited. Requires the
optional ``gui`` extra (PySide6 + tomlkit); the core stays lean.
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

# English-only models and their multilingual twins (same family). When a
# non-English language is picked, the .en choice can't be right.
MULTILINGUAL_TWINS = {
    "tiny.en": "tiny",
    "base.en": "base",
    "small.en": "small",
    "medium.en": "medium",
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
            return "🌐 Auto-detect" if c == "auto" else f"{flag} {native} ({c})"
    return None


def _lang_code(text: str) -> str:
    t = text.strip()
    for c, native, flag in LANGUAGES:
        disp = "🌐 Auto-detect" if c == "auto" else f"{flag} {native} ({c})"
        if t == disp:
            return c
    m = re.search(r"\(([a-z]{2,3})\)\s*$", t)
    return m.group(1) if m else (t or "auto")


# Hover explanations for every field. Plain English first; the technical
# detail (if any) comes after the first sentence. Also shown in the window's
# status bar as you hover (context-sensitive help).
TIPS = {
    "model_name": ("Which speech-recognition model to use. Bigger models understand "
                   "better but are slower and use more memory — pick one marked "
                   "'downloaded' for everyday use. Note: models ending in .en "
                   "understand English only."),
    "device": ("Where the thinking happens. Auto picks the best option: your "
               "graphics card (GPU) if it can hold the model, otherwise the main "
               "processor (CPU). The GPU is faster; the CPU is calmer on the "
               "battery and doesn't compete with other GPU work."),
    "device_rocm": ("Support for AMD graphics cards. Not available on this "
                    "machine — the installed build is for NVIDIA (CUDA) cards. "
                    "For an AMD GPU you'd need CTranslate2's ROCm build."),
    "language": ("The language you'll be speaking. Setting it makes recognition "
                 "more accurate and a bit faster. If it's not English, avoid the "
                 ".en models — they understand English only (the list will mark "
                 "them, and can switch to the matching all-language model)."),
    "cpu_threads": ("How many CPU cores the model may use while thinking. More "
                    "cores = faster, but a bigger short CPU spike. Leave it at "
                    "the default unless transcription feels slow."),
    "type_ms": ("How quickly words are typed into your window (milliseconds "
                "per key). If an app sometimes drops letters, raise this — 10 "
                "is a good test value."),
    "commit_lag_s": ("How long a word waits before it's typed. This little "
                     "pause is what lets it phrase things with the full "
                     "sentence in mind, so words land and then never change — "
                     "the Mac-like feel. Lower = snappier, higher = more "
                     "polished."),
    "transcribe_every_s": ("How often it re-listens to what you've just said "
                           "while you keep talking, so it can adjust the "
                           "wording as the sentence grows."),
    "duck_volume_pct": ("How quiet the music and other sound get while you're "
                        "talking, as a percentage of the volume. 0 = turn it "
                        "off completely."),
    "duck_ramp_ms": ("How gently the sound fades down and back up (in "
                     "milliseconds). Larger = smoother, less noticeable."),
    "no_repeat_ngram_size": ("A safety switch that stops the model repeating "
                             "itself when the GPU is overloaded. Leave it on "
                             "(2); 0 turns it off."),
    "condition_on_previous_text": ("Let the model use your earlier words as "
                                   "context. Off is safer: it stops the model "
                                   "re-typing a phrase it already gave you."),
    "hotwords": ("Words the app keeps getting wrong — names, products, "
                 "jargon. One per line (commas work too). Keep it short: "
                 "every entry nudges the model a little, so a very long list "
                 "can backfire."),
    "hotwords_file": ("A text file that holds the hotwords list, so it's easy "
                      "to share or keep out of the settings file. Edit the box "
                      "above and Save writes it there."),
    "hallucination_tails": ("Nonsense phrases the model sometimes adds at the "
                            "end of a sentence when you pause — like 'thanks "
                            "for watching' or 'see you next time'. Add any you "
                            "see, one per line, and they'll be stripped before "
                            "they're typed."),
    "hallucination_tails_file": ("A text file that holds the tails list, so "
                                 "it's easy to share or keep out of the "
                                 "settings file. Edit the box above and Save "
                                 "writes it there."),
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


def _gpu_count() -> int | None:
    """GPUs the INSTALLED CTranslate2 build can actually use (via the HIP
    layer this covers ROCm too). 0 = no usable GPU with this build (CPU-only
    wheel, or no GPU). None = ctranslate2 not importable (fall back to
    hardware-only detection)."""
    try:
        import ctranslate2
        return int(ctranslate2.get_cuda_device_count())
    except Exception:
        return None


def _model_of(text: str) -> str:
    """'small.en  (484 MB) — downloaded' -> 'small.en'."""
    return text.split("  (")[0].split(" — ")[0].split(" · ")[0].strip()


class SettingsWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(self.tr("type-as-you-speak {v} — settings").format(v=__version__))
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

        # ---- settings (three tabs) ------------------------------------------
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
        gl.addStretch(1)

        corrections = QWidget()
        cl = QVBoxLayout(corrections)
        cl.addWidget(self._corrections_group())
        cl.addStretch(1)

        advanced = QWidget()
        al = QVBoxLayout(advanced)
        al.addWidget(self._timing_group())
        al.addWidget(self._decode_group())
        al.addStretch(1)

        tabs = QTabWidget()
        tabs.addTab(general, self.tr("General"))
        tabs.addTab(corrections, self.tr("Corrections"))
        tabs.addTab(advanced, self.tr("Advanced"))
        root.addWidget(tabs, 1)

        # ---- actions ----------------------------------------------------------
        actions = QHBoxLayout()
        self.save_btn = QPushButton(self.tr("Save"))
        self.save_btn.clicked.connect(self.save)
        self.revert_btn = QPushButton(self.tr("Revert"))
        self.revert_btn.clicked.connect(self.reload)
        self.open_btn = QPushButton(self.tr("Open config file"))
        self.open_btn.clicked.connect(self._open_config_file)
        actions.addStretch(1)
        for b in (self.revert_btn, self.open_btn, self.save_btn):
            actions.addWidget(b)
        root.addLayout(actions)

        hint = QLabel(self.tr(
            "Changes take effect for the next session — stop and start the "
            "session to apply them.  Hover any field for an explanation."))
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

    def _listarea(self, placeholder: str) -> QPlainTextEdit:
        w = QPlainTextEdit()
        w.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        w.setPlaceholderText(placeholder)
        w.setFixedHeight(120)
        return w

    # ---- model picker: availability + download --------------------------------
    def _selected_model(self) -> str:
        return _model_of(self.model_combo.currentText())

    def _selected_lang(self) -> str:
        return _lang_code(self.lang_combo.currentText())

    def _en_only_marked(self) -> bool:
        """True when a specific non-English language is active — .en models
        are the wrong tools then, so they get an explicit mark."""
        return self._selected_lang() not in ("auto", "en", "")

    def _refresh_model_marks(self) -> None:
        """Rebuild the model list with downloaded / not-downloaded marks (and
        an 'English only' mark when a non-English language is selected)."""
        cur = self._selected_model()
        marked = self._en_only_marked()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for name, size, _note in cli._MODELS:
            mark = " — downloaded" if _model_available(name) else " — not downloaded"
            if marked and name.endswith(".en"):
                mark += " · English only"
            self.model_combo.addItem(f"{name}  ({size}){mark}")
        if cur:
            texts = [self.model_combo.itemText(i) for i in range(self.model_combo.count())]
            if not any(_model_of(t) == cur for t in texts):
                mark = " — downloaded" if _model_available(cur) else " — not downloaded"
                if marked and cur.endswith(".en"):
                    mark += " · English only"
                self.model_combo.addItem(f"{cur}{mark}")
            for i in range(self.model_combo.count()):
                if _model_of(self.model_combo.itemText(i)) == cur:
                    self.model_combo.setCurrentIndex(i)
                    break
        self.model_combo.blockSignals(False)
        self._update_download_btn()

    def _model_lang_sync(self) -> None:
        """Picked a non-English language while an .en model is selected: the
        .en model can only transcribe English. Switch to the multilingual
        twin when it's already downloaded (no surprise fetch), otherwise
        point at it — and mark the list either way."""
        self._refresh_model_marks()
        lang = self._selected_lang()
        model = self._selected_model()
        if lang in ("auto", "en", "") or model not in MULTILINGUAL_TWINS:
            return
        twin = MULTILINGUAL_TWINS[model]
        if _model_available(twin):
            self.model_combo.setCurrentText(twin)
            native = next((n for c, n, _f in LANGUAGES if c == lang), lang)
            self.statusBar().showMessage(self.tr(
                "{m} is English-only — switched to {t} for {n}.").format(
                m=model, t=twin, n=native))
        else:
            native = next((n for c, n, _f in LANGUAGES if c == lang), lang)
            self.statusBar().showMessage(self.tr(
                "{m} is English-only — {t} suits {n} better (Download it or "
                "pick it from the list).").format(m=model, t=twin, n=native))
        self._update_download_btn()

    def _update_download_btn(self) -> None:
        name = self._selected_model()
        if self._dl_thread is not None and self._dl_thread.is_alive():
            self.dl_btn.setEnabled(False)
            self.dl_btn.setText(self.tr("Downloading…"))
        elif _model_available(name):
            self.dl_btn.setEnabled(False)
            self.dl_btn.setText(self.tr("Ready ✓"))
        else:
            self.dl_btn.setEnabled(True)
            self.dl_btn.setText(self.tr("Download"))

    def _download_clicked(self) -> None:
        name = self._selected_model()
        if not name or (self._dl_thread is not None and self._dl_thread.is_alive()):
            return
        self._dl_name = name
        self._dl_result = None
        self._dl_line = f"Downloading {name}…"
        self.dl_btn.setEnabled(False)
        self.dl_btn.setText(self.tr("Downloading…"))
        self._dl_thread = threading.Thread(
            target=self._download_worker, args=(name,), daemon=True)
        self._dl_thread.start()

    def _download_worker(self, name: str) -> None:
        """Fetch the model into the Hugging Face cache (and validate it by
        loading on CPU). Runs in a background thread; the status timer polls
        _dl_line / _dl_result. Full output is also appended to
        model-download.log (state dir) so failures leave evidence."""
        code = (f"from faster_whisper import WhisperModel; "
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
        g = QGroupBox(self.tr("Model & device"))
        f = QFormLayout(g)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        # keep the "English only" / downloaded marks in sync with whichever
        # of language/model is changed last
        self.model_combo.currentTextChanged.connect(
            lambda _t: self._refresh_model_marks())
        self._register(self.model_combo, TIPS["model_name"])
        self._fields["model_name"] = self.model_combo

        self.dl_btn = QPushButton(self.tr("Download"))
        self.dl_btn.setToolTip(self.tr(
            "Download the selected model (stored in the Hugging Face cache; "
            "the session would also fetch it on first use)."))
        self.dl_btn.clicked.connect(self._download_clicked)
        self.model_label = QLabel("")
        self.model_label.setWordWrap(True)
        mh = QHBoxLayout()
        mh.addWidget(self.model_combo, 1)
        mh.addWidget(self.dl_btn)
        f.addRow(self.tr("Model:"), mh)
        f.addRow("", self.model_label)

        # device: radio buttons. A vendor option is enabled ONLY when the
        # installed CTranslate2 build can actually use that GPU — hardware
        # alone (lspci) is not enough, e.g. an AMD iGPU with a CUDA build.
        self._dev_btns: dict[str, QRadioButton] = {}
        self._dev_group = QButtonGroup(self)
        dev_cfg = str(load_config().get("device", "auto"))
        nv = _nvidia_gpu()
        amd = _amd_gpu()
        count = _gpu_count()
        cuda_ok = bool(nv) and (count is None or count > 0)
        rocm_ok = bool(amd) and (count is None or count > 0) and not nv
        if count == 0:
            cuda_tip = self.tr("No usable GPU with the installed CTranslate2 "
                               "build (it's a CPU-only wheel).")
            rocm_tip = cuda_tip
        elif nv and amd:
            cuda_tip = TIPS["device"]
            rocm_tip = self.tr("A CUDA build is active on this machine — "
                               "install CTranslate2's ROCm wheel to use the "
                               "AMD GPU.")
        else:
            cuda_tip = TIPS["device"]
            rocm_tip = TIPS["device_rocm"]
        options: list[tuple[str, str, str, bool]] = [
            ("auto", self.tr("Auto"), TIPS["device"], True),
            ("cuda", (f"GPU — CUDA ({nv})" if nv else self.tr("GPU — CUDA (NVIDIA)")),
             cuda_tip, cuda_ok),
            ("rocm", (f"GPU — ROCm ({amd})" if amd else self.tr("GPU — ROCm (AMD)")),
             rocm_tip, rocm_ok),
            ("cpu", self.tr("CPU"), TIPS["device"], True),
        ]
        dev_row = QHBoxLayout()
        for key, label, tip, ok in options:
            rb = QRadioButton(label)
            rb.setEnabled(ok)
            self._register(rb, tip if ok else tip + " "
                           + self.tr("Unavailable on this machine."))
            self._dev_group.addButton(rb)
            self._dev_btns[key] = rb
            dev_row.addWidget(rb)
        target = (dev_cfg if dev_cfg in self._dev_btns
                  and self._dev_btns[dev_cfg].isEnabled() else "auto")
        self._dev_btns[target].setChecked(True)
        f.addRow(self.tr("Device:"), dev_row)

        self.lang_combo = QComboBox()
        self.lang_combo.setEditable(True)
        self._register(self.lang_combo, TIPS["language"])
        self.lang_combo.addItems(
            ["🌐 Auto-detect" if c == "auto" else f"{flag} {native} ({c})"
             for c, native, flag in LANGUAGES])
        self.lang_combo.currentTextChanged.connect(
            lambda _t: (self._update_download_btn(), self._model_lang_sync()))
        self._fields["language"] = self.lang_combo
        f.addRow(self.tr("Language:"), self.lang_combo)

        f.addRow(self.tr("CPU threads:"), self._spin("cpu_threads"))

        self._refresh_model_marks()
        return g

    def _timing_group(self) -> QGroupBox:
        g = QGroupBox(self.tr("Typing & pacing"))
        f = QFormLayout(g)
        f.addRow(self.tr("Type speed (ms/key):"), self._spin("type_ms"))
        f.addRow(self.tr("Commit lag (s):"), self._dspin("commit_lag_s"))
        f.addRow(self.tr("Transcribe every (s):"), self._dspin("transcribe_every_s"))
        return g

    def _audio_group(self) -> QGroupBox:
        g = QGroupBox(self.tr("Background audio while dictating"))
        f = QFormLayout(g)
        f.addRow(self.tr("Duck level (%, 0 = hard mute):"), self._spin("duck_volume_pct"))
        f.addRow(self.tr("Fade time (ms):"), self._spin("duck_ramp_ms"))
        return g

    def _decode_group(self) -> QGroupBox:
        g = QGroupBox(self.tr("Decode stability"))
        f = QFormLayout(g)
        f.addRow(self.tr("No-repeat N-gram size (0 = off):"),
                 self._spin("no_repeat_ngram_size"))
        w = QCheckBox(self.tr("Condition on previous text"))
        w.setChecked(bool(load_config().get("condition_on_previous_text", False)))
        self._register(w, TIPS["condition_on_previous_text"])
        self._fields["condition_on_previous_text"] = w
        f.addRow(w)
        return g

    # ---- corrections: one editor per list + one optional file ----------------
    def _default_file_for(self, key: str) -> str:
        """The natural home for a list file (next to the settings file) —
        offered in the field when the config has no entry yet, so there is
        always a visible, sensible path; saving with it creates the file."""
        name = {"hotwords_file": "hotwords.txt",
                "hallucination_tails_file": "hallucination-tails.txt"}.get(
            key, key + ".txt")
        return str(user_config_path().parent / name)

    def _file_row(self, key: str, browse_title: str) -> QHBoxLayout:
        """[path] [Browse…] [Open in editor] — where the list is kept."""
        cfg = str(load_config().get(key, "")).strip() or self._default_file_for(key)
        w = QLineEdit(cfg)
        self._register(w, TIPS[key])
        self._fields[key] = w
        hf = QHBoxLayout()
        hf.addWidget(w, 1)
        browse = QPushButton(self.tr("Browse…"))
        browse.clicked.connect(lambda: self._browse_file(key, browse_title))
        editor = QPushButton(self.tr("Open in editor"))
        editor.clicked.connect(lambda: self._open_file(w.text()))
        hf.addWidget(browse)
        hf.addWidget(editor)
        return hf

    def _effective_list(self, list_key: str, file_key: str) -> list[str]:
        """The list that's actually in effect: the inline settings value plus
        the file, deduped (first occurrence wins) — the same combination the
        engine uses, so the editor shows exactly what's active."""
        cfg = load_config()
        inline = cfg.get(list_key, "")
        if isinstance(inline, str):
            entries = [e.strip() for e in re.split(r"[,;]", inline) if e.strip()]
        else:
            entries = [str(e).strip() for e in inline if str(e).strip()]
        p = str(cfg.get(file_key, "")).strip()
        if not p:
            # No entry in the config yet: if the natural home file exists,
            # that's clearly the intended list — show it (Save wires it up).
            cand = self._default_file_for(file_key)
            if Path(cand).expanduser().is_file():
                p = cand
        if p:
            try:
                text = Path(p).expanduser().read_text(encoding="utf-8")
                for line in text.splitlines():
                    e = line.split("#", 1)[0].strip()
                    if e:
                        entries.append(e)
            except OSError:
                pass  # missing file: inline value only
        seen, out = set(), []
        for e in entries:
            k = e.casefold()
            if k not in seen:
                seen.add(k)
                out.append(e)
        return out

    def _corrections_group(self) -> QGroupBox:
        g = QGroupBox(self.tr("Corrections"))
        f = QFormLayout(g)

        self.hw_area = self._listarea(self.tr("One word or phrase per line…"))
        self._register(self.hw_area, TIPS["hotwords"])
        f.addRow(self.tr("Hotwords — words it should hear right:"), self.hw_area)
        f.addRow("", self._file_row("hotwords_file",
                                    self.tr("Choose a hotwords file")))

        self.tails_area = self._listarea(self.tr("One phrase per line…"))
        self._register(self.tails_area, TIPS["hallucination_tails"])
        f.addRow(self.tr("Tails — phrases to strip off the end:"), self.tails_area)
        f.addRow("", self._file_row("hallucination_tails_file",
                                    self.tr("Choose a tails file")))
        return g

    def _load_areas(self) -> None:
        self.hw_area.setPlainText(
            "\n".join(self._effective_list("hotwords", "hotwords_file")))
        self.tails_area.setPlainText(
            "\n".join(self._effective_list("hallucination_tails",
                                           "hallucination_tails_file")))

    def _browse_file(self, key: str, title: str) -> None:
        start = str(self._fields[key].text()).strip() or str(Path.home())
        p = QFileDialog.getOpenFileName(self, title, start,
                                        self.tr("Text files (*.txt);;All files (*)"))
        if p:
            self._fields[key].setText(p[0])

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
        file_keys = ("hotwords_file", "hallucination_tails_file")
        for key, widget in self._fields.items():
            if key in cfg:
                value = cfg[key]
                if key in file_keys and not str(value).strip():
                    # keep the sensible default entry (next to the settings)
                    # rather than showing an empty path
                    value = self._default_file_for(key)
                self._set_widget(key, widget, value)
        self._set_device(str(cfg.get("device", "auto")))
        self._load_areas()
        self._refresh_model_marks()
        self.statusBar().showMessage(self.tr("Settings reloaded from config."))

    # ---- save / revert / open ---------------------------------------------------
    def save(self) -> None:
        path = user_config_path()

        # Resolve the correction lists first: the editor's content goes to the
        # file when a path is set (and the inline copy is cleared, so the list
        # lives in exactly one place), otherwise it stays in the settings.
        lists = []
        for file_key, area in (("hotwords_file", self.hw_area),
                               ("hallucination_tails_file", self.tails_area)):
            p = str(self._fields[file_key].text()).strip()
            lines = [e.strip() for line in area.toPlainText().splitlines()
                     for e in re.split(r"[,;]", line) if e.strip()]
            lists.append((Path(p).expanduser() if p else None, lines))
        (hw_target, hw_lines), (tl_target, tl_lines) = lists

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
            doc["hotwords"] = "" if hw_target else ",".join(hw_lines)
            doc["hallucination_tails"] = [] if tl_target else list(tl_lines)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(tomlkit.dumps(doc))
        except Exception as e:
            QMessageBox.critical(self, self.tr("Save failed"),
                                 self.tr("Could not write {p}:").format(p=path) + f"\n{e}")
            return

        # Write the list files (creating them if needed).
        try:
            for target, lines in ((hw_target, hw_lines), (tl_target, tl_lines)):
                if target is not None:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(
                        "\n".join(lines) + ("\n" if lines else ""),
                        encoding="utf-8")
        except Exception as e:
            QMessageBox.warning(self, self.tr("Save"),
                                self.tr("Config saved, but a list file could not "
                                        "be written: {e}").format(e=e))
            return
        self.statusBar().showMessage(
            self.tr("Saved to {p} — applies to the next session.").format(p=str(path)))

    def _open_config_file(self) -> None:
        self._open_file(str(user_config_path()))

    def _open_file(self, path: str) -> None:
        if not path or not Path(path).is_file():
            QMessageBox.information(self, self.tr("Open"), self.tr("No such file."))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).expanduser())))

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
                on = self.tr("CPU (int8)")
            else:
                on = dev.upper()
            line = self.tr("● Listening — {m} on {d} (pid {p})").format(
                m=model, d=on, p=st.get("pid"))
            # The running session keeps the device it STARTED with; a config
            # change applies to the next session. Say so, or the panel and
            # the radio buttons look out of sync.
            cfg_dev = str(load_config().get("device", "auto"))
            if cfg_dev != dev:
                line += "  " + self.tr("(configured: {c} — applies to the next session)").format(c=cfg_dev)
            return line
        return self.tr("● Stopped — {m} (device: {d})").format(m=model, d=dev)

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
                    False, self.tr("unknown error — see model-download.log in "
                                  "~/.local/state/type-as-you-speak/"))
                self._dl_result = None
                self.model_label.setText(
                    self.tr("Downloaded {n} ✓ — ready to use").format(n=self._dl_name)
                    if ok else self.tr("Download failed: {e}").format(e=msg))
                self._refresh_model_marks()
        try:
            p = self._tays("status", "--json")
            st = json.loads(p.stdout)
        except Exception:
            self.status_label.setText(self.tr("status: (unavailable)"))
            return
        self.status_label.setText(self._status_line(st))
        self.session_btn.setText(self.tr("Stop") if st.get("running") else self.tr("Start"))

    def _session_clicked(self) -> None:
        try:
            p = self._tays("toggle")
            detail = (p.stdout or p.stderr).strip().splitlines()
            if detail:
                self.statusBar().showMessage(detail[-1])
        except Exception as e:
            QMessageBox.warning(self, self.tr("Session"),
                                self.tr("toggle failed: {e!r}").format(e=e))
        self._update_status()


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    win = SettingsWindow()
    win.resize(720, 780)
    win.show()
    return app.exec()

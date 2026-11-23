"""Optional settings GUI — ``tays gui``.

A single window to pick the model and every other option instead of editing
config.toml by hand:

  * session panel — live status (polled from ``tays status --json``) and a
    start/stop button (drives ``tays toggle`` / ``tays stop`` as subprocesses,
    so the engine always runs in its own process, exactly like the CLI);
  * model & device, timing, audio ducking, decode stability, and corrections
    (hotwords inline + file, hallucination-tail list).

Saving writes ``~/.config/type-as-you-speak/config.toml`` with ``tomlkit`` in a
way that preserves the file's existing comments and layout. Requires the
optional ``gui`` extra (PySide6 + tomlkit); the core stays lean.
"""
import json
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QPlainTextEdit, QSpinBox, QVBoxLayout, QWidget,
)

import tomlkit

from . import __version__
from . import cli
from .config import load_config, user_config_path

# Spin-box ranges (key -> (min, max, single-step, decimals)).
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


def _icon() -> QIcon | None:
    """The project icon (repo ``data/icons/``), when we can find it."""
    here = Path(__file__).resolve()
    for base in (here.parents[2], here.parents[1]):
        p = base / "data" / "icons" / "type-as-you-speak.svg"
        if p.is_file():
            return QIcon(str(p))
    return None


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

        # ---- settings groups --------------------------------------------------
        # key -> widget; populated by the builders below (skips specials).
        self._fields: dict[str, QWidget] = {}

        root.addWidget(self._model_group())
        root.addWidget(self._timing_group())
        root.addWidget(self._audio_group())
        root.addWidget(self._decode_group())
        root.addWidget(self._corrections_group())

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
            "session to apply them.")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.reload()
        self._update_status()

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._update_status)
        self._timer.start()

    # ---- widget builders ------------------------------------------------------
    def _line(self, key: str) -> QLineEdit:
        w = QLineEdit(str(load_config().get(key, "")))
        self._fields[key] = w
        return w

    def _spin(self, key: str) -> QSpinBox:
        lo, hi, step = _SPIN_INT[key]
        w = QSpinBox()
        w.setRange(lo, hi)
        w.setSingleStep(step)
        w.setValue(int(load_config().get(key, lo)))
        self._fields[key] = w
        return w

    def _dspin(self, key: str) -> QDoubleSpinBox:
        lo, hi, step = _SPIN_FLOAT[key]
        w = QDoubleSpinBox()
        w.setRange(lo, hi)
        w.setSingleStep(step)
        w.setDecimals(2)
        w.setValue(float(load_config().get(key, lo)))
        self._fields[key] = w
        return w

    def _model_group(self) -> QGroupBox:
        g = QGroupBox("Model & device")
        f = QFormLayout(g)

        cur = load_config()["model_name"]
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        for name, size, _note in cli._MODELS:
            self.model_combo.addItem(f"{name}  ({size})")
        if not any(cur in self.model_combo.itemText(i)
                   for i in range(self.model_combo.count())):
            self.model_combo.addItem(cur)
        self.model_combo.setCurrentText(
            next((self.model_combo.itemText(i)
                  for i in range(self.model_combo.count())
                  if self.model_combo.itemText(i).startswith(cur)), cur))
        self._fields["model_name"] = self.model_combo

        self.device_combo = QComboBox()
        self.device_combo.addItems(["auto", "cuda", "cpu"])
        self.device_combo.setCurrentText(str(load_config().get("device", "auto")))
        self._fields["device"] = self.device_combo

        f.addRow("Model:", self.model_combo)
        f.addRow("Device:", self.device_combo)
        f.addRow("Language:", self._line("language"))
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
        self._fields["hallucination_tails"] = w
        f.addRow("Hallucination tails (one per line):", w)
        return g

    # ---- values <-> widgets ----------------------------------------------------
    def _value_for(self, key: str, widget: QWidget):
        if isinstance(widget, QComboBox):
            text = widget.currentText().strip()
            if key == "model_name":
                # "small.en  (484 MB)" -> "small.en"
                return text.split("  (")[0].strip()
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
            if key == "model_name" and not widget.isEditable():
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

    def reload(self) -> None:
        """Refresh every widget from the current config (file + defaults)."""
        cfg = load_config()
        for key, widget in self._fields.items():
            if key in cfg:
                self._set_widget(key, widget, cfg[key])
        self.status_label.setText("Settings reloaded from config.")

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
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(tomlkit.dumps(doc))
        except Exception as e:
            QMessageBox.critical(self, "Save failed",
                                 f"Could not write {path}:\n{e}")
            return
        self.status_label.setText(f"Saved to {path} — applies to the next session.")

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

    def _update_status(self) -> None:
        try:
            p = self._tays("status", "--json")
            st = json.loads(p.stdout)
        except Exception:
            self.status_label.setText("status: (unavailable)")
            return
        if st.get("running"):
            self.status_label.setText(
                f"● Listening — {st.get('model')} on {st.get('device')} "
                f"(pid {st.get('pid')})")
            self.session_btn.setText("Stop")
        else:
            self.status_label.setText(f"● Stopped — {st.get('model')}")
            self.session_btn.setText("Start")

    def _session_clicked(self) -> None:
        try:
            p = self._tays("toggle")
            detail = (p.stdout or p.stderr).strip().splitlines()
            if detail:
                self.status_label.setText(detail[-1])
        except Exception as e:
            QMessageBox.warning(self, "Session", f"toggle failed: {e!r}")
        self._update_status()


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    win = SettingsWindow()
    win.resize(640, 720)
    win.show()
    return app.exec()

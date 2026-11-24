// SPDX-License-Identifier: MIT
// type-as-you-speak — Plasma 6 panel applet.
//
// The icon is always present: grey while the dictation session is stopped,
// red while it is live. Both icons are installed into the icon theme
// (hicolor) — that is where Plasma looks for applet icons.
//
// Left-click: status (model + where it is running) with Start/Stop,
// Settings, and — when an action fails — the reason. Right-click:
// Start/Stop + Settings, nothing else.
//
// State is polled from `tays status --json` every two seconds, so the icon
// mirrors a session started from anywhere (CLI, GUI, or here).
//
// Commands run through Plasma's "executable" data source, which runs each
// source through a shell (KProcess::setShellCommand). The engine does not
// re-run a source string it has already connected, so every run gets a
// UNIQUE source: a trailing shell comment (` #123`) is ignored by the shell
// but makes the source unique — `tays toggle #42` still runs `tays toggle`.
//
// Settings open via `tays gui --detach`: the CLI launches the window in its
// own session and returns at once, so this applet is never held "busy" for
// the lifetime of the window. A 20-second watchdog clears `busy` anyway —
// the buttons must never die.

import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PlasmaComponents3
import org.kde.plasma.plasma5support as Plasma5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    // ----- state -------------------------------------------------------------
    property bool running: false
    property bool busy: false            // a start/stop/settings command is in flight
    property bool statusOk: false        // the last status poll produced JSON
    property string detail: ""          // e.g. "medium.en on NVIDIA GeForce RTX 5090 (CUDA)"
    property string lastError: ""       // shown in the popup when an action fails
    property int nonce: 0

    // ----- command resolution ------------------------------------------------
    // The applet is installed under $HOME/.local/share/plasma/plasmoids/, so
    // $HOME is derivable from this file's own URL (QML itself cannot read
    // environment variables).
    function homePath() {
        const parts = Qt.resolvedUrl.toString().replace("file://", "").split("/");
        const i = parts.indexOf(".local");
        if (i > 1) {
            return "/" + parts.slice(0, i).join("/");
        }
        return "";
    }

    property int cmdIndex: 0

    function candidateCommands() {
        const list = [];
        const home = root.homePath();
        if (home.length > 0) {
            list.push(home + "/.local/share/type-as-you-speak/venv/bin/python -m type_as_you_speak");
            list.push(home + "/.local/bin/tays");
        }
        list.push("$HOME/.local/bin/tays");
        list.push("tays");
        return list;
    }

    function baseCommand() {
        const list = candidateCommands();
        return list[root.cmdIndex % list.length];
    }

    // ----- command runner ------------------------------------------------------
    Plasma5Support.DataSource {
        id: exec
        engine: "executable"
        connectedSources: []

        onNewData: function(source, data) {
            // Pull the JSON line out of the payload (keys: "stdout",
            // "stderr", "exit code", "exit status").
            let json = "";
            for (const k in data) {
                if (String(k) === "exit code" || String(k) === "exit status") continue;
                const lines = String(data[k]).split("\n");
                for (let i = 0; i < lines.length && json.length === 0; i++) {
                    const v = lines[i].trim();
                    if (v.length === 0 || v.charAt(0) !== "{") continue;
                    try { JSON.parse(v); json = v; } catch (e) { /* not JSON */ }
                }
            }

            if (String(source).indexOf(" status --json") !== -1) {
                root.handleStatus(json);
                return;
            }

            // One-shot actions (toggle / gui).
            const exit = data["exit code"] === undefined ? -1 : parseInt(data["exit code"], 10);
            const what = String(source).indexOf(" toggle") !== -1
                ? i18n("Start/Stop") : i18n("Settings");
            if (exit === 0) {
                root.lastError = "";
                console.log("type-as-you-speak applet: " + what + " ok");
            } else {
                let msg = "";
                try {
                    const err = String(data["stderr"] || "").trim();
                    if (err.length > 0) {
                        msg = " — " + err.split("\n").pop().slice(0, 120);
                    }
                } catch (e) {}
                root.lastError = i18n("%1 failed (exit code %2).", what, exit) + msg;
                console.warn("type-as-you-speak applet: " + what + " exit=" + exit +
                             " out=" + String(data["stdout"] || "").slice(0, 200));
            }
            root.busy = false;
        }
    }

    // Every run gets a unique source string (see the header comment).
    function runOnce(cmd) {
        root.nonce = (root.nonce + 1) % 1000000;
        const src = cmd + " #" + root.nonce;
        exec.disconnectSource(src);
        exec.connectSource(src);
    }

    // Poll the session state (each poll is a fresh run — the engine will not
    // re-run a source it has seen before).
    Timer {
        id: pollTimer
        interval: 2000
        running: true
        repeat: true
        onTriggered: {
            if (!root.busy) {
                runOnce(root.baseCommand() + " status --json");
            }
        }
    }

    // If a command never reports back, don't leave the applet stuck — the
    // buttons must stay usable.
    Timer {
        id: busyWatchdog
        interval: 20000
        running: root.busy
        onTriggered: {
            root.busy = false;
            console.warn("type-as-you-speak applet: command timed out — clearing busy");
        }
    }

    function handleStatus(json) {
        let st = null;
        if (json.length > 0) {
            try { st = JSON.parse(json); } catch (e) { st = null; }
        }
        if (st !== null) {
            const was = root.running;
            root.statusOk = true;
            root.running = !!st["running"];
            root.detail = root.describe(st);
            if (was !== root.running) {
                console.log("type-as-you-speak applet: " +
                            (root.running ? "RUNNING" : "stopped") + " — " + root.detail);
            }
        } else {
            if (root.statusOk) {
                console.warn("type-as-you-speak applet: status poll failed — trying next candidate");
            }
            root.statusOk = false;
            root.detail = "";
            root.cmdIndex = (root.cmdIndex + 1) % candidateCommands().length;
        }
    }

    function describe(st) {
        const model = st["model"] || "?";
        const dev = String(st["device"] || "?");
        let where;
        if (dev === "cuda" || dev === "rocm") {
            where = (st["gpu"] ? st["gpu"] + " " : "") + "(" + dev.toUpperCase() + ")";
        } else if (dev === "cpu") {
            where = st["cpu"] ? st["cpu"] + " (CPU)" : i18n("CPU");
        } else {
            where = dev + (st["cpu"] ? " — " + st["cpu"] : "");
        }
        if (st["running"]) {
            return i18n("%1 on %2", model, where);
        }
        return i18n("%1 · %2", model, where);
    }

    // ----- actions -------------------------------------------------------------
    function toggle() {
        if (root.busy) return;
        root.busy = true;
        runOnce(root.baseCommand() + " toggle");
    }

    function runGui() {
        if (root.busy) return;
        root.busy = true;
        runOnce(root.baseCommand() + " gui --detach");
    }

    // ----- look ------------------------------------------------------------------
    Plasmoid.icon: root.running ? "type-as-you-speak-active" : "type-as-you-speak"
    Plasmoid.status: root.running
        ? PlasmaCore.Types.ActiveStatus
        : PlasmaCore.Types.PassiveStatus

    toolTipMainText: i18n("type-as-you-speak")
    toolTipSubText: {
        if (root.running) {
            return i18n("Listening — %1", root.detail);
        }
        return root.statusOk
            ? i18n("Stopped — %1", root.detail)
            : i18n("Stopped (status unavailable)");
    }

    // ----- right-click menu (kept deliberately short) -------------------------
    Plasmoid.contextualActions: [
        PlasmaCore.Action {
            text: root.running ? i18n("Stop dictation") : i18n("Start dictation")
            icon.name: root.running ? "media-playback-stop" : "media-record"
            onTriggered: root.toggle()
        },
        PlasmaCore.Action {
            text: i18n("Settings…")
            icon.name: "configure"
            onTriggered: root.runGui()
        }
    ]

    Component.onCompleted: {
        // No applet-specific configuration UI; drop the generic entry.
        Plasmoid.removeInternalAction("configure");
    }

    // ----- left-click popup (compact) -------------------------------------------
    fullRepresentation: Item {
        implicitWidth: Kirigami.Units.gridUnit * 24
        implicitHeight: Kirigami.Units.gridUnit * 13

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.smallSpacing * 2
            spacing: Kirigami.Units.smallSpacing

            RowLayout {
                spacing: Kirigami.Units.smallSpacing
                Rectangle {
                    width: Kirigami.Units.gridUnit / 2
                    height: Kirigami.Units.gridUnit / 2
                    radius: width / 2
                    color: root.running ? "#E2574C" : "#8A8A9C"
                }
                PlasmaComponents3.Label {
                    text: root.running ? i18n("Listening") : i18n("Stopped")
                    font.bold: true
                    Layout.fillWidth: true
                }
            }

            PlasmaComponents3.Label {
                text: root.statusOk && root.detail.length > 0
                    ? root.detail
                    : (root.statusOk
                        ? i18n("checking status…")
                        : i18n("No status yet — try 'tays status' in a terminal."))
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                opacity: 0.85
            }

            PlasmaComponents3.Button {
                text: root.running ? i18n("Stop") : i18n("Start")
                Layout.fillWidth: true
                implicitHeight: Kirigami.Units.gridUnit * 4
                padding: Kirigami.Units.smallSpacing / 2
                onClicked: root.toggle()
            }

            PlasmaComponents3.Button {
                text: i18n("Settings…")
                Layout.fillWidth: true
                implicitHeight: Kirigami.Units.gridUnit * 4
                padding: Kirigami.Units.smallSpacing / 2
                onClicked: root.runGui()
            }

            PlasmaComponents3.Label {
                visible: root.lastError.length > 0
                text: root.lastError
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                color: "#B04A42"
                font.pixelSize: Math.floor(Kirigami.Units.fontPixelSize) - 1
            }

            PlasmaComponents3.LinkButton {
                text: "github.com/iller7/type-as-you-speak"
                Layout.alignment: Qt.AlignLeft
                Layout.topMargin: Kirigami.Units.smallSpacing / 2
                onClicked: Qt.openUrlExternally("https://github.com/iller7/type-as-you-speak")
            }
        }
    }
}

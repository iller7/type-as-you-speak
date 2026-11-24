// SPDX-License-Identifier: AGPL-3.0-only
// type-as-you-speak — Plasma 6 panel applet.
//
// The icon is always present: grey while the dictation session is stopped,
// red while it is live (both are installed into the icon theme — see
// install.sh / the README). Left-click shows the status popup
// (start/stop, settings); right-click gives the full menu. State is polled
// from `tays status --json` every two seconds, so the icon mirrors a
// session started from anywhere (CLI, GUI, or here).
//
// Commands run through Plasma's "executable" data source (KDE's
// KProcess::setShellCommand — the command goes through a shell, so $HOME
// and friends work). plasmashell's PATH does not include ~/.local/bin, so
// the applet tries the standard install locations in order (absolute
// home path derived from this file's own location, then $HOME, then bare
// `tays`) and remembers whichever one answers.
//
// `gui --detach` is used for the settings window: the CLI launches the
// window in its own session and returns at once, so this applet is never
// blocked for the lifetime of the window.

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
    property bool busy: false            // a start/stop command is in flight
    property bool statusOk: false        // last status poll succeeded
    property string detail: ""          // "small.en on NVIDIA GeForce RTX 5090 (CUDA)"
    property string lastError: ""       // shown in the popup when an action fails
    property string popupView: "status" // "status" | "about"

    // ----- command resolution ------------------------------------------------
    // The applet is installed under $HOME/.local/share/plasma/plasmoids/, so
    // $HOME is derivable from this file's own URL — no environment access
    // needed from QML.
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
        let cfg = "";
        try {
            cfg = String(Plasmoid.configuration.command || "");
        } catch (e) {
            // no configuration entry — that's fine
        }
        if (cfg.length > 0) {
            list.push(cfg);
        }
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
            if (String(source).indexOf(" status --json") !== -1) {
                root.handleStatus(data);
                return;
            }
            // One-shot actions (start/stop/gui): show failure instead of
            // silently doing nothing.
            const exit = parseInt(data["exit code"], 10);
            if (exit !== 0) {
                const what = String(source).replace(root.baseCommand(), "").trim();
                root.lastError = i18n("‘%1’ finished with code %2 — run it in a terminal for details.", what, exit);
                console.warn("type-as-you-speak applet: command exited " + exit);
            } else {
                root.lastError = "";
            }
            root.busy = false;
        }

        function run(cmd) {
            disconnectSource(cmd);
            connectSource(cmd);
        }
    }

    // Poll session state (this also self-heals the command candidate list).
    Timer {
        id: pollTimer
        interval: 2000
        running: true
        repeat: true
        onTriggered: {
            if (!root.busy) {
                exec.run(root.baseCommand() + " status --json");
            }
        }
    }

    function handleStatus(data) {
        const exit = parseInt(data["exit code"], 10);
        let st = null;
        if (exit === 0) {
            for (const k in data) {
                if (String(k) === "exit code") continue;
                const line = String(data[k]).trim();
                if (line.length === 0) continue;
                try {
                    st = JSON.parse(line);
                    break;
                } catch (e) {
                    // not JSON — keep looking
                }
            }
        }
        if (st !== null) {
            root.statusOk = true;
            root.running = !!st["running"];
            root.detail = root.describe(st);
        } else {
            // This candidate failed — try the next one on the next poll.
            root.statusOk = false;
            root.cmdIndex = (root.cmdIndex + 1) % candidateCommands().length;
        }
    }

    function describe(st) {
        const model = st["model"] || "?";
        const dev = String(st["device"] || "?");
        if (st["running"]) {
            let on;
            if (st["gpu"]) {
                on = st["gpu"] + " (" + dev.toUpperCase() + ")";
            } else if (dev === "cpu") {
                on = i18n("CPU (int8)");
            } else {
                on = dev.toUpperCase();
            }
            return i18n("%1 on %2", model, on);
        }
        return i18n("%1 (device: %2)", model, dev);
    }

    // ----- actions -------------------------------------------------------------
    function toggle() {
        if (root.busy) return;
        root.busy = true;
        exec.run(root.baseCommand() + " toggle");
    }

    function runGui() {
        if (root.busy) return;
        root.busy = true;
        // --detach: the CLI returns at once, so `busy` clears even while
        // the settings window stays open.
        exec.run(root.baseCommand() + " gui --detach");
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

    // ----- right-click menu ---------------------------------------------------------
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
        },
        PlasmaCore.Action {
            text: i18n("Status")
            icon.name: "system-information"
            onTriggered: {
                root.popupView = "status";
                Plasmoid.expanded = true;
            }
        },
        PlasmaCore.Action {
            text: i18n("About")
            icon.name: "help-about"
            onTriggered: {
                root.popupView = "about";
                Plasmoid.expanded = true;
            }
        }
    ]

    Component.onCompleted: {
        // No applet-specific configuration UI; drop the generic entry.
        Plasmoid.removeInternalAction("configure");
    }

    // ----- left-click popup ---------------------------------------------------------
    fullRepresentation: Item {
        implicitWidth: Kirigami.Units.gridUnit * 30
        implicitHeight: Kirigami.Units.gridUnit * 15

        // ---- status view ----
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.smallSpacing
            visible: root.popupView === "status"

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
                text: root.detail.length > 0 ? root.detail : i18n("checking status…")
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                opacity: 0.85
            }
            PlasmaComponents3.Button {
                text: root.running ? i18n("Stop") : i18n("Start")
                Layout.fillWidth: true
                onClicked: root.toggle()
            }
            PlasmaComponents3.Button {
                text: i18n("Settings…")
                Layout.fillWidth: true
                onClicked: root.runGui()
            }
            PlasmaComponents3.Label {
                visible: root.lastError.length > 0
                text: root.lastError
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                color: "#B04A42"
                font.pixelSize: Kirigami.Units.fontPixelSize - 1
            }
        }

        // ---- about view ----
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.smallSpacing
            visible: root.popupView === "about"

            PlasmaComponents3.Label {
                text: i18n("type-as-you-speak")
                font.bold: true
            }
            PlasmaComponents3.Label {
                text: i18n("Speak, and it types into your window — Mac-like live dictation for Linux.")
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                opacity: 0.85
            }
            PlasmaComponents3.Button {
                text: i18n("GitHub")
                Layout.alignment: Qt.AlignLeft
                onClicked: Qt.openUrlExternally("https://github.com/iller7/type-as-you-speak")
            }
        }
    }
}

// SPDX-License-Identifier: AGPL-3.0-only
// type-as-you-speak — Plasma 6 panel applet.
//
// The icon is always present: grey while the dictation session is stopped,
// red while it is live. Both icons are installed into the icon theme
// (hicolor) — that is where Plasma looks for applet icons.
//
// Clicking the icon (left or right) opens one short menu: Start/Stop,
// Settings…, and the project page. There is deliberately no popup: the
// state is carried by the icon and the tooltip, and command failures are
// logged to the journal instead of shown in a window.
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
// own session and returns at once. The GUI is single-instance, so a second
// launch just brings the existing window to the front.

import QtQuick
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as Plasma5Support

PlasmoidItem {
    id: root

    // ----- state -------------------------------------------------------------
    property bool running: false
    property string phase: "stopped"     // stopped | preparing | listening
    property bool statusOk: false        // the last status poll produced JSON
    property string detail: ""          // e.g. "medium.en on NVIDIA GeForce RTX 5090 (CUDA)"
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

            // One-shot actions (toggle / gui): there is no popup to show a
            // failure in, so record it in the journal and move on.
            const exit = data["exit code"] === undefined ? -1 : parseInt(data["exit code"], 10);
            const what = String(source).indexOf(" toggle") !== -1
                ? i18n("Start/Stop") : i18n("Settings");
            if (exit === 0) {
                console.log("type-as-you-speak applet: " + what + " ok");
            } else {
                let err = "";
                try { err = String(data["stderr"] || "").trim().split("\n").pop(); } catch (e) {}
                console.warn("type-as-you-speak applet: " + what + " failed (exit " + exit + ")"
                             + (err.length > 0 ? " — " + err.slice(0, 200) : ""));
            }
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
        onTriggered: runOnce(root.baseCommand() + " status --json")
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
            root.phase = root.running
                ? (st["state"] === "listening" ? "listening" : "preparing")
                : "stopped";
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
        runOnce(root.baseCommand() + " toggle");
    }

    function runGui() {
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
            return root.phase === "listening"
                ? i18n("Listening — %1", root.detail)
                : i18n("Preparing — %1", root.detail);
        }
        return root.statusOk
            ? i18n("Stopped — %1", root.detail)
            : i18n("Stopped (status unavailable)");
    }

    // ----- menu (both left- and right-click open it) -----------------------------
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
            text: "github.com/iller7/type-as-you-speak"
            icon.name: "applications-internet"
            onTriggered: Qt.openUrlExternally("https://github.com/iller7/type-as-you-speak")
        }
    ]

    Component.onCompleted: {
        // No applet-specific configuration UI; drop the generic entry.
        Plasmoid.removeInternalAction("configure");
    }
}

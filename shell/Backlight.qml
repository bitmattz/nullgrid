pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

// Screen brightness of the first backlight device (laptops); changed through brightnessctl,
// which works without root via logind.
Singleton {
    id: root
    property string dir: ""
    readonly property bool available: dir !== ""
    property real percent: NaN

    function refresh() {
        if (!available) return
        cur.reload(); max.reload()
        const m = parseFloat(max.text())
        root.percent = m > 0 ? 100 * parseFloat(cur.text()) / m : NaN
    }
    function step(delta) {
        Quickshell.execDetached(["brightnessctl", "-q", "set", Math.abs(delta) + "%" + (delta > 0 ? "+" : "-")])
        refreshSoon.restart()
    }

    FileView { id: cur; path: root.dir ? root.dir + "/brightness" : ""; blockLoading: true; printErrors: false }
    FileView { id: max; path: root.dir ? root.dir + "/max_brightness" : ""; blockLoading: true; printErrors: false }
    Timer { id: refreshSoon; interval: 150; onTriggered: root.refresh() }
    Timer { interval: 5000; running: root.available; repeat: true; onTriggered: root.refresh() }

    Process {
        running: true
        command: ["sh", "-c", "for d in /sys/class/backlight/*; do [ -r \"$d/brightness\" ] && echo \"$d\" && break; done"]
        stdout: StdioCollector { onStreamFinished: { root.dir = text.trim(); root.refresh() } }
    }
}

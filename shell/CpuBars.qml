import QtQuick

// One segmented bar per core, the total, the load average and the core count.
HudPanel {
    title: "CPU"
    caption: Sys.cores.length + " CORES"
    implicitWidth: 360; implicitHeight: 160

    Row {
        id: stats
        spacing: 16
        NgText { text: Math.round(Sys.cpu) + "%"; font.family: Theme.fontDisplay; font.pixelSize: 20; font.bold: true }
        Column {
            NgText { label: true; text: "LOAD" }
            NgText { mono: true; text: Sys.load.map(v => v.toFixed(2)).join("  "); font.pixelSize: 12 }
        }
    }

    Row {
        id: bars
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom; top: stats.bottom; topMargin: 8 }
        spacing: Math.max(2, Math.min(8, (width - n * 6) / Math.max(1, n)))
        readonly property int n: Math.min(Sys.cores.length, 32)
        readonly property int segments: 10
        Repeater {
            model: bars.n
            Column {
                required property int index
                readonly property real value: Sys.cores[index] || 0
                width: Math.max(4, Math.min(18, (bars.width - (bars.n - 1) * bars.spacing) / Math.max(1, bars.n)))
                spacing: 2
                anchors.bottom: parent.bottom
                Repeater {
                    model: bars.segments
                    Rectangle {
                        required property int index
                        readonly property bool lit: (bars.segments - index) <= Math.ceil(parent.value / 100 * bars.segments)
                        width: parent.width
                        height: (bars.height - (bars.segments - 1) * 2) / bars.segments
                        color: lit ? (bars.segments - index > 8 ? Theme.secondary : Theme.primary) : Theme.alpha(Theme.dim, 0.18)
                    }
                }
            }
        }
    }
}

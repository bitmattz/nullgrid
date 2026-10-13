import QtQuick

// A dot matrix of recent CPU activity: one column per sample, lit up to the load.
HudPanel {
    id: panel
    title: "ACTIVITY"
    caption: "T-" + cols + "s"
    implicitWidth: 260; implicitHeight: 120
    readonly property int cols: 24
    readonly property int rows: 6

    Grid {
        id: grid
        anchors.centerIn: parent
        columns: panel.cols
        rowSpacing: 4; columnSpacing: 4
        readonly property var history: Sys.cpuHistory.slice(-panel.cols)
        Repeater {
            model: grid.columns * panel.rows
            Rectangle {
                required property int index
                readonly property int col: index % grid.columns
                readonly property int row: Math.floor(index / grid.columns)
                readonly property real v: grid.history[col - (grid.columns - grid.history.length)] ?? -1
                readonly property bool lit: v >= 0 && (5 - row) < Math.max(1, Math.ceil(v / 100 * 6))
                width: 5; height: 5
                color: lit ? (row === 0 ? Theme.secondary : Theme.primary) : Theme.alpha(Theme.dim, 0.22)
            }
        }
    }
}

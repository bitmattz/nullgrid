import QtQuick
import Quickshell
import Quickshell.Wayland

// The desktop HUD widgets placed at one screen position ([widgets] in nullgrid.toml), on the
// layer under the windows. shell.qml makes one per position that has a visible widget.
PanelWindow {
    id: hud
    required property string position
    readonly property var names: ["ram_gauge", "cpu_bars", "activity_grid", "net_graph", "workspace_strip"]
        .filter(n => Theme.widget(n).visible && Theme.widget(n).position === position)
    readonly property bool hasTop: position.startsWith("top")
    readonly property bool hasBottom: position.startsWith("bottom")
    readonly property bool hasLeft: position.endsWith("left")
    readonly property bool hasRight: position.endsWith("right")

    visible: names.length > 0
    anchors { top: hasTop; bottom: hasBottom; left: hasLeft; right: hasRight }
    margins { top: 14; bottom: 14; left: 14; right: 14 }
    implicitWidth: flow.width
    implicitHeight: flow.implicitHeight
    exclusiveZone: 0
    color: "transparent"
    WlrLayershell.namespace: "nullgrid-hud"
    WlrLayershell.layer: WlrLayer.Bottom
    mask: Region { item: flow }

    Flow {
        id: flow
        width: 628
        spacing: 8
        layoutDirection: hud.hasRight ? Qt.RightToLeft : Qt.LeftToRight
        Repeater {
            model: hud.names
            Loader {
                required property string modelData
                source: ({ ram_gauge: "RamGauge.qml", cpu_bars: "CpuBars.qml", activity_grid: "ActivityGrid.qml",
                           net_graph: "NetGraph.qml", workspace_strip: "WorkspaceStrip.qml" })[modelData]
            }
        }
    }
}

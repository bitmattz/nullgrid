import QtQuick
import Quickshell
import Quickshell.Wayland

// The left dock: the start button, pinned apps as circular neon buttons, and the workspaces
// (a dot each, plus the number of the current one).
PanelWindow {
    id: dock
    property bool right: Theme.widget("dock").position === "right"

    anchors { left: !dock.right; right: dock.right }
    margins { left: dock.right ? 0 : 6; right: dock.right ? 6 : 0 }
    implicitWidth: 60
    implicitHeight: column.implicitHeight + 36
    exclusiveZone: implicitWidth + 6
    color: "transparent"
    WlrLayershell.namespace: "nullgrid-dock"
    WlrLayershell.layer: WlrLayer.Top

    Chamfer { anchors.fill: parent; cut: 14 }
    Rectangle {  // a short accent rail on the outer edge
        x: dock.right ? parent.width - 3 : 0
        y: 24; width: 3; height: 46
        color: Theme.secondary
    }

    Column {
        id: column
        anchors.centerIn: parent
        spacing: 10

        DockButton {
            label: "Menu"
            active: Ui.menuOpen
            onClicked: Ui.toggleMenu()
            LatticeLogo { anchors.centerIn: parent; width: 20; color: Theme.primary }
        }

        Rectangle { width: 30; height: 1; color: Theme.alpha(Theme.dim, 0.5); anchors.horizontalCenter: parent.horizontalCenter }

        Repeater {
            model: Ui.pinned
            DockButton {
                required property var modelData
                label: modelData.label
                active: Wm.activeApp === modelData.app
                running: Running.apps.indexOf(modelData.app) >= 0
                onClicked: Wm.exec(modelData.cmd)
                NgIcon { anchors.centerIn: parent; name: modelData.icon; size: 20; color: parent.active ? Theme.text : Theme.primary }
            }
        }

        Rectangle { width: 30; height: 1; color: Theme.alpha(Theme.dim, 0.5); anchors.horizontalCenter: parent.horizontalCenter }

        Grid {  // workspace dots
            anchors.horizontalCenter: parent.horizontalCenter
            columns: 2
            spacing: 6
            Repeater {
                model: Wm.workspaces
                Rectangle {
                    required property var modelData
                    width: 8; height: 8; radius: 4
                    color: modelData.focused ? Theme.primary : "transparent"
                    border.width: 1
                    border.color: modelData.urgent ? Theme.warning : modelData.occupied || modelData.focused ? Theme.primary : Theme.alpha(Theme.dim, 0.6)
                    MouseArea { anchors.fill: parent; anchors.margins: -3; onClicked: Wm.activate(modelData.id) }
                }
            }
        }

        Item {  // number of the current workspace
            width: 40; height: 30
            anchors.horizontalCenter: parent.horizontalCenter
            Chamfer { anchors.fill: parent; cut: 7; fill: Theme.alpha(Theme.secondary, 0.18); stroke: Theme.secondary }
            NgText {
                anchors.centerIn: parent
                text: String(Wm.focused).padStart(2, "0")
                font.family: Theme.fontDisplay
                font.pixelSize: 14
                font.bold: true
                color: Theme.text
            }
        }
    }

    component DockButton: Item {
        id: button
        property string label
        property bool active: false
        property bool running: false
        signal clicked()
        width: 42; height: 42

        Rectangle {
            id: ring
            anchors.fill: parent
            radius: width / 2
            color: button.active ? Theme.alpha(Theme.primary, 0.2) : mouse.containsMouse ? Theme.alpha(Theme.primary, 0.1) : "transparent"
            border.width: button.active ? 2 : 1
            border.color: button.active || mouse.containsMouse ? Theme.primary : Theme.alpha(Theme.primary, 0.45)
            Behavior on color { ColorAnimation { duration: Theme.durations.fast } }
        }
        Hatch {  // the active state is hatched, inside the circle
            visible: button.active
            anchors.fill: parent; anchors.margins: 6
            spacing: 5
            color: Theme.alpha(Theme.primary, 0.25)
            layer.enabled: false
        }
        Rectangle {  // running indicator
            visible: button.running && !button.active
            width: 4; height: 4; radius: 2
            color: Theme.secondary
            anchors { right: parent.right; verticalCenter: parent.verticalCenter; rightMargin: -6 }
        }
        MouseArea {
            id: mouse
            anchors.fill: parent
            hoverEnabled: true
            onClicked: button.clicked()
        }
    }
}

import QtQuick

// Workspaces as numbered panels; the active one is hatched.
HudPanel {
    title: "WORKSPACES"
    caption: Wm.name
    implicitWidth: 628; implicitHeight: 74

    Row {
        anchors.fill: parent
        spacing: 6
        Repeater {
            model: Wm.workspaces
            Item {
                required property var modelData
                width: (parent.width - (Wm.workspaces.length - 1) * 6) / Wm.workspaces.length
                height: parent.height
                Chamfer {
                    anchors.fill: parent; cut: 6
                    fill: modelData.focused ? Theme.alpha(Theme.primary, 0.15) : "transparent"
                    stroke: modelData.focused ? Theme.primary : Theme.alpha(Theme.dim, modelData.occupied ? 0.9 : 0.35)
                }
                Hatch { anchors.fill: parent; anchors.margins: 3; visible: modelData.focused; spacing: 6 }
                NgText {
                    anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                    text: String(modelData.id).padStart(2, "0")
                    font.family: Theme.fontDisplay; font.pixelSize: 12; font.bold: true
                    color: modelData.focused ? Theme.text : modelData.occupied ? Theme.primary : Theme.dim
                }
                Rectangle {
                    visible: modelData.occupied
                    anchors { right: parent.right; rightMargin: 8; verticalCenter: parent.verticalCenter }
                    width: 5; height: 5
                    color: modelData.urgent ? Theme.warning : Theme.secondary
                }
                MouseArea { anchors.fill: parent; onClicked: Wm.activate(modelData.id) }
            }
        }
    }
}

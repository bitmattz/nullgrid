import QtQuick

// A HUD widget frame: chamfered panel, a title with an accent tick, an optional caption on the right.
Item {
    id: root
    property string title
    property string caption
    default property alias content: body.data
    Chamfer { anchors.fill: parent; cut: 12; fill: Theme.alpha(Theme.surface, Theme.surfaceOpacity * 0.85) }
    Rectangle { x: 14; y: 13; width: 3; height: 10; color: Theme.secondary }
    NgText { x: 22; y: 9; height: 18; label: true; text: root.title; color: Theme.primary }
    NgText { anchors.right: parent.right; anchors.rightMargin: 16; y: 9; height: 18; label: true; text: root.caption }
    Item {
        id: body
        anchors { fill: parent; topMargin: 32; leftMargin: 14; rightMargin: 14; bottomMargin: 12 }
    }
}

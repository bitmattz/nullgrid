import QtQuick

// A small chamfered text button for the pickers.
Item {
    id: btn
    property string text
    property bool warn: false
    signal clicked()
    implicitWidth: label.implicitWidth + 22
    implicitHeight: 26
    width: implicitWidth; height: implicitHeight

    Chamfer {
        anchors.fill: parent
        cut: 6
        fill: area.containsMouse ? Theme.alpha(btn.warn ? Theme.secondary : Theme.primary, 0.18) : "transparent"
        stroke: btn.warn ? Theme.secondary : Theme.alpha(Theme.primary, 0.7)
    }
    NgText {
        id: label
        anchors.centerIn: parent
        text: btn.text
        mono: true
        font.pixelSize: 10
        font.letterSpacing: 1
        color: btn.warn ? Theme.secondary : Theme.primary
    }
    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        onClicked: { Sfx.play("button_click"); btn.clicked() }
    }
}

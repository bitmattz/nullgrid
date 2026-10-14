import QtQuick
import Quickshell
import Quickshell.Wayland

// A HUD popup next to the bar's right end (the Wi-Fi and Bluetooth pickers). A chamfered panel
// with a title; Esc or a click outside closes it. It takes the keyboard while open, so a
// password can be typed into it.
PanelWindow {
    id: pop
    property string name            // Ui.picker value that shows this popup
    property string title
    property string subtitle
    property bool switchOn: false   // the switch in the title row (radio on/off)
    property bool switchVisible: true
    signal switchToggled()
    default property alias content: body.data

    visible: Ui.picker === name
    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    color: "transparent"
    WlrLayershell.namespace: "nullgrid-picker"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

    readonly property bool barTop: Theme.widget("bar").position === "top"

    MouseArea { anchors.fill: parent; onClicked: Ui.picker = "" }   // click outside closes

    Item {
        id: panel
        width: 400
        height: Math.min(pop.height - 100, header.height + body.childrenRect.height + 34)
        x: parent.width - width - 12
        y: pop.barTop ? 42 : parent.height - height - 42
        focus: true
        Keys.onEscapePressed: Ui.picker = ""
        MouseArea { anchors.fill: parent }   // swallow clicks inside

        Chamfer { anchors.fill: parent; cut: 14; fill: Theme.alpha(Theme.surface, 0.99); stroke: Theme.primary; strokeWidth: 1.5 }
        Rectangle { x: 0; y: 22; width: 3; height: 40; color: Theme.secondary }

        Item {
            id: header
            x: 18; y: 12; width: parent.width - 36; height: 44
            NgText {
                id: titleText
                text: pop.title
                font.family: Theme.fontDisplay
                font.pixelSize: 15
                font.letterSpacing: 2
                color: Theme.primary
            }
            NgText { anchors.top: titleText.bottom; text: pop.subtitle; label: true; width: parent.width - 70 }
            // ON/OFF switch: a segmented two-cell toggle
            Item {
                visible: pop.switchVisible
                anchors { right: parent.right; verticalCenter: titleText.verticalCenter }
                width: 64; height: 20
                Row {
                    anchors.fill: parent
                    spacing: 2
                    Repeater {
                        model: ["OFF", "ON"]
                        Rectangle {
                            required property string modelData
                            required property int index
                            readonly property bool active: (index === 1) === pop.switchOn
                            width: 31; height: 20
                            color: active ? (index === 1 ? Theme.primary : Theme.alpha(Theme.dim, 0.5)) : "transparent"
                            border.color: Theme.alpha(Theme.primary, 0.5)
                            border.width: 1
                            NgText {
                                anchors.centerIn: parent
                                text: modelData
                                mono: true
                                font.pixelSize: 10
                                color: parent.active ? Theme.bg : Theme.dim
                            }
                        }
                    }
                }
                MouseArea { anchors.fill: parent; onClicked: { Sfx.play("button_click"); pop.switchToggled() } }
            }
        }

        Flickable {
            id: flick
            x: 14; y: header.y + header.height + 8
            width: parent.width - 28
            height: parent.height - y - 14
            contentHeight: body.childrenRect.height
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            Column { id: body; width: flick.width; spacing: 4 }
        }
    }
}

import QtQuick
import Quickshell

// Bluetooth picker, opened by clicking the bar's Bluetooth icon. Paired devices (click:
// connect / disconnect, battery when the device reports it) and devices in range (click: pair,
// trust and connect). It looks for devices while open. PIN pairing: bluetoothctl.
Popout {
    id: picker
    name: "bluetooth"
    title: "LINK // BLUETOOTH"
    subtitle: !Bt.present ? "no bluetooth adapter"
            : !Bt.on ? "bluetooth is off"
            : (Bt.paired.filter(d => d.connected).length + " connected · " + (Bt.adapter.discovering ? "scanning" : "idle"))
    switchVisible: Bt.present
    switchOn: Bt.on
    onSwitchToggled: Bt.setOn(!Bt.on)
    onVisibleChanged: Bt.scanning = visible

    component Section: NgText {
        width: parent ? parent.width : 0; height: 26
        label: true; leftPadding: 4
        verticalAlignment: Text.AlignBottom
    }

    component DeviceRow: Item {
        id: row
        required property var modelData
        readonly property var dev: modelData
        readonly property string error: Bt.errors[dev.address] || ""
        readonly property bool busy: !!Bt.pending[dev.address]
        width: parent ? parent.width : 0
        height: 34 + (error ? 16 : 0)

        Rectangle {
            anchors { fill: parent; bottomMargin: 2 }
            color: hover.containsMouse ? Theme.alpha(Theme.primary, 0.08) : "transparent"
        }
        Rectangle { visible: row.dev.connected; x: 0; y: 6; width: 3; height: 22; color: Theme.primary }
        NgIcon { x: 10; y: 8; name: "bluetooth"; size: 18; color: row.dev.connected ? Theme.primary : Theme.dim }
        NgText {
            x: 38; y: 0; height: 34; width: parent.width - 170
            text: Bt.label(row.dev)
            color: row.dev.connected ? Theme.primary : row.dev.name ? Theme.text : Theme.dim
        }
        NgText {
            anchors.right: parent.right; anchors.rightMargin: (row.dev.paired || row.dev.bonded) ? 36 : 8
            y: 0; height: 34
            mono: true; font.pixelSize: 10
            text: row.busy ? "PAIRING…"
                : (row.dev.batteryAvailable ? Math.round(row.dev.battery * 100) + "%  " : "")
                  + (row.dev.connected ? "LINKED" : Bt.kind(row.dev))
            color: row.dev.connected ? Theme.primary : Theme.dim
        }
        MouseArea {
            id: hover
            width: parent.width - ((row.dev.paired || row.dev.bonded) ? 32 : 0); height: 34
            hoverEnabled: true
            onClicked: { Sfx.play("button_click"); Bt.activate(row.dev.address) }
        }
        // forget a paired device
        Item {
            visible: row.dev.paired || row.dev.bonded
            anchors.right: parent.right; y: 4; width: 28; height: 26
            NgIcon { anchors.centerIn: parent; name: "close"; size: 12; color: forget.containsMouse ? Theme.secondary : Theme.dim }
            MouseArea { id: forget; anchors.fill: parent; hoverEnabled: true; onClicked: { Sfx.play("button_click"); Bt.forget(row.dev.address) } }
        }
        NgText {
            visible: row.error !== ""
            x: 38; y: row.height - 18; height: 14
            text: "▲ " + row.error
            mono: true; font.pixelSize: 10; color: Theme.secondary
        }
    }

    NgText {
        visible: !Bt.present
        width: parent.width; height: 48; leftPadding: 4; wrapMode: Text.WordWrap
        text: "No adapter found (or the bluetooth service isn't running)."
        mono: true; font.pixelSize: 11; color: Theme.dim
    }

    Section { visible: Bt.on && Bt.paired.length > 0; text: "PAIRED" }
    Repeater { model: Bt.on ? Bt.paired : []; delegate: DeviceRow {} }

    Section { visible: Bt.on; text: "AVAILABLE" + (Bt.adapter && Bt.adapter.discovering ? "  ·  scanning" : "") }
    Repeater { model: Bt.on ? Bt.available : []; delegate: DeviceRow {} }
    NgText {
        visible: Bt.on && Bt.available.length === 0
        width: parent.width; height: 30; leftPadding: 4
        text: "looking for devices… (put yours in pairing mode)"
        mono: true; font.pixelSize: 11; color: Theme.dim
    }

    Item {
        width: parent.width; height: 40
        PickerButton {
            anchors.right: parent.right; anchors.rightMargin: 4; y: 8
            text: "MORE: BLUETOOTHCTL"
            onClicked: { Ui.picker = ""; Wm.exec("kitty --class nullgrid-bt bluetoothctl") }
        }
    }
}

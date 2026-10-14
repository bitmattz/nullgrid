import QtQuick
import Quickshell

// Wi-Fi picker, opened by clicking the bar's Wi-Fi icon. Networks in range (scanned while open),
// connect with a click; a secured network NetworkManager doesn't know asks for its password
// inline. A connected or saved network offers disconnect / forget. Everything else: nmtui.
Popout {
    id: picker
    name: "wifi"
    title: "NETWORK // UPLINK"
    subtitle: !Net.hasWifi ? "no wi-fi adapter"
            : !Net.wifiOn ? "wi-fi is off"
            : Net.connected ? "linked: " + Net.connected.name : "not connected"
    switchVisible: Net.hasWifi
    switchOn: Net.wifiOn
    onSwitchToggled: Net.setWifi(!Net.wifiOn)

    property string expanded: ""   // the network whose row is open (password or actions)
    onVisibleChanged: { Net.scanning = visible; expanded = "" }

    // wired link
    Item {
        width: parent.width; height: Net.wired ? 30 : 0
        visible: Net.wired !== null
        NgText { x: 4; anchors.verticalCenter: parent.verticalCenter; text: "WIRED"; label: true }
        NgText {
            x: 90; anchors.verticalCenter: parent.verticalCenter
            mono: true; font.pixelSize: 12
            text: Net.wired && Net.wired.up ? "LINKED" + (Net.wired.speed ? "  " + Net.wired.speed + " Mb/s" : "") : "cable unplugged"
            color: Net.wired && Net.wired.up ? Theme.primary : Theme.dim
        }
    }

    NgText {
        visible: Net.hasWifi && Net.wifiOn && Net.networks.length === 0
        width: parent.width; height: 34
        text: "scanning…"; mono: true; font.pixelSize: 12; color: Theme.dim
        leftPadding: 4
    }

    Repeater {
        model: Net.hasWifi && Net.wifiOn ? Net.networks : []
        delegate: Item {
            id: row
            required property var modelData
            readonly property var net: modelData
            readonly property bool open: picker.expanded === net.name
            readonly property string error: Net.errors[net.name] || ""
            width: parent ? parent.width : 0
            height: 34 + (open ? 40 : 0) + (error ? 16 : 0)

            Rectangle {   // hover / open highlight with a hatched left edge for the linked one
                anchors { fill: parent; bottomMargin: 2 }
                color: hover.containsMouse || row.open ? Theme.alpha(Theme.primary, 0.08) : "transparent"
                border.color: row.open ? Theme.alpha(Theme.primary, 0.5) : "transparent"
                border.width: 1
            }
            Rectangle { visible: row.net.connected; x: 0; y: 6; width: 3; height: 22; color: Theme.primary }

            // signal: four segments
            Row {
                x: 10; y: 11; spacing: 2
                Repeater {
                    model: 4
                    Rectangle {
                        required property int index
                        width: 4; height: 4 + index * 3
                        anchors.bottom: parent.bottom
                        color: index < Net.bars(row.net) ? (row.net.connected ? Theme.primary : Theme.text) : Theme.alpha(Theme.dim, 0.35)
                    }
                }
            }
            NgText {
                x: 40; y: 0; height: 34; width: parent.width - 150
                text: row.net.name
                color: row.net.connected ? Theme.primary : Theme.text
            }
            NgIcon { visible: Net.secured(row.net); x: parent.width - 108; y: 10; name: "lock"; size: 13; color: Theme.dim }
            NgText {
                anchors.right: parent.right; anchors.rightMargin: 8; y: 0; height: 34
                mono: true; font.pixelSize: 10
                text: row.net.connected ? "LINKED" : row.net.stateChanging ? "LINKING…" : row.net.known ? "SAVED" : ""
                color: row.net.connected ? Theme.primary : Theme.dim
            }
            MouseArea {
                id: hover
                width: parent.width; height: 34
                hoverEnabled: true
                onClicked: {
                    Sfx.play("button_click")
                    if (Net.needsPassword(row.net)) {
                        picker.expanded = row.open ? "" : row.net.name    // password
                    } else if (row.net.connected || row.net.known) {
                        picker.expanded = row.open ? "" : row.net.name   // actions
                        if (!row.net.connected && !row.open) Net.connect(row.net.name)
                    } else if (Net.enterprise(row.net)) {
                        picker.expanded = row.open ? "" : row.net.name    // shows the nmtui hint
                    } else {
                        Net.connect(row.net.name)
                    }
                }
            }

            // the open row: password field, or actions, or the enterprise hint
            Item {
                visible: row.open
                x: 10; y: 34; width: parent.width - 20; height: 34

                // password
                Item {
                    visible: Net.needsPassword(row.net)
                    anchors.fill: parent
                    Chamfer {
                        width: parent.width - 96; height: 30
                        cut: 7
                        fill: Theme.alpha(Theme.bg, 0.7)
                        stroke: psk.activeFocus ? Theme.primary : Theme.alpha(Theme.dim, 0.6)
                    }
                    TextInput {
                        id: psk
                        x: 10; width: parent.width - 116; height: 30
                        verticalAlignment: TextInput.AlignVCenter
                        echoMode: TextInput.Password
                        passwordCharacter: "■"
                        color: Theme.text
                        font.family: Theme.fontMono
                        font.pixelSize: 13
                        clip: true
                        Keys.onEscapePressed: Ui.picker = ""
                        Keys.onReturnPressed: join.go()
                        Keys.onEnterPressed: join.go()
                        NgText {
                            visible: !psk.text
                            anchors.verticalCenter: parent.verticalCenter
                            text: "PASSWORD"; mono: true; font.pixelSize: 12; color: Theme.dim
                        }
                    }
                    Connections {
                        target: row
                        function onOpenChanged() { if (row.open && Net.needsPassword(row.net)) { psk.text = ""; psk.forceActiveFocus() } }
                    }
                    PickerButton {
                        id: join
                        anchors.right: parent.right; y: 2
                        text: "CONNECT"
                        function go() {
                            if (!psk.text) { Sfx.play("error"); return }
                            Net.connect(row.net.name, psk.text)
                            psk.text = ""
                            picker.expanded = ""
                        }
                        onClicked: go()
                    }
                }
                // actions for a connected or saved network
                Row {
                    visible: (row.net.known || row.net.connected) && !Net.needsPassword(row.net)
                    spacing: 8; y: 2
                    PickerButton { visible: row.net.connected; text: "DISCONNECT"; onClicked: { Net.disconnect(row.net.name); picker.expanded = "" } }
                    PickerButton { visible: !row.net.connected; text: "CONNECT"; onClicked: { Net.connect(row.net.name); picker.expanded = "" } }
                    PickerButton { text: "FORGET"; warn: true; onClicked: { Net.forget(row.net.name); picker.expanded = "" } }
                }
                // enterprise (802.1X) networks need more than a password
                NgText {
                    visible: !row.net.known && Net.enterprise(row.net)
                    height: 30; width: parent.width
                    text: "enterprise network: set it up in nmtui"
                    mono: true; font.pixelSize: 11; color: Theme.warning
                }
            }
            NgText {
                visible: row.error !== ""
                x: 40; y: row.height - 18; height: 14
                text: "▲ " + row.error
                mono: true; font.pixelSize: 10; color: Theme.secondary
            }
        }
    }

    // more: the full NetworkManager TUI (hidden networks, VPN, enterprise, static IPs)
    Item {
        width: parent.width; height: 40
        PickerButton {
            anchors.right: parent.right; anchors.rightMargin: 4; y: 8
            text: "MORE: NMTUI"
            onClicked: { Ui.picker = ""; Wm.exec("kitty --class nullgrid-net nmtui") }
        }
    }
}

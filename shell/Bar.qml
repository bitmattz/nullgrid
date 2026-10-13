import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import Quickshell.Bluetooth
import Quickshell.Networking
import Quickshell.Services.Mpris
import Quickshell.Services.Pipewire
import Quickshell.Services.SystemTray

// The status bar: mode, workspaces and window title on the left, media in the middle, then
// tray, quick toggles, system readings and the clock on the right.
PanelWindow {
    id: bar
    property bool top: Theme.widget("bar").position === "top"

    anchors { left: true; right: true; top: bar.top; bottom: !bar.top }
    implicitHeight: 34
    exclusiveZone: implicitHeight
    color: "transparent"
    WlrLayershell.namespace: "nullgrid-bar"
    WlrLayershell.layer: WlrLayer.Top

    Rectangle {
        anchors.fill: parent
        color: Theme.alpha(Theme.surface, Theme.surfaceOpacity)
        Rectangle {  // the edge line toward the screen
            anchors { left: parent.left; right: parent.right }
            y: bar.top ? parent.height - 1 : 0
            height: 1
            color: Theme.alpha(Theme.primary, 0.55)
        }
    }

    // ---------------------------------------------------------------- left
    RowLayout {
        anchors { left: parent.left; verticalCenter: parent.verticalCenter; leftMargin: 6 }
        spacing: 10

        Item {  // mode / profile plate
            implicitWidth: modeText.implicitWidth + 30
            implicitHeight: 24
            Chamfer {
                anchors.fill: parent
                cut: 7
                fill: Theme.alpha(Theme.primary, 0.14)
                stroke: Theme.primary
            }
            Row {
                id: modeText
                anchors.centerIn: parent
                spacing: 6
                NgText { text: "NG"; color: Theme.primary; font.family: Theme.fontDisplay; font.pixelSize: 11; font.bold: true }
                NgText { text: "//"; label: true }
                NgText {
                    text: (Theme.mode === "tty" ? "TTY" : "DESKTOP") + " · " + (Theme.lite ? "LITE" : "FULL")
                    label: true; color: Theme.text
                }
            }
        }

        Row {  // workspaces
            spacing: 3
            Repeater {
                model: Wm.workspaces
                Item {
                    required property var modelData
                    width: 22; height: 20
                    Chamfer {
                        anchors.fill: parent
                        cut: 5
                        fill: modelData.focused ? Theme.alpha(Theme.primary, 0.22) : "transparent"
                        stroke: modelData.urgent ? Theme.warning
                              : modelData.focused ? Theme.primary
                              : Theme.alpha(Theme.dim, modelData.occupied ? 0.8 : 0.3)
                    }
                    Hatch { anchors.fill: parent; anchors.margins: 2; visible: modelData.focused; spacing: 5 }
                    NgText {
                        anchors.centerIn: parent
                        text: modelData.id
                        mono: true
                        font.pixelSize: 11
                        color: modelData.focused ? Theme.text : modelData.occupied ? Theme.primary : Theme.dim
                    }
                    MouseArea { anchors.fill: parent; onClicked: Wm.activate(modelData.id) }
                }
            }
        }

        NgText {
            Layout.maximumWidth: 360
            text: Wm.activeTitle ? "› " + Wm.activeTitle : ""
            color: Theme.dim
        }
    }

    // ---------------------------------------------------------------- middle: now playing
    Row {
        id: media
        readonly property var player: {
            const ps = Mpris.players.values
            return ps.find(p => p.isPlaying) || ps[0] || null
        }
        visible: player !== null
        anchors.centerIn: parent
        spacing: 8
        NgIcon {
            name: media.player && media.player.isPlaying ? "pause" : "play"
            size: 14; anchors.verticalCenter: parent.verticalCenter
            MouseArea { anchors.fill: parent; onClicked: media.player.togglePlaying() }
        }
        NgText {
            width: Math.min(implicitWidth, 320)
            text: media.player ? (media.player.trackTitle || media.player.identity)
                  + (media.player.trackArtist ? "  —  " + media.player.trackArtist : "") : ""
        }
    }

    // ---------------------------------------------------------------- right
    RowLayout {
        anchors { right: parent.right; verticalCenter: parent.verticalCenter; rightMargin: 10 }
        spacing: 14

        Row {  // tray
            spacing: 6
            Repeater {
                model: SystemTray.items
                Item {
                    required property var modelData
                    width: 16; height: 16
                    Image { anchors.fill: parent; source: modelData.icon; sourceSize: Qt.size(16, 16) }
                    MouseArea {
                        anchors.fill: parent
                        acceptedButtons: Qt.LeftButton | Qt.RightButton
                        onClicked: mouse => {
                            if (mouse.button === Qt.RightButton && modelData.hasMenu) {
                                const p = mapToItem(null, 0, 0)
                                modelData.display(bar, p.x, bar.top ? bar.height : -4)
                            } else {
                                modelData.activate()
                            }
                        }
                    }
                }
            }
        }

        Row {  // quick toggles
            spacing: 10
            Toggle {
                icon: "wifi"
                visible: Networking.wifiHardwareEnabled
                on: Networking.wifiEnabled
                onClicked: Networking.wifiEnabled = !Networking.wifiEnabled
            }
            Toggle {
                icon: "bluetooth"
                visible: Bluetooth.defaultAdapter !== null
                on: Bluetooth.defaultAdapter ? Bluetooth.defaultAdapter.enabled : false
                onClicked: Bluetooth.defaultAdapter.enabled = !Bluetooth.defaultAdapter.enabled
            }
            Toggle {
                icon: "brightness"
                visible: Backlight.available
                on: true
                value: Backlight.percent
                onClicked: {}
                onScrolled: up => Backlight.step(up ? 5 : -5)
            }
            Toggle {
                id: volume
                readonly property var sink: Pipewire.defaultAudioSink
                PwObjectTracker { objects: volume.sink ? [volume.sink] : [] }
                icon: sink && sink.audio && sink.audio.muted ? "mute" : "volume"
                visible: Pipewire.ready && sink !== null
                on: sink && sink.audio ? !sink.audio.muted : false
                value: sink && sink.audio ? sink.audio.volume * 100 : NaN
                onClicked: sink.audio.muted = !sink.audio.muted
                onScrolled: up => sink.audio.volume = Math.max(0, Math.min(1, sink.audio.volume + (up ? 0.05 : -0.05)))
            }
        }

        Reading { label: "CPU"; value: Sys.pct(Sys.cpu); hot: Sys.cpu > 85 }
        Reading { label: "RAM"; value: Sys.pct(Sys.memPct); hot: Sys.memPct > 90 }
        Reading { label: "GPU"; value: Sys.pct(Sys.gpuBusy); visible: !isNaN(Sys.gpuBusy) }
        Reading { label: "NET"; value: "↓" + Sys.bytes(Sys.rxRate) + " ↑" + Sys.bytes(Sys.txRate) }
        Reading {
            label: "TEMP"
            value: Sys.temp(Sys.cpuTemp) + (isNaN(Sys.gpuTemp) ? "" : " / " + Sys.temp(Sys.gpuTemp))
            visible: !isNaN(Sys.cpuTemp)
            hot: Sys.cpuTemp > 85
        }
        Reading {
            label: Sys.discharging ? "BAT" : "PWR"
            value: isNaN(Sys.battery) ? "AC"
                 : Sys.pct(Sys.battery) + (Sys.discharging && !isNaN(Sys.power) ? " " + Sys.power.toFixed(1) + "W" : "")
            hot: Sys.discharging && Sys.battery < 15
        }

        Item {  // clock
            implicitWidth: clockText.implicitWidth + 24
            implicitHeight: 24
            Chamfer { anchors.fill: parent; cut: 7; cutTopLeft: false; cutTopRight: true; cutBottomRight: false; cutBottomLeft: true
                      fill: "transparent"; stroke: Theme.alpha(Theme.primary, 0.6) }
            SystemClock { id: clock; precision: SystemClock.Minutes }
            NgText {
                id: clockText
                anchors.centerIn: parent
                mono: true
                text: Qt.formatDateTime(clock.date, "yyyy-MM-dd HH:mm")
                color: Theme.primary
            }
        }
    }

    // ---------------------------------------------------------------- pieces
    component Reading: Row {
        property string label
        property string value
        property bool hot: false
        spacing: 5
        NgText { label: true; text: parent.label; anchors.verticalCenter: parent.verticalCenter }
        NgText {
            mono: true
            text: parent.value
            color: parent.hot ? Theme.warning : Theme.text
            font.pixelSize: Math.round(Theme.fontSize * 0.9)
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    component Toggle: Item {
        id: toggle
        property string icon
        property bool on: false
        property real value: NaN
        signal clicked()
        signal scrolled(bool up)
        implicitWidth: row.implicitWidth
        implicitHeight: 20
        Row {
            id: row
            spacing: 3
            anchors.verticalCenter: parent.verticalCenter
            NgIcon { name: toggle.icon; size: 16; color: toggle.on ? Theme.primary : Theme.dim }
            NgText {
                visible: !isNaN(toggle.value)
                text: Math.round(toggle.value)
                mono: true
                font.pixelSize: 11
                color: Theme.dim
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        MouseArea {
            anchors.fill: parent
            onClicked: toggle.clicked()
            onWheel: wheel => toggle.scrolled(wheel.angleDelta.y > 0)
        }
    }
}

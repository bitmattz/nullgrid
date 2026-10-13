import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Services.Notifications

// The notification daemon (org.freedesktop.Notifications) and its popups: chamfered cards in
// the top right corner, newest on top. Critical ones stay until clicked; the rest expire.
Scope {
    id: root

    NotificationServer {
        id: server
        keepOnReload: true
        actionsSupported: true
        imageSupported: true
        bodyMarkupSupported: false
        persistenceSupported: false
        onNotification: n => {
            n.tracked = true
            if (!(n.hints && n.hints["suppress-sound"]))
                Sfx.play(n.urgency === NotificationUrgency.Critical ? "notification_critical" : "notification")
        }
    }

    readonly property var shown: server.trackedNotifications.values.slice().reverse().slice(0, 5)

    PanelWindow {
        visible: root.shown.length > 0
        anchors { top: true; right: true }
        margins { top: 14; right: 14 }
        implicitWidth: 380
        implicitHeight: stack.implicitHeight
        exclusiveZone: 0
        color: "transparent"
        WlrLayershell.namespace: "nullgrid-notifications"
        WlrLayershell.layer: WlrLayer.Overlay

        Column {
            id: stack
            width: parent.width
            spacing: 8
            Repeater {
                model: root.shown
                Card { required property var modelData; notification: modelData }
            }
        }
    }

    component Card: Item {
        id: card
        property var notification
        readonly property bool critical: notification.urgency === NotificationUrgency.Critical
        readonly property color accent: critical ? Theme.secondary : Theme.primary
        width: 380
        height: Math.max(72, body.implicitHeight + 24)

        Chamfer { anchors.fill: parent; cut: 12; fill: Theme.alpha(Theme.surface, 0.94); stroke: card.accent; strokeWidth: card.critical ? 1.5 : 1 }
        Rectangle { x: 0; y: 14; width: 3; height: parent.height - 28; color: card.accent }

        Item {
            id: art
            x: 16; y: 14; width: 36; height: 36
            Rectangle { anchors.fill: parent; radius: 18; color: "transparent"; border.width: 1; border.color: Theme.alpha(card.accent, 0.6) }
            Image {
                id: img
                anchors.centerIn: parent
                width: 22; height: 22; sourceSize: Qt.size(22, 22)
                source: card.notification.image || (card.notification.appIcon ? Quickshell.iconPath(card.notification.appIcon, true) : "")
                visible: status === Image.Ready
            }
            NgIcon { anchors.centerIn: parent; visible: !img.visible; name: card.critical ? "warning" : "bell"; size: 18; color: card.accent }
        }

        Column {
            id: body
            anchors { left: art.right; leftMargin: 12; right: parent.right; rightMargin: 16; top: parent.top; topMargin: 12 }
            spacing: 3
            NgText { width: parent.width; label: true; text: (card.notification.appName || "system") + (card.critical ? "  //  CRITICAL" : ""); color: card.critical ? Theme.secondary : Theme.dim }
            NgText { width: parent.width; text: card.notification.summary; font.bold: true; color: Theme.text }
            NgText {
                width: parent.width
                visible: text !== ""
                text: card.notification.body
                color: Theme.dim
                wrapMode: Text.Wrap
                maximumLineCount: 4
                textFormat: Text.PlainText
            }
            Row {
                visible: card.notification.actions.length > 0
                spacing: 6
                topPadding: 4
                Repeater {
                    model: card.notification.actions
                    Item {
                        required property var modelData
                        width: actionText.implicitWidth + 20; height: 24
                        Chamfer { anchors.fill: parent; cut: 5; fill: "transparent"; stroke: Theme.alpha(card.accent, 0.7) }
                        NgText { id: actionText; anchors.centerIn: parent; text: modelData.text; font.pixelSize: 12 }
                        MouseArea { anchors.fill: parent; onClicked: { Sfx.play("button_click"); modelData.invoke() } }
                    }
                }
            }
        }

        // expiry: the sender's timeout, or 6 s; critical notifications wait for a click
        Timer {
            running: !card.critical && !hover.containsMouse
            interval: card.notification.expireTimeout > 0 ? card.notification.expireTimeout * 1000 : 6000
            onTriggered: card.notification.expire()
        }
        MouseArea {
            id: hover
            anchors.fill: parent
            z: -1
            hoverEnabled: true
            onClicked: card.notification.dismiss()
        }
    }
}

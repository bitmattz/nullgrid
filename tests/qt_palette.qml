// A plain Qt Quick Controls window for the shell smoke test: with QT_QPA_PLATFORMTHEME=qt6ct it
// takes the NULLGRID palette and font, and must change them live when the theme switches.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    visible: true
    width: 520; height: 300
    title: "qt-palette-test"
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 20
        Label { text: "QT PALETTE TEST // " + Qt.application.font.family }
        TextField { placeholderText: "type here"; Layout.fillWidth: true }
        RowLayout { Button { text: "Button" } CheckBox { text: "check"; checked: true } }
        ProgressBar { value: 0.6; Layout.fillWidth: true }
    }
}

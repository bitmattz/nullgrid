import QtQuick
import QtQuick.Shapes

// Circular RAM gauge with the percentage in the middle; swap and totals beside it.
HudPanel {
    title: "MEMORY"
    caption: "RAM"
    implicitWidth: 260; implicitHeight: 160

    Item {
        id: gauge
        width: 104; height: 104
        anchors.verticalCenter: parent.verticalCenter
        readonly property real frac: Math.max(0, Math.min(1, Sys.memPct / 100))
        Shape {
            anchors.fill: parent
            ShapePath {  // track, segmented
                fillColor: "transparent"
                strokeColor: Theme.alpha(Theme.dim, 0.35)
                strokeWidth: 8
                dashPattern: [0.6, 0.4]
                capStyle: ShapePath.FlatCap
                PathAngleArc { centerX: 52; centerY: 52; radiusX: 46; radiusY: 46; startAngle: 135; sweepAngle: 270 }
            }
            ShapePath {  // value
                fillColor: "transparent"
                strokeColor: Sys.memPct > 90 ? Theme.warning : Theme.primary
                strokeWidth: 8
                capStyle: ShapePath.FlatCap
                PathAngleArc { centerX: 52; centerY: 52; radiusX: 46; radiusY: 46; startAngle: 135; sweepAngle: 270 * gauge.frac }
            }
            ShapePath {  // inner hairline
                fillColor: "transparent"
                strokeColor: Theme.alpha(Theme.primary, 0.3)
                strokeWidth: 1
                PathAngleArc { centerX: 52; centerY: 52; radiusX: 36; radiusY: 36; startAngle: 0; sweepAngle: 360 }
            }
        }
        NgText {
            anchors.centerIn: parent
            text: Math.round(Sys.memPct) + "%"
            font.family: Theme.fontDisplay
            font.pixelSize: 22
            font.bold: true
            color: Theme.text
        }
    }

    Column {
        anchors { left: gauge.right; leftMargin: 14; verticalCenter: parent.verticalCenter }
        spacing: 4
        NgText { label: true; text: "USED" }
        NgText { mono: true; text: Sys.bytes(Sys.memUsed) + " / " + Sys.bytes(Sys.memTotal) }
        NgText { label: true; text: "SWAP" }
        NgText { mono: true; text: Sys.swapTotal > 0 ? Sys.bytes(Sys.swapUsed) + " / " + Sys.bytes(Sys.swapTotal) : "none" }
    }
}

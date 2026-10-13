import QtQuick
import QtQuick.Shapes

// A HUD panel: 45° cut corners (top left and bottom right by default), a thin outline and a
// translucent fill. Follows [theme.style] corners: sharp, chamfer or round.
Item {
    id: root
    property color fill: Theme.alpha(Theme.surface, Theme.surfaceOpacity)
    property color stroke: Theme.alpha(Theme.primary, 0.7)
    property real strokeWidth: 1
    property int cut: Theme.cut
    property bool cutTopLeft: true
    property bool cutTopRight: false
    property bool cutBottomRight: true
    property bool cutBottomLeft: false

    readonly property bool round: Theme.corners === "round"
    readonly property real h: strokeWidth / 2
    readonly property real c: Theme.corners === "sharp" ? 0 : cut
    readonly property real tl: cutTopLeft ? c : 0
    readonly property real tr: cutTopRight ? c : 0
    readonly property real br: cutBottomRight ? c : 0
    readonly property real bl: cutBottomLeft ? c : 0

    Rectangle {
        visible: root.round
        anchors.fill: parent
        radius: root.cut
        color: root.fill
        border.color: root.stroke
        border.width: root.strokeWidth
    }

    Shape {
        visible: !root.round
        anchors.fill: parent
        ShapePath {
            fillColor: root.fill
            strokeColor: root.strokeWidth > 0 ? root.stroke : "transparent"
            strokeWidth: root.strokeWidth
            joinStyle: ShapePath.MiterJoin
            startX: root.h + root.tl; startY: root.h
            PathLine { x: root.width - root.h - root.tr; y: root.h }
            PathLine { x: root.width - root.h; y: root.h + root.tr }
            PathLine { x: root.width - root.h; y: root.height - root.h - root.br }
            PathLine { x: root.width - root.h - root.br; y: root.height - root.h }
            PathLine { x: root.h + root.bl; y: root.height - root.h }
            PathLine { x: root.h; y: root.height - root.h - root.bl }
            PathLine { x: root.h; y: root.h + root.tl }
            PathLine { x: root.h + root.tl; y: root.h }
        }
    }
}

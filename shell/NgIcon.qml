import QtQuick
import QtQuick.Shapes
import "Icons.js" as Icons

// A line icon from Icons.js, stroked in any color, at any size.
Item {
    id: root
    property string name: "apps"
    property color color: Theme.primary
    property real lineWidth: 1.6
    property int size: 20
    implicitWidth: size
    implicitHeight: size

    Shape {
        anchors.centerIn: parent
        width: 24; height: 24
        scale: root.size / 24
        ShapePath {
            fillColor: "transparent"
            strokeColor: root.color
            strokeWidth: root.lineWidth * 24 / root.size
            capStyle: ShapePath.SquareCap
            joinStyle: ShapePath.MiterJoin
            PathSvg { path: Icons.paths[root.name] || Icons.paths.apps }
        }
    }
}

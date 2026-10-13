import QtQuick

// The NULLGRID mark (docs/LOGO.md): a 4x4 lattice with the dead pixel at row 2, column 2.
// `cells: 2` gives the small variant.
Item {
    id: root
    property int cells: 4
    property color color: Theme.primary
    property color hole: Theme.secondary
    property real line: Math.max(1, width / (cells * 10))
    readonly property real cell: width / cells
    readonly property int hr: cells === 4 ? 2 : 1
    readonly property int hc: cells === 4 ? 2 : 1
    implicitWidth: 24
    implicitHeight: width

    Repeater {   // horizontal segments
        model: (root.cells + 1) * root.cells
        Rectangle {
            required property int index
            readonly property int r: Math.floor(index / root.cells)
            readonly property int col: index % root.cells
            visible: !((r === root.hr || r === root.hr + 1) && col === root.hc)
            x: col * root.cell + root.cell * 0.16
            y: r * root.cell - root.line / 2
            width: root.cell * 0.68; height: root.line
            color: root.color
        }
    }
    Repeater {   // vertical segments
        model: (root.cells + 1) * root.cells
        Rectangle {
            required property int index
            readonly property int col: Math.floor(index / root.cells)
            readonly property int r: index % root.cells
            visible: !((col === root.hc || col === root.hc + 1) && r === root.hr)
            x: col * root.cell - root.line / 2
            y: r * root.cell + root.cell * 0.16
            width: root.line; height: root.cell * 0.68
            color: root.color
        }
    }
    Rectangle {
        x: root.hc * root.cell + root.cell * 0.22
        y: root.hr * root.cell + root.cell * 0.22
        width: root.cell * 0.56; height: width
        color: root.hole
    }
}

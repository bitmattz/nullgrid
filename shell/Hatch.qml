import QtQuick

// Diagonal stripes: the "active" fill of the HUD style.
Item {
    id: root
    property color color: Theme.alpha(Theme.primary, 0.35)
    property real spacing: 6
    clip: true
    Repeater {
        model: Math.max(0, Math.ceil((root.width + root.height) / root.spacing) + 1)
        Rectangle {
            required property int index
            width: 1.5
            height: (root.width + root.height) * 1.5
            x: index * root.spacing - root.height
            y: -root.height * 0.25
            rotation: 45
            transformOrigin: Item.Top
            color: root.color
            antialiasing: true
        }
    }
}

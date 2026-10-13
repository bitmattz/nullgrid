import QtQuick
import Quickshell
import Quickshell.Wayland

// Falling character columns over the wallpaper (decor.matrix_rain), under the windows and the
// HUD. They move in discrete steps a few times a second. Off with reduce_motion, the lite
// profile, and without a GPU (software rendering): there each step makes the compositor redraw
// the screen on the CPU, which took Hyprland to 150% CPU in a VM.
PanelWindow {
    id: rain
    readonly property int columnCount: 9
    readonly property int length: 14
    readonly property int line: 19

    visible: (Theme.decor.matrix_rain ?? true) && Theme.animations && !Theme.lite && !Theme.software
    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    color: "transparent"
    mask: Region {}  // clicks pass through
    WlrLayershell.namespace: "nullgrid-matrix"
    WlrLayershell.layer: WlrLayer.Bottom

    readonly property string glyphs: "0123456789ABCDEF:./<>|=+*#"
    function glyph() { return glyphs[Math.floor(Math.random() * glyphs.length)] }

    Repeater {
        id: columns
        model: rain.columnCount
        Column {
            id: col
            required property int index
            property int head: -Math.floor(Math.random() * 40)
            property var chars: Array.from({ length: rain.length }, () => rain.glyph())
            // spread over the left part of the screen, clear of the dock and the HUD cluster
            x: 110 + ((index * 0.6180339 + 0.13) % 1) * (rain.width * 0.55)
            y: (head - rain.length) * rain.line
            Repeater {
                model: rain.length
                NgText {
                    required property int index
                    readonly property bool lead: index === rain.length - 1
                    width: 14
                    height: rain.line
                    horizontalAlignment: Text.AlignHCenter
                    mono: true
                    font.pixelSize: 13
                    text: col.chars[index]
                    color: lead ? Theme.text : Theme.primary
                    opacity: lead ? 0.55 : 0.05 + 0.3 * Math.pow(index / rain.length, 1.8)
                }
            }
            function step() {
                head += 1
                if ((head - rain.length) * rain.line > rain.height) head = -Math.floor(Math.random() * 30)
                const next = chars.slice(1)
                next.push(rain.glyph())
                if (Math.random() < 0.3) next[Math.floor(Math.random() * next.length)] = rain.glyph()
                chars = next
            }
        }
    }

    Timer {  // one step for every column at once: one redraw per tick
        interval: 125
        running: rain.visible
        repeat: true
        onTriggered: {
            for (let i = 0; i < columns.count; i++)
                columns.itemAt(i).step()
        }
    }
}

pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

// The look, from ~/.config/nullgrid/generated/theme.json (written by `nullgrid theme ...`).
// The file is watched: a theme change restyles the shell without a restart.
Singleton {
    id: root

    readonly property string path: Quickshell.env("NULLGRID_THEME_JSON")
        || (Quickshell.env("XDG_CONFIG_HOME") || Quickshell.env("HOME") + "/.config") + "/nullgrid/generated/theme.json"
    property var data: ({})
    readonly property bool loaded: data.colors !== undefined

    readonly property var c: data.colors || ({})
    readonly property color bg: c.bg || "#1a0b0f"
    readonly property color bgAlt: c.bg_alt || "#2a0f15"
    readonly property color surface: c.surface || "#24111a"
    readonly property color primary: c.primary || "#5ef2f2"
    readonly property color secondary: c.secondary || "#ff3b4e"
    readonly property color glow: c.glow || "#ff4d6d"
    readonly property color text: c.text || "#e6f7f7"
    readonly property color dim: c.dim || "#7a8a8f"
    readonly property color warning: c.warning || "#ffd166"

    readonly property var style: data.style || ({})
    readonly property real surfaceOpacity: style.surface_opacity ?? 0.85
    readonly property int border: Math.max(1, style.border_width ?? 2)
    readonly property real glowLevel: style.glow ?? 0.6
    readonly property string corners: style.corners || "chamfer"
    readonly property int gaps: style.gaps ?? 8
    // the cut of a chamfered corner, or the radius of a round one
    readonly property int cut: corners === "sharp" ? 0 : 10

    readonly property var fonts: data.fonts || ({})
    readonly property string fontUi: fonts.ui || "Rajdhani"
    readonly property string fontMono: fonts.mono || "JetBrains Mono"
    readonly property string fontDisplay: fonts.display || "Orbitron"
    readonly property int fontSize: Math.round((fonts.size || 11) * 4 / 3)  // pt -> px

    readonly property var widgets: data.widgets || ({})
    readonly property var decor: data.decor || ({})
    readonly property var effects: data.effects || ({})
    readonly property bool animations: effects.animations ?? true
    readonly property bool lite: effects.lite ?? false
    // set by nullgrid-session when there's no GPU with 3D: continuous animations cost real CPU then
    readonly property bool software: Quickshell.env("NULLGRID_SOFTWARE_RENDER") === "1"
    readonly property var durations: data.durations || ({ fast: 120, normal: 180, slow: 220 })
    readonly property int refreshMs: data.refresh_ms || 1000
    readonly property string name: data.name || "crimson-hud"
    readonly property string mode: data.behavior ? data.behavior.default_mode : "desktop"

    function alpha(col, a) { return Qt.rgba(col.r, col.g, col.b, a) }
    function widget(name) { return widgets[name] || ({ visible: true, position: "" }) }

    FileView {
        path: root.path
        watchChanges: true
        onFileChanged: reload()
        onLoaded: {
            try {
                root.data = JSON.parse(text())
            } catch (e) {
                console.warn("theme.json: " + e)  // keep the last good theme
            }
        }
    }
}

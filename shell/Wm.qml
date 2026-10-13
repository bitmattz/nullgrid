pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.I3
import Quickshell.Wayland

// The window manager behind one interface: Hyprland, or Sway (through its i3 IPC).
Singleton {
    id: root

    readonly property bool hyprland: !!Quickshell.env("HYPRLAND_INSTANCE_SIGNATURE")
    readonly property bool sway: !hyprland && !!Quickshell.env("SWAYSOCK")
    readonly property string name: hyprland ? "HYPRLAND" : sway ? "SWAY" : "WAYLAND"

    // [{ id, focused, occupied, urgent }] for workspaces 1..count, where count grows past 5
    // when a higher workspace exists.
    readonly property var workspaces: {
        const list = hyprland ? Hyprland.workspaces.values : sway ? I3.workspaces.values : []
        const byId = {}
        let top = 5
        for (const w of list) {
            const id = hyprland ? w.id : w.number
            if (id < 1) continue  // special/scratch workspaces
            byId[id] = w
            top = Math.max(top, id)
        }
        const out = []
        for (let i = 1; i <= Math.min(top, 10); i++) {
            const w = byId[i]
            out.push({
                id: i,
                focused: !!w && (hyprland ? w.focused : w.focused),
                occupied: !!w && (hyprland ? w.toplevels.values.length > 0 : true),
                urgent: !!w && w.urgent,
            })
        }
        return out
    }
    readonly property int focused: {
        const f = workspaces.find(w => w.focused)
        return f ? f.id : 1
    }
    readonly property string activeTitle: ToplevelManager.activeToplevel ? ToplevelManager.activeToplevel.title : ""
    readonly property string activeApp: ToplevelManager.activeToplevel ? ToplevelManager.activeToplevel.appId : ""

    function activate(id) {
        if (hyprland)
            Hyprland.dispatch(Hyprland.usingLua ? `hl.dsp.focus({ workspace = ${id} })` : `workspace ${id}`)
        else if (sway)
            I3.dispatch(`workspace number ${id}`)
    }

    function exec(cmd) {
        Quickshell.execDetached(["sh", "-c", cmd])
    }
}

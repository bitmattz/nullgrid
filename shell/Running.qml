pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Wayland

// The app ids of every open window, for "running" markers.
Singleton {
    readonly property var apps: ToplevelManager.toplevels.values.map(t => t.appId)
}

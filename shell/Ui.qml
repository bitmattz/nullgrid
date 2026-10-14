pragma Singleton
import QtQuick
import Quickshell

// Shell-wide UI state shared between panels.
Singleton {
    property bool menuOpen: false
    function toggleMenu() { menuOpen = !menuOpen }
    onMenuOpenChanged: {
        Sfx.play(menuOpen ? "launcher_open" : "launcher_close")
        if (menuOpen) picker = ""
    }

    // the open bar picker: "wifi", "bluetooth" or "" (NetPicker.qml, BtPicker.qml)
    property string picker: ""
    function togglePicker(name) { picker = picker === name ? "" : name }
    onPickerChanged: if (picker) menuOpen = false

    // demo mode for the shell test: the pickers show fake networks and devices (PickerDemo.qml)
    readonly property bool demo: Quickshell.env("NULLGRID_SHELL_DEMO") === "1"

    // Apps pinned to the dock (and shown as favorites in the start menu). `app` is the window
    // class that marks the app as running/active.
    readonly property var pinned: [
        { icon: "terminal", label: "Terminal", desc: "kitty", app: "kitty", cmd: "kitty" },
        { icon: "files", label: "Files", desc: "yazi file manager", app: "nullgrid-files", cmd: "kitty --class nullgrid-files yazi" },
        { icon: "globe", label: "Browser", desc: "firefox", app: "firefox", cmd: "firefox" },
        { icon: "editor", label: "Editor", desc: "neovim", app: "nullgrid-editor", cmd: "kitty --class nullgrid-editor nvim" },
        { icon: "monitor", label: "Monitor", desc: "btop resource monitor", app: "nullgrid-btop", cmd: "kitty --class nullgrid-btop btop" },
        { icon: "dashboard", label: "Dashboard", desc: "NULLGRID system dashboard", app: "nullgrid-dash", cmd: "kitty --class nullgrid-dash nullgrid-dash" },
        { icon: "settings", label: "Settings", desc: "edit nullgrid.toml", app: "nullgrid-settings", cmd: "kitty --class nullgrid-settings nullgrid theme edit" },
    ]
}

//@ pragma UseQApplication
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
import QtQuick
import Quickshell
import Quickshell.Io

// The NULLGRID desktop shell (Quickshell): status bar, dock, HUD widgets, start menu,
// notifications and the animated matrix layer. Colors, fonts and layout come from
// ~/.config/nullgrid/generated/theme.json, which `nullgrid theme ...` rewrites; the shell
// restyles live. Run it with `nullgrid-shell`; talk to it with `nullgrid-shell menu` etc.
ShellRoot {
    Variants {
        model: Quickshell.screens
        Scope {
            id: perScreen
            required property var modelData
            MatrixRain { screen: perScreen.modelData }
            Variants {
                model: ["top", "bottom", "left", "right", "top-left", "top-right", "bottom-left", "bottom-right"]
                Hud { required property string modelData; position: modelData; screen: perScreen.modelData }
            }
            Bar { screen: perScreen.modelData; visible: Theme.widget("bar").visible }
            Dock { screen: perScreen.modelData; visible: Theme.widget("dock").visible }
        }
    }

    StartMenu {}
    Notifications {}

    // `qs -c nullgrid ipc call shell <function>` (nullgrid-shell wraps it)
    IpcHandler {
        target: "shell"
        function toggleMenu(): void { Ui.toggleMenu() }
        function openMenu(): void { Ui.menuOpen = true }
        function closeMenu(): void { Ui.menuOpen = false }
        function status(): string {
            return `theme=${Theme.name} wm=${Wm.name} menu=${Ui.menuOpen} cpu=${Math.round(Sys.cpu)} mem=${Math.round(Sys.memPct)}`
        }
    }
}

//@ pragma UseQApplication
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.Pipewire

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
    NetPicker {}
    BtPicker {}
    Notifications {}

    // `qs -c nullgrid ipc call shell <function>` (nullgrid-shell wraps it)
    IpcHandler {
        target: "shell"
        function toggleMenu(): void { Ui.toggleMenu() }
        function openMenu(): void { Ui.menuOpen = true }
        function closeMenu(): void { Ui.menuOpen = false }
        // the bar's pickers: openPicker wifi|bluetooth
        function openPicker(name: string): void { Ui.picker = name }
        function togglePicker(name: string): void { Ui.togglePicker(name) }
        function closePicker(): void { Ui.picker = "" }
        function wifi(): string { return JSON.stringify(Net.summary()) }
        function bluetooth(): string { return JSON.stringify(Bt.summary()) }
        // the same calls as clicking in the pickers (for tests and scripts)
        function wifiConnect(name: string, password: string): string { return Net.connect(name, password) ? "ok" : "no such network" }
        function btActivate(address: string): string { return Bt.activate(address) ? "ok" : "no such device" }
        function demoLog(): string { return JSON.stringify(PickerDemo.log) }
        function status(): string {
            const audio = Pipewire.ready && Pipewire.defaultAudioSink !== null
            return `theme=${Theme.name} wm=${Wm.name} menu=${Ui.menuOpen} picker=${Ui.picker || "none"} cpu=${Math.round(Sys.cpu)} mem=${Math.round(Sys.memPct)} audio=${audio}`
        }
    }
}

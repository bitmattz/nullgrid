import QtQuick
import Quickshell
import Quickshell.Wayland

// The start menu, opened from the dock's top button or SUPER+SPACE: search, categories,
// favorites/app grid and power buttons. Type to search, arrows + Enter to launch, Esc to close.
PanelWindow {
    id: menu
    visible: Ui.menuOpen
    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    color: Theme.alpha(Theme.bg, 0.35)
    WlrLayershell.namespace: "nullgrid-menu"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

    property string category: "Favorites"
    property int selected: 0
    readonly property var categories: [
        { name: "Favorites", icon: "star", match: [] },
        { name: "All", icon: "apps", match: [] },
        { name: "Development", icon: "code", match: ["Development"] },
        { name: "Graphics", icon: "image", match: ["Graphics"] },
        { name: "Internet", icon: "globe", match: ["Network", "WebBrowser"] },
        { name: "Multimedia", icon: "media", match: ["AudioVideo", "Audio", "Video"] },
        { name: "Office", icon: "office", match: ["Office"] },
        { name: "Settings", icon: "settings", match: ["Settings"] },
        { name: "System", icon: "system", match: ["System", "Monitor"] },
        { name: "Utilities", icon: "tool", match: ["Utility", "Accessories"] },
        { name: "Games", icon: "game", match: ["Game"] },
    ]

    // Apps to show: [{ name, comment, icon (theme icon), glyph (NgIcon name), launch() }]
    readonly property var items: {
        const q = search.text.trim().toLowerCase()
        if (category === "Favorites" && !q)
            return Ui.pinned.map(p => ({ name: p.label, comment: p.desc, glyph: p.icon, icon: "", run: () => Wm.exec(p.cmd) }))
        const cat = categories.find(c => c.name === category)
        return DesktopEntries.applications.values
            .filter(e => !e.noDisplay)
            .filter(e => q ? (e.name + " " + e.genericName + " " + e.keywords + " " + e.comment).toLowerCase().includes(q)
                           : cat.match.length === 0 || cat.match.some(m => e.categories.indexOf(m) >= 0))
            .sort((a, b) => a.name.localeCompare(b.name))
            .map(e => ({ name: e.name, comment: e.comment || e.genericName, glyph: "", icon: e.icon, run: () => launch(e) }))
    }

    function launch(entry) {
        if (entry.runInTerminal)
            Quickshell.execDetached(["kitty", "sh", "-c", entry.execString.replace(/%[fFuUdDnNickvm]/g, "")])
        else
            entry.execute()
    }
    function run(i) {
        if (i >= 0 && i < items.length) {
            items[i].run()
            Ui.menuOpen = false
        } else {
            Sfx.play("error")  // Enter with nothing matching
        }
    }

    onVisibleChanged: {
        if (visible) {
            search.text = ""
            category = "Favorites"
            selected = 0
            search.forceActiveFocus()
        }
    }

    MouseArea { anchors.fill: parent; onClicked: Ui.menuOpen = false }  // click outside closes

    Item {
        id: panel
        width: 760; height: 540
        x: Theme.widget("dock").position === "right" ? parent.width - width - 84 : 84
        y: Theme.widget("bar").position === "top" ? 44 : parent.height - height - 44
        MouseArea { anchors.fill: parent }  // swallow clicks inside
        Chamfer { anchors.fill: parent; cut: 18; fill: Theme.alpha(Theme.surface, 0.96); stroke: Theme.primary; strokeWidth: 1.5 }
        Rectangle { x: 0; y: 30; width: 3; height: 60; color: Theme.secondary }

        // ---------------------------------------------------------------- header + search
        Row {
            x: 24; y: 16
            spacing: 10
            LatticeLogo { width: 22; anchors.verticalCenter: parent.verticalCenter }
            NgText { text: "NULLGRID"; font.family: Theme.fontDisplay; font.pixelSize: 15; font.bold: true; color: Theme.primary }
            NgText { label: true; text: "//  APPLICATIONS" }
        }
        Item {
            x: 24; y: 52; width: parent.width - 48; height: 38
            Chamfer { anchors.fill: parent; cut: 9; fill: Theme.alpha(Theme.bg, 0.7); stroke: search.activeFocus ? Theme.primary : Theme.alpha(Theme.dim, 0.6) }
            NgIcon { x: 12; anchors.verticalCenter: parent.verticalCenter; name: "search"; size: 16; color: Theme.dim }
            TextInput {
                id: search
                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 38; rightMargin: 12 }
                color: Theme.text
                selectionColor: Theme.alpha(Theme.primary, 0.4)
                font.family: Theme.fontMono
                font.pixelSize: 14
                onTextChanged: menu.selected = 0
                Keys.onEscapePressed: Ui.menuOpen = false
                Keys.onReturnPressed: menu.run(menu.selected)
                Keys.onEnterPressed: menu.run(menu.selected)
                Keys.onDownPressed: menu.selected = Math.min(menu.items.length - 1, menu.selected + grid.columns)
                Keys.onUpPressed: menu.selected = Math.max(0, menu.selected - grid.columns)
                Keys.onRightPressed: event => { if (cursorPosition === text.length) menu.selected = Math.min(menu.items.length - 1, menu.selected + 1); else event.accepted = false }
                Keys.onLeftPressed: event => { if (cursorPosition === text.length && menu.selected > 0) menu.selected--; else event.accepted = false }
                NgText {
                    visible: !search.text
                    anchors.verticalCenter: parent.verticalCenter
                    text: "SEARCH APPLICATIONS…"
                    color: Theme.dim
                    font.family: Theme.fontMono
                    font.pixelSize: 13
                }
            }
        }

        // ---------------------------------------------------------------- categories
        Column {
            id: cats
            x: 24; y: 104; width: 170
            spacing: 2
            Repeater {
                model: menu.categories
                Item {
                    required property var modelData
                    readonly property bool current: menu.category === modelData.name && !search.text
                    width: cats.width; height: 30
                    Rectangle { anchors.fill: parent; color: current ? Theme.alpha(Theme.primary, 0.14) : catMouse.containsMouse ? Theme.alpha(Theme.primary, 0.06) : "transparent" }
                    Rectangle { visible: current; width: 2; height: parent.height; color: Theme.primary }
                    NgIcon { x: 12; anchors.verticalCenter: parent.verticalCenter; name: modelData.icon; size: 16; color: current ? Theme.primary : Theme.dim }
                    NgText { x: 38; anchors.verticalCenter: parent.verticalCenter; text: modelData.name.toUpperCase(); font.letterSpacing: 1; color: current ? Theme.text : Theme.dim }
                    MouseArea { id: catMouse; anchors.fill: parent; hoverEnabled: true; onClicked: { Sfx.play("button_click"); search.text = ""; menu.category = modelData.name; menu.selected = 0; search.forceActiveFocus() } }
                }
            }
        }
        Rectangle { x: 206; y: 104; width: 1; height: 370; color: Theme.alpha(Theme.dim, 0.35) }

        // ---------------------------------------------------------------- apps
        GridView {
            id: grid
            readonly property int columns: 3
            x: 222; y: 104
            width: parent.width - x - 24; height: 370
            cellWidth: width / columns; cellHeight: 62
            clip: true
            model: menu.items
            currentIndex: menu.selected
            boundsBehavior: Flickable.StopAtBounds
            delegate: Item {
                required property var modelData
                required property int index
                readonly property bool current: index === menu.selected
                width: grid.cellWidth; height: grid.cellHeight
                Chamfer {
                    anchors.fill: parent; anchors.margins: 3; cut: 8
                    fill: current ? Theme.alpha(Theme.primary, 0.16) : appMouse.containsMouse ? Theme.alpha(Theme.primary, 0.07) : "transparent"
                    stroke: current ? Theme.primary : "transparent"
                }
                Item {
                    id: iconBox
                    x: 12; width: 32; height: 32
                    anchors.verticalCenter: parent.verticalCenter
                    Rectangle { anchors.fill: parent; radius: 16; color: "transparent"; border.width: 1; border.color: Theme.alpha(Theme.primary, 0.5) }
                    NgIcon { anchors.centerIn: parent; visible: modelData.glyph !== ""; name: modelData.glyph || "apps"; size: 18 }
                    Image {
                        anchors.centerIn: parent
                        visible: modelData.glyph === ""
                        width: 20; height: 20
                        sourceSize: Qt.size(20, 20)
                        source: modelData.icon ? Quickshell.iconPath(modelData.icon, "application-x-executable") : ""
                    }
                }
                Column {
                    anchors { left: iconBox.right; leftMargin: 10; right: parent.right; rightMargin: 8; verticalCenter: parent.verticalCenter }
                    NgText { width: parent.width; text: modelData.name; color: current ? Theme.text : Theme.text }
                    NgText { width: parent.width; text: modelData.comment || ""; color: Theme.dim; font.pixelSize: 11 }
                }
                MouseArea {
                    id: appMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    onEntered: { menu.selected = index; Sfx.play("menu_hover") }
                    onClicked: menu.run(index)
                }
            }
            NgText {
                visible: menu.items.length === 0
                anchors.centerIn: parent
                label: true
                text: "NO MATCH IN THE GRID"
            }
        }

        // ---------------------------------------------------------------- power
        Rectangle { x: 24; y: parent.height - 58; width: parent.width - 48; height: 1; color: Theme.alpha(Theme.dim, 0.35) }
        NgText { x: 24; y: parent.height - 44; height: 30; label: true; text: "SESSION // " + Wm.name }
        Row {
            anchors { right: parent.right; rightMargin: 24; bottom: parent.bottom; bottomMargin: 14 }
            spacing: 8
            // nullgrid-lock / nullgrid-power play the lock, logout and shutdown sounds first
            PowerButton { glyph: "lock"; text: "LOCK"; command: "nullgrid-lock" }
            PowerButton { glyph: "logout"; text: "LOG OUT"; confirm: true; command: "nullgrid-power logout" }
            PowerButton { glyph: "sleep"; text: "SLEEP"; command: "nullgrid-power suspend" }
            PowerButton { glyph: "restart"; text: "RESTART"; confirm: true; command: "nullgrid-power reboot" }
            PowerButton { glyph: "power"; text: "SHUT DOWN"; confirm: true; command: "nullgrid-power poweroff"; danger: true }
        }
    }

    // Destructive buttons ask once: the first click arms them for 3 s.
    component PowerButton: Item {
        id: pb
        property string glyph
        property string text
        property string command
        property bool confirm: false
        property bool danger: false
        property bool armed: false
        readonly property color tint: armed || danger && pbMouse.containsMouse ? Theme.secondary : Theme.primary
        width: label.implicitWidth + 44; height: 30
        Chamfer { anchors.fill: parent; cut: 7; fill: pb.armed ? Theme.alpha(Theme.secondary, 0.2) : pbMouse.containsMouse ? Theme.alpha(pb.tint, 0.12) : "transparent"; stroke: Theme.alpha(pb.tint, 0.8) }
        NgIcon { x: 10; anchors.verticalCenter: parent.verticalCenter; name: pb.glyph; size: 14; color: pb.tint }
        NgText { id: label; x: 30; anchors.verticalCenter: parent.verticalCenter; text: pb.armed ? "CONFIRM" : pb.text; font.letterSpacing: 1; font.pixelSize: 12; color: pb.armed ? Theme.secondary : Theme.text }
        Timer { id: disarm; interval: 3000; onTriggered: pb.armed = false }
        MouseArea {
            id: pbMouse
            anchors.fill: parent
            hoverEnabled: true
            onClicked: {
                if (pb.confirm && !pb.armed) { pb.armed = true; disarm.restart(); Sfx.play("button_click"); return }
                Ui.menuOpen = false
                Wm.exec(pb.command)
            }
        }
    }
}

pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Bluetooth

// Bluetooth for the bar's picker (BtPicker.qml), from BlueZ through Quickshell. In demo mode
// (NULLGRID_SHELL_DEMO=1, the shell test) the adapter and devices are fakes from PickerDemo.
Singleton {
    id: root

    readonly property var adapter: Ui.demo ? PickerDemo.adapter : Bluetooth.defaultAdapter
    readonly property bool present: adapter !== null
    readonly property bool on: present && adapter.enabled
    // discover devices while the picker is open
    property bool scanning: false

    readonly property var all: !present ? [] : (Ui.demo ? PickerDemo.devices : adapter.devices.values)
    // paired devices: connected first, then by name
    readonly property var paired: all.filter(d => d.paired || d.bonded)
        .sort((a, b) => (b.connected - a.connected) || label(a).localeCompare(label(b)))
    // devices in range that aren't paired; nameless ones (just an address) last
    readonly property var available: all.filter(d => !d.paired && !d.bonded)
        .sort((a, b) => ((b.name !== "") - (a.name !== "")) || label(a).localeCompare(label(b)))

    // devices we're pairing to connect them afterwards, by address
    property var pending: ({})
    property var errors: ({})

    function label(d) { return d.name || d.deviceName || d.address }
    // what kind of device, from BlueZ's icon name ("audio-headset", "input-mouse", ...)
    function kind(d) {
        const i = d.icon || ""
        if (i.indexOf("audio") === 0) return i.indexOf("headset") >= 0 || i.indexOf("headphone") >= 0 ? "HEADSET" : "AUDIO"
        if (i === "input-mouse") return "MOUSE"
        if (i === "input-keyboard") return "KEYBOARD"
        if (i === "input-gaming") return "GAMEPAD"
        if (i.indexOf("phone") >= 0) return "PHONE"
        if (i.indexOf("computer") >= 0) return "COMPUTER"
        return "DEVICE"
    }

    function setOn(v) { if (present) adapter.enabled = v }

    function find(address) { return all.find(d => d.address === address) || null }

    function setError(address, text) {
        const e = Object.assign({}, errors)
        if (text) e[address] = text
        else delete e[address]
        errors = e
    }

    // click on a device: paired -> connect or disconnect; new -> pair, trust, then connect
    function activate(address) {
        const d = find(address)
        if (!d) return false
        setError(address, "")
        if (d.paired || d.bonded) {
            if (d.connected) d.disconnect()
            else d.connect()
        } else {
            const p = Object.assign({}, pending)
            p[address] = true
            pending = p
            d.trusted = true
            d.pair()
            pairTimeout.restart()
        }
        return true
    }
    function forget(address) { const d = find(address); if (d) d.forget() }

    // a device that finished pairing gets connected
    Instantiator {
        model: root.all
        delegate: Connections {
            required property var modelData
            target: modelData
            function onPairedChanged() {
                if (modelData.paired && root.pending[modelData.address]) {
                    const p = Object.assign({}, root.pending)
                    delete p[modelData.address]
                    root.pending = p
                    modelData.connect()
                    Sfx.play("button_click")
                }
            }
        }
    }
    // BlueZ needs an agent for devices that ask for a PIN; without a reply in time, say so
    Timer {
        id: pairTimeout
        interval: 30000
        onTriggered: {
            for (const a in root.pending) {
                const d = root.find(a)
                if (d && !d.paired) root.setError(a, "not paired: if it needs a PIN, use bluetoothctl")
            }
            root.pending = ({})
        }
    }

    Binding {
        when: root.present && root.on
        target: root.adapter
        property: "discovering"
        value: root.scanning
    }

    function summary() {
        const dev = d => ({ name: label(d), kind: kind(d), connected: d.connected, paired: d.paired || d.bonded,
                           battery: d.batteryAvailable ? Math.round(d.battery * 100) : -1, error: errors[d.address] || "" })
        return { adapter: present, on: on, paired: paired.map(dev), available: available.map(dev) }
    }
}

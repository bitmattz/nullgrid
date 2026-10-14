pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Networking

// Networks for the bar's picker (NetPicker.qml), from NetworkManager through Quickshell. In demo
// mode (NULLGRID_SHELL_DEMO=1, used by the shell test) the networks are fakes from PickerDemo.
Singleton {
    id: root

    readonly property var wifiDevice: firstOf(DeviceType.Wifi)
    readonly property var wiredDevice: firstOf(DeviceType.Wired)
    readonly property bool hasWifi: Ui.demo || wifiDevice !== null
    readonly property bool wifiOn: Ui.demo ? PickerDemo.wifiOn : Networking.wifiEnabled
    // scan while the picker is open (NetworkManager rescans every few seconds then)
    property bool scanning: false

    // Wi-Fi networks: connected first, then saved ones, then by signal
    readonly property var networks: {
        const list = Ui.demo ? PickerDemo.networks : (wifiDevice ? wifiDevice.networks.values : [])
        return list.filter(n => n.name)
            .slice()
            .sort((a, b) => (b.connected - a.connected) || (b.known - a.known)
                            || (b.signalStrength - a.signalStrength) || a.name.localeCompare(b.name))
    }
    readonly property var connected: networks.find(n => n.connected) || null
    // the wired link: null, or { up: bool, speed: Mb/s }
    readonly property var wired: Ui.demo ? PickerDemo.wired
        : wiredDevice ? { up: wiredDevice.network ? wiredDevice.network.connected : false, speed: wiredDevice.linkSpeed } : null

    // why the last connection attempt failed, by network name
    property var errors: ({})

    // the first device of a type; for Wi-Fi a client one (not a radio serving a hotspot)
    function firstOf(type) {
        const devs = Networking.devices.values.filter(d => d.type === type)
        if (type === DeviceType.Wifi) {
            const client = devs.find(d => d.mode !== WifiDeviceMode.AccessPoint)
            if (client) return client
        }
        return devs.length ? devs[0] : null
    }

    function setWifi(on) {
        if (Ui.demo) PickerDemo.wifiOn = on
        else Networking.wifiEnabled = on
    }

    // open (or enhanced-open) networks need no password; enterprise ones need more than one.
    // A saved network whose last attempt failed asks again (NetworkManager kept the bad one).
    function needsPassword(n) {
        return (!n.known || !!errors[n.name]) && secured(n) && !enterprise(n)
    }
    function enterprise(n) {
        return [WifiSecurityType.Wpa2Eap, WifiSecurityType.WpaEap, WifiSecurityType.Wpa3SuiteB192,
                WifiSecurityType.Leap, WifiSecurityType.DynamicWep].indexOf(n.security) >= 0
    }
    function secured(n) { return n.security !== WifiSecurityType.Open && n.security !== WifiSecurityType.Owe }
    // 0..4 bars from the signal strength (0..1)
    function bars(n) { return Math.max(1, Math.min(4, Math.ceil(n.signalStrength * 4))) }

    function find(name) { return networks.find(n => n.name === name) || null }

    function clearError(name) {
        const e = Object.assign({}, errors)
        delete e[name]
        errors = e
    }

    // connect by name; psk only for a secured network NetworkManager has no password for
    function connect(name, psk) {
        const n = find(name)
        if (!n) return false
        clearError(name)
        if (psk !== undefined && psk !== "") {
            n.connectWithPsk(psk)   // a saved network gets its password updated (no second profile)
        } else {
            n.connect()
        }
        return true
    }
    function disconnect(name) { const n = find(name); if (n) n.disconnect() }
    function forget(name) { const n = find(name); if (n) n.forget() }

    function failed(name, reason) {
        const e = Object.assign({}, errors)
        e[name] = reason === ConnectionFailReason.NoSecrets || reason === ConnectionFailReason.WifiClientFailed
                  || reason === ConnectionFailReason.WifiAuthTimeout ? "wrong password?" : "could not connect"
        errors = e
        Sfx.play("error")
    }

    // a connection attempt's failure, from whichever network reports it
    Instantiator {
        model: Ui.demo ? [] : root.networks
        delegate: Connections {
            required property var modelData
            target: modelData
            function onConnectionFailed(reason) { root.failed(modelData.name, reason) }
            function onConnectedChanged() { if (modelData.connected) { root.clearError(modelData.name); Sfx.play("button_click") } }
        }
    }

    Binding {
        when: root.wifiDevice !== null && !Ui.demo
        target: root.wifiDevice
        property: "scannerEnabled"
        value: root.scanning
    }

    // for the shell test: what the picker would show
    function summary() {
        return {
            wifi: hasWifi, on: wifiOn, wired: wired,
            networks: networks.map(n => ({ name: n.name, bars: bars(n), secured: secured(n), known: n.known,
                                           connected: n.connected, error: errors[n.name] || "" }))
        }
    }
}

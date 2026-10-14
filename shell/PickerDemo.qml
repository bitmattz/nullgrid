pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Networking

// Fake networks and Bluetooth devices for the pickers in demo mode (NULLGRID_SHELL_DEMO=1).
// `make test-shell` has no Wi-Fi or Bluetooth hardware: it drives the pickers with these and
// reads what they were asked to do from `log`.
Singleton {
    id: root
    property bool wifiOn: true
    property var log: []
    function record(what) { log = log.concat([what]) }

    readonly property var wired: ({ up: true, speed: 1000 })

    component FakeNetwork: QtObject {
        property string name
        property real signalStrength: 0.5
        property int security: WifiSecurityType.Wpa2Psk
        property bool known: false
        property bool connected: false
        property bool stateChanging: false
        function connect() { root.record("connect " + name); connected = true; known = true }
        function connectWithPsk(psk) {
            root.record("connect " + name + " psk=" + psk)
            if (psk === "nullgrid8") { connected = true; known = true }
        }
        function disconnect() { root.record("disconnect " + name); connected = false }
        function forget() { root.record("forget " + name); known = false; connected = false }
    }

    readonly property var networks: Array.from(netList)
    property list<QtObject> netList: [
        FakeNetwork { name: "NULLGRID-NODE"; signalStrength: 0.9; known: true; connected: true },
        FakeNetwork { name: "night_market_5G"; signalStrength: 0.7 },
        FakeNetwork { name: "OPEN-RELAY"; signalStrength: 0.45; security: WifiSecurityType.Open },
        FakeNetwork { name: "corp-secure"; signalStrength: 0.3; security: WifiSecurityType.Wpa2Eap },
        FakeNetwork { name: "neighbour"; signalStrength: 0.15 },
    ]

    component FakeDevice: QtObject {
        property string name
        property string deviceName: name
        property string address
        property string icon: ""
        property bool paired: false
        property bool bonded: paired
        property bool connected: false
        property bool trusted: paired
        property bool batteryAvailable: false
        property real battery: 0
        function connect() { root.record("bt connect " + name); connected = true }
        function disconnect() { root.record("bt disconnect " + name); connected = false }
        function pair() { root.record("bt pair " + name); paired = true }
        function forget() { root.record("bt forget " + name); paired = false; connected = false }
    }

    readonly property QtObject adapter: QtObject {
        property bool enabled: true
        property bool discovering: false
    }
    readonly property var devices: Array.from(devList)
    property list<QtObject> devList: [
        FakeDevice { name: "NG-PODS"; address: "0A:00:00:00:00:01"; icon: "audio-headset"; paired: true; connected: true; batteryAvailable: true; battery: 0.8 },
        FakeDevice { name: "deck mouse"; address: "0A:00:00:00:00:02"; icon: "input-mouse"; paired: true },
        FakeDevice { name: "Speaker X"; address: "0A:00:00:00:00:03"; icon: "audio-card" },
        FakeDevice { name: ""; address: "0A:00:00:00:00:04" },
    ]
}

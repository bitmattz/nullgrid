pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

// System readings for the bar and the HUD widgets, sampled every Theme.refreshMs (1 s, or 3 s
// with the lite profile) straight from /proc and /sys: no helper processes per tick.
Singleton {
    id: root

    property real cpu: 0                 // total, 0-100
    property var cores: []               // per core, 0-100
    property var load: [0, 0, 0]
    property real memUsed: 0             // bytes
    property real memTotal: 1
    readonly property real memPct: memTotal > 0 ? 100 * memUsed / memTotal : 0
    property real swapUsed: 0
    property real swapTotal: 0
    property real rxRate: 0              // bytes/s
    property real txRate: 0
    property var rxHistory: []           // last `historyLength` samples
    property var txHistory: []
    property var cpuHistory: []
    property real cpuTemp: NaN           // degrees C, NaN when unknown
    property real gpuTemp: NaN
    property real gpuBusy: NaN           // 0-100
    property real power: NaN             // watts drawn from the battery
    property bool discharging: false
    property real battery: NaN           // 0-100
    property real uptime: 0              // seconds
    readonly property int historyLength: 60

    property var _lastCpu: []
    property real _lastRx: -1
    property real _lastTx: -1
    property real _lastNetMs: 0

    // Paths found once at startup (hwmon numbering differs between machines).
    property string _cpuTempPath: ""
    property string _gpuTempPath: ""
    property string _gpuBusyPath: ""
    property string _batteryDir: ""

    function _push(list, value) {
        const out = list.concat([value])
        return out.length > historyLength ? out.slice(out.length - historyLength) : out
    }

    function _parseStat(text) {
        const rows = text.split("\n").filter(l => l.startsWith("cpu"))
        const now = rows.map(l => {
            const f = l.trim().split(/\s+/).slice(1).map(Number)
            const idle = f[3] + (f[4] || 0)
            const total = f.slice(0, 8).reduce((a, b) => a + b, 0)
            return [idle, total]
        })
        const pct = now.map((v, i) => {
            const p = root._lastCpu[i]
            if (!p) return 0
            const dt = v[1] - p[1]
            return dt > 0 ? Math.max(0, Math.min(100, 100 * (1 - (v[0] - p[0]) / dt))) : 0
        })
        root._lastCpu = now
        root.cpu = pct[0] || 0
        root.cores = pct.slice(1)
        root.cpuHistory = _push(cpuHistory, root.cpu)
    }

    function _parseMem(text) {
        const kv = {}
        for (const l of text.split("\n")) {
            const m = l.match(/^(\w+):\s+(\d+)/)
            if (m) kv[m[1]] = Number(m[2]) * 1024
        }
        root.memTotal = kv.MemTotal || 1
        root.memUsed = (kv.MemTotal || 0) - (kv.MemAvailable || 0)
        root.swapTotal = kv.SwapTotal || 0
        root.swapUsed = (kv.SwapTotal || 0) - (kv.SwapFree || 0)
    }

    function _parseNet(text) {
        let rx = 0, tx = 0
        for (const l of text.split("\n").slice(2)) {
            const m = l.trim().match(/^([^:]+):\s*(.*)$/)
            if (!m || m[1] === "lo") continue
            const f = m[2].split(/\s+/).map(Number)
            rx += f[0]; tx += f[8]
        }
        const now = Date.now()
        if (root._lastRx >= 0) {
            const dt = Math.max(0.001, (now - root._lastNetMs) / 1000)
            root.rxRate = Math.max(0, (rx - root._lastRx) / dt)
            root.txRate = Math.max(0, (tx - root._lastTx) / dt)
        }
        root._lastRx = rx; root._lastTx = tx; root._lastNetMs = now
        root.rxHistory = _push(rxHistory, root.rxRate)
        root.txHistory = _push(txHistory, root.txRate)
    }

    function _number(view, scale) {
        const v = parseFloat(view.text())
        return isNaN(v) ? NaN : v * scale
    }

    function sample() {
        stat.reload(); mem.reload(); net.reload(); loadavg.reload(); up.reload()
        _parseStat(stat.text())
        _parseMem(mem.text())
        _parseNet(net.text())
        root.load = loadavg.text().split(" ").slice(0, 3).map(Number)
        root.uptime = parseFloat(up.text()) || 0
        if (_cpuTempPath) { cpuTempFile.reload(); root.cpuTemp = _number(cpuTempFile, 0.001) }
        if (_gpuTempPath) { gpuTempFile.reload(); root.gpuTemp = _number(gpuTempFile, 0.001) }
        if (_gpuBusyPath) { gpuBusyFile.reload(); root.gpuBusy = _number(gpuBusyFile, 1) }
        if (_batteryDir) {
            batStatus.reload(); batCapacity.reload(); batPower.reload()
            root.discharging = batStatus.text().trim() === "Discharging"
            root.battery = _number(batCapacity, 1)
            root.power = _number(batPower, 1e-6)
        }
    }

    FileView { id: stat; path: "/proc/stat"; printErrors: false; blockLoading: true }
    FileView { id: mem; path: "/proc/meminfo"; printErrors: false; blockLoading: true }
    FileView { id: net; path: "/proc/net/dev"; printErrors: false; blockLoading: true }
    FileView { id: loadavg; path: "/proc/loadavg"; printErrors: false; blockLoading: true }
    FileView { id: up; path: "/proc/uptime"; printErrors: false; blockLoading: true }
    FileView { id: cpuTempFile; path: root._cpuTempPath; printErrors: false; blockLoading: true }
    FileView { id: gpuTempFile; path: root._gpuTempPath; printErrors: false; blockLoading: true }
    FileView { id: gpuBusyFile; path: root._gpuBusyPath; printErrors: false; blockLoading: true }
    FileView { id: batStatus; path: root._batteryDir ? root._batteryDir + "/status" : ""; printErrors: false; blockLoading: true }
    FileView { id: batCapacity; path: root._batteryDir ? root._batteryDir + "/capacity" : ""; printErrors: false; blockLoading: true }
    FileView { id: batPower; path: root._batteryDir ? root._batteryDir + "/power_now" : ""; printErrors: false; blockLoading: true }

    // One-off discovery of the sensor files: "<kind> <path>" per line.
    Process {
        running: true
        command: ["sh", "-c", `
            for h in /sys/class/hwmon/hwmon*; do
                n=$(cat "$h/name" 2>/dev/null); t="$h/temp1_input"; [ -r "$t" ] || continue
                case $n in
                    coretemp|k10temp|zenpower|cpu_thermal|soc_thermal) echo "cpu $t" ;;
                    amdgpu|nouveau|radeon|xe|i915) echo "gpu $t" ;;
                    acpitz) echo "cpu? $t" ;;
                esac
            done
            for f in /sys/class/drm/card*/device/gpu_busy_percent; do [ -r "$f" ] && echo "gpubusy $f" && break; done
            for b in /sys/class/power_supply/BAT*; do [ -r "$b/capacity" ] && echo "battery $b" && break; done
        `]
        stdout: StdioCollector {
            onStreamFinished: {
                let fallback = ""
                for (const line of text.split("\n")) {
                    const [kind, path] = line.split(" ")
                    if (kind === "cpu" && !root._cpuTempPath) root._cpuTempPath = path
                    else if (kind === "cpu?") fallback = path
                    else if (kind === "gpu" && !root._gpuTempPath) root._gpuTempPath = path
                    else if (kind === "gpubusy") root._gpuBusyPath = path
                    else if (kind === "battery") root._batteryDir = path
                }
                if (!root._cpuTempPath) root._cpuTempPath = fallback
            }
        }
    }

    Timer {
        interval: Theme.refreshMs
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: root.sample()
    }

    // -- formatting helpers shared by the bar and the widgets ---------------------
    function bytes(v) {
        const units = ["B", "K", "M", "G", "T"]
        let i = 0
        while (v >= 1024 && i < units.length - 1) { v /= 1024; i++ }
        return (v >= 100 || i === 0 ? Math.round(v) : v.toFixed(1)) + units[i]
    }
    function pct(v) { return isNaN(v) ? "--" : Math.round(v) + "%" }
    function temp(v) { return isNaN(v) ? "--" : Math.round(v) + "°" }
}

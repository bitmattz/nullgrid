import QtQuick

// Download/upload over the last minute, with a labeled scale.
HudPanel {
    id: root
    title: "NETWORK"
    caption: "↓ " + Sys.bytes(Sys.rxRate) + "/s   ↑ " + Sys.bytes(Sys.txRate) + "/s"
    implicitWidth: 360; implicitHeight: 120

    // A round number above the busiest sample, so the scale reads well: 1K, 2K, 5K, 10K...
    readonly property real scaleTop: {
        const peak = Math.max(1024, ...Sys.rxHistory, ...Sys.txHistory)
        let step = 1024
        while (step < peak) step *= step.toString()[0] === "1" ? 2 : step.toString()[0] === "2" ? 2.5 : 2
        return step
    }

    Canvas {
        id: canvas
        anchors { fill: parent; leftMargin: 44 }
        property var rx: Sys.rxHistory
        property var tx: Sys.txHistory
        onRxChanged: requestPaint()
        onWidthChanged: requestPaint()
        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            const w = width, h = height, n = Sys.historyLength
            ctx.strokeStyle = Theme.alpha(Theme.dim, 0.25)
            ctx.lineWidth = 1
            for (let i = 0; i <= 2; i++) {
                const y = Math.round(i * (h - 1) / 2) + 0.5
                ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke()
            }
            function line(values, color, fill) {
                if (values.length < 2) return
                ctx.beginPath()
                values.forEach((v, i) => {
                    const x = w - (values.length - 1 - i) * w / (n - 1)
                    const y = h - 1 - Math.min(1, v / root.scaleTop) * (h - 2)
                    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
                })
                ctx.strokeStyle = color
                ctx.lineWidth = 1.5
                ctx.stroke()
                if (fill) {
                    ctx.lineTo(w, h); ctx.lineTo(w - (values.length - 1) * w / (n - 1), h); ctx.closePath()
                    ctx.fillStyle = Theme.alpha(Theme.primary, 0.12)
                    ctx.fill()
                }
            }
            line(rx, Theme.primary, true)
            line(tx, Theme.secondary, false)
        }
    }
    Column {  // the scale
        anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
        NgText { mono: true; height: parent.height / 2; verticalAlignment: Text.AlignTop; font.pixelSize: 10; color: Theme.dim; text: Sys.bytes(root.scaleTop) }
        NgText { mono: true; height: parent.height / 2; verticalAlignment: Text.AlignBottom; font.pixelSize: 10; color: Theme.dim; text: "0" }
    }
}

pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

// UI sounds. play("button_click") hands the event to the nullgrid-sfx daemon over its socket;
// the daemon decides whether and how loud ([sound] in nullgrid.toml). Without a daemon this
// does nothing, and it never waits for anything.
Singleton {
    id: root
    readonly property string path: (Quickshell.env("XDG_RUNTIME_DIR") || "/tmp") + "/nullgrid-sfx.sock"
    property string pending: ""
    property real pendingAt: 0

    function play(event) {
        if (sock.connected) {
            sock.write("play " + event + "\n")
            sock.flush()
        } else {  // (re)connect, e.g. after the daemon restarted; send it once connected
            pending = event
            pendingAt = Date.now()
            sock.connected = true
        }
    }

    Socket {
        id: sock
        path: root.path
        onConnectionStateChanged: {
            if (connected && root.pending && Date.now() - root.pendingAt < 500) {
                write("play " + root.pending + "\n")
                flush()
            }
            root.pending = ""
        }
        onError: root.pending = ""
    }
}

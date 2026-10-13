"""The `nullgrid-sfx` command.

  nullgrid-sfx daemon [--no-startup-sound]   run the daemon (the desktop session starts it)
  nullgrid-sfx play EVENT [--wait]           play an event's sound through the daemon
  nullgrid-sfx status | reload | quit        talk to the running daemon

`play` is called from key bindings and scripts, so it only imports the standard library and
hands the event to the daemon. With no daemon running (e.g. on a TTY) it plays the sound itself.
"""
from __future__ import annotations

import os
import signal
import socket
import sys

USAGE = __doc__.split("\n\n")[1]


def _socket_path() -> str:
    # same rule as nullgrid.sound.socket_path(), without importing nullgrid (slow start)
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime and os.path.isdir(runtime):
        return os.path.join(runtime, "nullgrid-sfx.sock")
    return f"/tmp/nullgrid-sfx-{os.getuid()}.sock"


def _request(line: str, timeout: float, reply: bool) -> str | None:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(_socket_path())
        s.sendall(line.encode() + b"\n")
        if not reply:
            return ""
        s.shutdown(socket.SHUT_WR)
        data = b""
        while chunk := s.recv(4096):
            data += chunk
        return data.decode(errors="replace").strip()
    except OSError:
        return None
    finally:
        s.close()


def play_direct(event: str, wait: bool) -> int:
    """No daemon: apply the config's rules here and play with pw-play."""
    from nullgrid import config as cfgmod
    from nullgrid import paths as pathmod
    from nullgrid import sound

    if event not in cfgmod.SOUND_EVENTS:
        print(f"nullgrid-sfx: unknown event {event!r}", file=sys.stderr)
        return 2
    paths = pathmod.resolve()
    try:
        cfg = cfgmod.load(paths).config["sound"]
        where = sound.find_pack(paths, cfg["pack"])
        pack = sound.load_pack(where) if where else None
    except cfgmod.ConfigError as exc:
        print(f"nullgrid-sfx: {exc}", file=sys.stderr)
        return 1
    if pack is None or event not in pack.sounds:
        return 0
    s = pack.sounds[event]
    sound.play(s.path, sound.volume(cfg, event, s.volume), wait=wait)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0 if args else 2
    cmd, rest = args[0], args[1:]

    if cmd == "daemon":
        import logging

        from nullgrid import paths as pathmod

        from . import daemon
        paths = pathmod.resolve()
        logfile = None
        if not sys.stderr.isatty():  # started by the session: log to ~/.local/state/nullgrid/sfx.log
            paths.state_dir.mkdir(parents=True, exist_ok=True)
            logfile = str(paths.state_dir / "sfx.log")
        logging.basicConfig(level=logging.INFO, filename=logfile, filemode="w",
                            format="%(asctime)s nullgrid-sfx: %(message)s", datefmt="%H:%M:%S")
        return daemon.run(paths, startup_sound="--no-startup-sound" not in rest)

    # a reload signal (sent to every process named nullgrid-sfx) must not kill a client
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    if cmd == "play" and rest:
        event, wait = rest[0], "--wait" in rest
        if wait:
            answer = _request(f"playwait {event}", timeout=5, reply=True)
        else:
            answer = _request(f"play {event}", timeout=0.5, reply=False)
        return play_direct(event, wait) if answer is None else 0
    if cmd in ("status", "reload", "quit"):
        answer = _request(cmd, timeout=2, reply=True)
        if answer is None:
            print("nullgrid-sfx: the daemon is not running (start it with: nullgrid-sfx daemon &)", file=sys.stderr)
            return 1
        print(answer)
        return 0
    print(USAGE, file=sys.stderr)
    return 2

"""The nullgrid-sfx daemon: one process per session, idle in select() until something happens.

Inputs, all in one selector loop:
  - its unix socket ($XDG_RUNTIME_DIR/nullgrid-sfx.sock), one command per line:
      play EVENT       play it (if the config allows); no reply
      playwait EVENT   play it, reply "done" when it finished (logout/shutdown sounds)
      status           reply with one line of JSON
      reload           re-read the config (same as SIGHUP)
      quit             exit
    The shell (Quickshell Socket), nullgrid-sfx play, zsh hooks and scripts use it.
  - the compositor's event stream: Hyprland's socket2 or `swaymsg -t subscribe`. When it ends,
    the session is over and the daemon exits.
  - `udevadm monitor` for USB devices and power supplies, plus a slow poll of the battery.

Playing never blocks: each sound is a pw-play child, reaped on SIGCHLD.
"""
from __future__ import annotations

import ctypes
import errno
import json
import logging
import os
import selectors
import signal
import socket
import subprocess
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from nullgrid import config as cfgmod
from nullgrid import sound
from nullgrid.paths import Paths

from . import sources

log = logging.getLogger("nullgrid-sfx")

MIN_GAP = 0.08          # s between two plays of the same event (bursts of window events)
MAX_PLAYING = 4         # sounds at once; more are dropped
POWER_POLL = 60         # s between battery checks (udev usually reports changes sooner)
STARTUP_DELAY = 1.0     # s before the boot/login sound: lets PipeWire settle at session start


@dataclass
class Playing:
    proc: subprocess.Popen
    event: str
    waiter: socket.socket | None = None   # a `playwait` client to answer when done


@dataclass
class Stream:
    """A line-oriented input: a socket or a child's stdout."""
    name: str
    fileobj: object
    on_line: Callable[[str], None]
    on_close: Callable[[], None]
    buf: bytes = b""
    proc: subprocess.Popen | None = None


@dataclass
class Daemon:
    paths: Paths
    sysfs: Path = Path("/sys/class/power_supply")
    player: list[str] | None = field(default_factory=sound.player)
    clock: Callable[[], float] = time.monotonic

    def __post_init__(self):
        self.cfg: dict = {}
        self.pack: sound.Pack | None = None
        self.last: dict[str, float] = {}
        self.playing: list[Playing] = []
        self.played = 0
        self.recent: deque[str] = deque(maxlen=12)  # last events played, for `status`
        self.sources: list[str] = []
        self.running = True
        self.power = sources.read_power(self.sysfs)
        self.next_power_poll = self.clock() + POWER_POLL

    # ------------------------------------------------------------------ config
    def load(self) -> None:
        """Read the generated sfx.json (falls back to nullgrid.toml) and the selected pack."""
        f = self.paths.config_dir / "generated" / "sfx.json"
        try:
            self.cfg = json.loads(f.read_text())
        except (OSError, ValueError):
            try:
                self.cfg = cfgmod.load(self.paths).config["sound"]
            except cfgmod.ConfigError as exc:
                log.warning("config: %s; using defaults", exc)
                self.cfg = cfgmod.SOUND.validate({}, "sound", [])
        self.pack = None
        name = self.cfg.get("pack", "")
        where = sound.find_pack(self.paths, name)
        if where is None:
            log.warning("no sound pack named %r (available: %s)", name, ", ".join(sound.list_packs(self.paths)) or "none")
            return
        try:
            self.pack = sound.load_pack(where)
        except cfgmod.ConfigError as exc:
            log.warning("sound pack: %s", exc)
            return
        log.info("pack %s (%d sounds), %s, volume %s", self.pack.name, len(self.pack.sounds),
                 "on" if self.cfg.get("enabled") else "muted", self.cfg.get("volume"))

    # ------------------------------------------------------------------ playing
    def trigger(self, event: str, waiter: socket.socket | None = None) -> bool:
        """Play event if the config, the pack and the rate limits allow. True if it started."""
        started = self._start(event, waiter)
        if not started and waiter is not None:
            _reply(waiter, "skipped")
        return started

    def _start(self, event: str, waiter: socket.socket | None) -> bool:
        if self.pack is None or self.player is None or event not in self.pack.sounds:
            return False
        s = self.pack.sounds[event]
        try:
            vol = sound.volume(self.cfg, event, s.volume)
        except (KeyError, TypeError, ValueError):
            return False
        if vol <= 0:
            return False
        now = self.clock()
        if now - self.last.get(event, -1e9) < MIN_GAP or len(self.playing) >= MAX_PLAYING:
            return False
        cmd = sound.play_command(s.path, vol, self.player)
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
        except OSError as exc:
            log.warning("can't run %s: %s", cmd[0], exc)
            return False
        self.last[event] = now
        self.playing.append(Playing(proc, event, waiter))
        self.played += 1
        self.recent.append(event)
        return True

    def reap(self) -> list[socket.socket]:
        """Forget finished sounds; answer their `playwait` clients (returned)."""
        still, answered = [], []
        for p in self.playing:
            if p.proc.poll() is None:
                still.append(p)
            elif p.waiter is not None:
                _reply(p.waiter, "done")
                answered.append(p.waiter)
        self.playing = still
        return answered

    # ------------------------------------------------------------------ commands
    def command(self, line: str, conn: socket.socket | None = None) -> str | None:
        """Handle one socket command; returns a reply line, or None for no reply (yet)."""
        verb, _, arg = line.strip().partition(" ")
        arg = arg.strip()
        if verb == "play" and arg:
            self.trigger(arg)
        elif verb == "playwait" and arg:
            self.trigger(arg, waiter=conn)
        elif verb == "status":
            return json.dumps(self.status(), sort_keys=True)
        elif verb == "reload":
            self.load()
            return "ok"
        elif verb == "quit":
            self.running = False
            return "bye"
        elif verb:
            log.info("unknown command %r", line.strip()[:80])
        return None

    def status(self) -> dict:
        return {
            "pid": os.getpid(),
            "pack": self.pack.name if self.pack else None,
            "enabled": bool(self.cfg.get("enabled")),
            "volume": self.cfg.get("volume"),
            "player": self.player[0] if self.player else None,
            "played": self.played,
            "recent": list(self.recent),
            "sources": self.sources,
        }

    # ------------------------------------------------------------------ power
    def check_power(self) -> None:
        now = sources.read_power(self.sysfs)
        for event in sources.power_events(self.power, now):
            self.trigger(event)
        self.power = now
        self.next_power_poll = self.clock() + POWER_POLL

    def on_udev(self, line: str) -> None:
        parsed = sources.udev_event(line)
        if parsed is None:
            return
        action, subsystem = parsed
        if subsystem == "usb" and (event := sources.usb_event(action)):
            self.trigger(event)
        elif subsystem == "power_supply":
            self.check_power()


# =========================================================================== the loop
def _reply(conn: socket.socket, text: str) -> None:
    try:
        conn.settimeout(1)
        conn.sendall(text.encode() + b"\n")
    except OSError:
        pass
    finally:
        try:
            conn.setblocking(False)
        except OSError:
            pass


def first_sound(paths: Paths) -> str:
    """'boot' for the first session since the machine started, 'login' after that."""
    try:
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return "login"
    marker = paths.state_dir / "sfx-boot-id"
    try:
        if marker.read_text().strip() == boot_id:
            return "login"
    except OSError:
        pass
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(boot_id + "\n")
    except OSError:
        pass
    return "boot"


def take_socket(path: Path) -> socket.socket:
    """Listen on path. A daemon already there (an older session's) is asked to quit first."""
    if path.exists():
        old = sound.request("quit", timeout=1, reply=True)
        if old is not None:
            log.info("replaced the running daemon")
            time.sleep(0.2)
        path.unlink(missing_ok=True)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(path))
    os.chmod(path, 0o600)
    srv.listen(16)
    srv.setblocking(False)
    return srv


def set_process_name(name: str = "nullgrid-sfx") -> None:
    """`nullgrid theme reload` finds the daemon by process name (manifest: process =
    "nullgrid-sfx") to send SIGHUP; make sure that's the name, however it was started."""
    try:
        ctypes.CDLL(None, use_errno=True).prctl(15, name.encode(), 0, 0, 0)  # PR_SET_NAME
    except (OSError, AttributeError):
        pass


def run(paths: Paths, startup_sound: bool = True) -> int:
    set_process_name()
    d = Daemon(paths)
    d.load()
    if d.player is None:
        log.warning("no audio player found (pw-play, paplay or aplay): staying silent")
    sel = selectors.DefaultSelector()
    sock_path = sound.socket_path()
    srv = take_socket(sock_path)
    sock_inode = os.stat(sock_path).st_ino
    streams: dict[int, Stream] = {}

    # signals arrive through a pipe, so select() wakes up for them
    rfd, wfd = os.pipe()
    os.set_blocking(rfd, False)
    os.set_blocking(wfd, False)
    signal.set_wakeup_fd(wfd, warn_on_full_buffer=False)
    pending: list[int] = []
    for sig in (signal.SIGCHLD, signal.SIGHUP, signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda s, _f: pending.append(s))
    sel.register(rfd, selectors.EVENT_READ, "signals")
    sel.register(srv, selectors.EVENT_READ, "accept")

    def add_stream(st: Stream) -> None:
        streams[st.fileobj.fileno()] = st
        sel.register(st.fileobj, selectors.EVENT_READ, "stream")
        d.sources.append(st.name)

    def drop_stream(st: Stream) -> None:
        sel.unregister(st.fileobj)
        streams.pop(st.fileobj.fileno(), None)
        st.fileobj.close()
        if st.proc:
            st.proc.terminate()
        if st.name in d.sources:
            d.sources.remove(st.name)
        st.on_close()

    def session_over() -> None:
        log.info("the compositor is gone: exiting")
        d.running = False

    # -- compositor events
    if hypr := sources.hyprland_socket():
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            s.connect(str(hypr))
            s.setblocking(False)
            add_stream(Stream("hyprland", s, lambda l: _event(d, sources.hyprland_event(l)), session_over))
        except OSError as exc:
            log.warning("hyprland events: %s", exc)
            s.close()
    elif os.environ.get("SWAYSOCK"):
        proc = _spawn(sources.SWAY_SUBSCRIBE)
        if proc:
            add_stream(Stream("sway", proc.stdout, lambda l: _event(d, sources.sway_event(l)), session_over, proc=proc))
    # -- udev: USB devices, power supplies
    if proc := _spawn(sources.UDEV_MONITOR):
        add_stream(Stream("udev", proc.stdout, d.on_udev, lambda: None, proc=proc))

    if startup_sound:
        first = first_sound(paths)
        start_at = d.clock() + STARTUP_DELAY
    else:
        first, start_at = "", 0.0
    log.info("listening on %s; sources: %s", sock_path, ", ".join(d.sources) or "none")

    clients: dict[int, tuple[socket.socket, bytearray]] = {}
    try:
        while d.running:
            now = d.clock()
            timeout = d.next_power_poll - now
            if first:
                timeout = min(timeout, start_at - now)
            for key, _ in sel.select(max(0.0, timeout)):
                kind = key.data
                if kind == "signals":
                    try:
                        os.read(rfd, 512)
                    except BlockingIOError:
                        pass
                elif kind == "accept":
                    try:
                        conn, _ = srv.accept()
                    except OSError:
                        continue
                    conn.setblocking(False)
                    clients[conn.fileno()] = (conn, bytearray())
                    sel.register(conn, selectors.EVENT_READ, "client")
                elif kind == "client":
                    _read_client(d, sel, key.fileobj, clients)
                elif kind == "stream":
                    _read_stream(streams[key.fileobj.fileno()], drop_stream)
            while pending:
                sig = pending.pop()
                if sig == signal.SIGHUP:
                    d.load()
                elif sig in (signal.SIGTERM, signal.SIGINT):
                    d.running = False
            for conn in d.reap():
                if conn.fileno() not in clients:  # its client already hung up: close it now
                    conn.close()
            if first and d.clock() >= start_at:
                d.trigger(first)
                first = ""
            if d.clock() >= d.next_power_poll:
                d.check_power()
    finally:
        for st in list(streams.values()):
            if st.proc:
                st.proc.terminate()
        for conn, _ in clients.values():
            conn.close()
        srv.close()
        try:  # unless a newer daemon has taken the path over already
            if os.stat(sock_path).st_ino == sock_inode:
                sock_path.unlink()
        except OSError:
            pass
    return 0


def _event(d: Daemon, event: str | None) -> None:
    if event:
        d.trigger(event)


def _spawn(argv: list[str]) -> subprocess.Popen | None:
    try:
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL)
    except OSError as exc:
        log.info("%s not available: %s", argv[0], exc)
        return None
    os.set_blocking(proc.stdout.fileno(), False)
    return proc


def _read_stream(st: Stream, drop: Callable[[Stream], None]) -> None:
    try:
        data = st.fileobj.recv(65536) if isinstance(st.fileobj, socket.socket) else os.read(st.fileobj.fileno(), 65536)
    except (BlockingIOError, InterruptedError):
        return
    except OSError:
        data = b""
    if not data:
        drop(st)
        return
    st.buf += data
    *lines, st.buf = st.buf.split(b"\n")
    for line in lines:
        st.on_line(line.decode(errors="replace"))


def _read_client(d: Daemon, sel: selectors.BaseSelector, conn: socket.socket,
                 clients: dict[int, tuple[socket.socket, bytearray]]) -> None:
    fd = conn.fileno()
    _, buf = clients[fd]
    try:
        data = conn.recv(4096)
    except (BlockingIOError, InterruptedError):
        return
    except OSError as exc:
        data = b"" if exc.errno != errno.EAGAIN else None
        if data is None:
            return
    buf += data
    while b"\n" in buf:
        line, _, rest = bytes(buf).partition(b"\n")
        buf[:] = rest
        reply = d.command(line.decode(errors="replace"), conn)
        if reply is not None:
            _reply(conn, reply)
    if not data or len(buf) > 4096:
        # the client closed its side (or sends garbage). A `playwait` client keeps its
        # connection until the sound finished; Daemon.reap answers and the close happens here.
        sel.unregister(conn)
        del clients[fd]
        if not any(p.waiter is conn for p in d.playing):
            conn.close()

#!/usr/bin/env python3
"""Headless boot smoke test: boot the ISO, log in over serial, check the live system.

tty1 logs in by itself and starts the desktop. Through the QEMU monitor the test screenshots it,
presses keys there and saves PNGs to out/screens/ for a human to look at, while the serial
console checks the session: Hyprland, then Sway (the lite profile), then TTY mode (the dashboard).
The VM's sound card records to a WAV file, so the test can tell that sounds really come out.

Usage: boot_smoke.py [--bios] [iso]   (normally via `make test-boot`)
Env:   BOOT_TIMEOUT  seconds to wait for the shell prompt (default 600; TCG is slow)
"""
import os
import re
import socket
import struct
import subprocess
import tempfile
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOT_TIMEOUT = int(os.environ.get("BOOT_TIMEOUT", "600"))
PROMPT = "nullgrid@nullgrid"
SCREENS = os.path.join(ROOT, "out", "screens")
ANSI = re.compile(r"\x1b(\[[0-9;?]*[ -/]*[@-~]|\][^\x07\x1b]*(\x07|\x1b\\)|P[^\x1b]*\x1b\\|.)")

CHECKS = [
    # (command, regex that one output line must fully match)
    ("systemctl is-system-running --wait", r"running"),
    (". /etc/os-release; echo ID=$ID", r"ID=nullgrid"),
    ("id -nG", r".*\bwheel\b.*"),
    ("sudo -n true && echo SUDO_OK", r"SUDO_OK"),
    ("systemctl is-active NetworkManager", r"active"),
    ("nullgrid --version", r"nullgrid \d+\.\d+\.\d+"),
    ("nullgrid theme set ice-protocol >/dev/null && grep -o '\"name\": \"[a-z-]*\"' ~/.config/nullgrid/generated/theme.json",
     r'"name": "ice-protocol"'),
    ("nullgrid doctor >/dev/null && echo DOCTOR_OK", r"DOCTOR_OK"),
    # phase 3: the terminal experience (first login ran `nullgrid init`)
    ("nullgrid-dash --check | tail -1", r"DASH_OK"),
    ("fastfetch --pipe | grep -o 'NULLGRID OS // x86_64'", r"NULLGRID OS // x86_64"),
    ("nvim --headless -c 'lua io.stdout:write(vim.g.colors_name .. \"\\n\")' -c qa", r"nullgrid"),
    ("tmux new-session -d -s t && tmux show -gv status-left | grep -o ' NG '; tmux kill-server", r"NG"),
    ("for c in starship starship-tty; do STARSHIP_CONFIG=~/.config/$c.toml starship prompt 2>&1 >/dev/null; done"
     " | grep -ci warn", r"0"),
    ("fc-list : family | grep -xE 'Rajdhani|Orbitron|JetBrains Mono' | sort -u | tr '\\n' ,",
     r"JetBrains Mono,Orbitron,Rajdhani,"),
    ("kitty +runpy 'from kitty.config import load_config; print(load_config(\"'$HOME'/.config/kitty/kitty.conf\").font_family)'",
     r"JetBrains Mono"),
]
# Phase 4: the desktop on tty1. ENV points this serial shell at the session's compositor.
ENV = ("export XDG_RUNTIME_DIR=/run/user/$(id -u); "
       "export WAYLAND_DISPLAY=$(cd $XDG_RUNTIME_DIR && ls -d wayland-? | head -1); "
       "export HYPRLAND_INSTANCE_SIGNATURE=$(ls -t $XDG_RUNTIME_DIR/hypr 2>/dev/null | head -1); "
       "export SWAYSOCK=$(ls $XDG_RUNTIME_DIR/sway-ipc.*.sock 2>/dev/null | head -1)")
HYPRLAND_CHECKS = [
    ("Hyprland --verify-config -c ~/.config/hypr/hyprland.lua 2>&1 | tail -1", r"config ok"),
    ("hyprctl configerrors -j | tr -d ' \\t\\n'", r'\[(""|)\]'),
    ("hyprctl monitors | grep -o '1600x900'", r"1600x900"),
    ("pgrep -x swaybg >/dev/null && ls ~/.cache/nullgrid/wallpaper/ | grep -c 1600x900", r"[1-9]"),
    ("hyprctl binds | grep -c 'dispatcher'", r"[1-9]\d+"),
]
# Phase 6: PipeWire and the sound daemon in the Hyprland session (status JSON has sorted keys)
SOUND_CHECKS = [
    ("systemctl --user is-active pipewire wireplumber pipewire-pulse.socket | sort -u | tr '\\n' ' '", r"active"),
    ("wpctl inspect @DEFAULT_AUDIO_SINK@ | grep -o 'api.alsa.pcm.card = \"[0-9]\"'", r'api.alsa.pcm.card = "\d"'),
    # the first session after boot plays the boot sound
    ("nullgrid-sfx status", r'.*"pack": "neural-link".*"recent": \[[^]]*"boot".*"sources": \["hyprland", "udev"\].*'),
    ("nullgrid doctor | grep -E 'sound|PipeWire' | grep -vc '^\\[ ok \\]'", r"0"),
    # cava needs an audio server; without one it crashed (phase 3)
    ("TERM=linux timeout 3 script -qc 'cava -p ~/.config/cava/config-tty' /dev/null >/dev/null 2>&1; echo cava=$?", r"cava=124"),
]
# Run when a check fails, to make the report actionable.
DIAGNOSTICS = "systemctl --failed --no-legend --plain --full; journalctl -b -p warning --no-pager -o cat | tail -n 30"


class Console:
    """Serial console of the VM as one growing text buffer."""

    def __init__(self, cmd):
        self.vm = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, bufsize=0)
        self.raw = ""
        self.text = ""
        self.pos = 0  # everything before this has been consumed by wait_for
        self.lock = threading.Condition()
        self.alive = True
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        try:
            while chunk := os.read(self.vm.stdout.fileno(), 4096):
                with self.lock:
                    self.raw += chunk.decode(errors="replace")
                    # Strip escapes on the whole buffer: one sequence may span two chunks.
                    self.text = ANSI.sub("", self.raw).replace("\r", "")
                    self.lock.notify_all()
        finally:
            with self.lock:
                self.alive = False
                self.lock.notify_all()

    def wait_for(self, needle: str, timeout: float) -> str:
        """Return the text between the last consumed position and needle."""
        deadline = time.monotonic() + timeout
        with self.lock:
            while (i := self.text.find(needle, self.pos)) < 0:
                left = deadline - time.monotonic()
                if left <= 0:
                    raise TimeoutError(f"timed out waiting for {needle!r}")
                if not self.alive:
                    raise RuntimeError("VM exited")
                self.lock.wait(min(left, 1))
            out, self.pos = self.text[self.pos:i], i + len(needle)
            return out

    def send(self, line: str):
        self.vm.stdin.write(line.encode() + b"\n")
        self.vm.stdin.flush()

    def run(self, command: str, timeout: float = 180) -> list[str]:
        # The marker is spelled with $((...)) so the echoed command line never matches it.
        self.send(f"{command}; echo __D$((1))NE__")
        out = self.wait_for("__D1NE__", timeout)
        return [l.strip() for l in out.splitlines() if l.strip() and "__D$((1))NE__" not in l]


class Monitor:
    """The QEMU human monitor on a unix socket: screenshots and key presses for tty1."""

    def __init__(self, path: str):
        self.path = path
        self.sock: socket.socket | None = None

    def cmd(self, line: str) -> str:
        if self.sock is None:
            self.sock = socket.socket(socket.AF_UNIX)
            self.sock.connect(self.path)
            self._read()
        self.sock.sendall(line.encode() + b"\n")
        return self._read()

    def _read(self) -> str:
        buf = b""
        self.sock.settimeout(30)
        while not buf.endswith(b"(qemu) "):
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            buf += chunk
        return buf.decode(errors="replace")

    def screenshot(self, name: str) -> str:
        """Saves out/screens/<name>.png and prints where."""
        os.makedirs(SCREENS, exist_ok=True)
        path = os.path.join(SCREENS, f"{name}.png")
        self.cmd(f"screendump {path} -f png")
        uid, gid = os.environ.get("HOST_UID"), os.environ.get("HOST_GID")
        if uid and gid and os.path.exists(path):
            for p in (SCREENS, path):
                os.chown(p, int(uid), int(gid))
        print(f"[info] screenshot {os.path.relpath(path, ROOT)}")
        return path

    def keys(self, *names: str) -> None:
        for k in names:
            self.cmd(f"sendkey {k}")
            time.sleep(0.2)


def tty1_tour(mon: Monitor) -> None:
    """Screenshot the dashboard on tty1, switch theme from it, quit to the shell prompt."""
    mon.screenshot("tty1-dashboard")
    mon.keys("t")                  # next theme, restyles the console live
    time.sleep(6)
    mon.screenshot("tty1-dashboard-next-theme")
    mon.keys("q")                  # leave the dashboard
    time.sleep(3)
    mon.keys("l", "s", "spc", "minus", "a", "ret")
    time.sleep(2)
    mon.screenshot("tty1-shell")


class Recording:
    """The VM's sound card output, which QEMU writes to a WAV file (16-bit PCM)."""

    def __init__(self, path: str):
        self.path = path

    def size(self) -> int:
        return os.path.getsize(self.path) if os.path.exists(self.path) else 0

    def peak(self, since: int) -> float:
        """Loudest sample (0-1) written after byte offset `since`."""
        with open(self.path, "rb") as fh:
            fh.seek(max(44, since - since % 4))
            data = fh.read()
        data = data[: len(data) - len(data) % 2]
        samples = struct.unpack(f"<{len(data) // 2}h", data)
        return max((abs(v) for v in samples), default=0) / 32768


class Checker:
    def __init__(self, con: Console):
        self.con = con
        self.failures: list[str] = []

    def verify(self, what: str, ok: bool, detail: str = "") -> bool:
        """A check made on this side (not a command in the VM)."""
        print(f"[{'ok' if ok else 'FAIL'}] {what}  ->  {detail}")
        if not ok:
            self.failures.append(what)
        return ok

    def check(self, command: str, expect: str, timeout: float = 180) -> bool:
        body = self.con.run(command, timeout)
        ok = any(re.fullmatch(expect, l) for l in body)
        print(f"[{'ok' if ok else 'FAIL'}] {command[:120]}  ->  {' | '.join(body)[-200:]}")
        if not ok:
            self.failures.append(command)
        return ok

    def wait(self, command: str, expect: str, seconds: int) -> bool:
        """Poll on the VM side until command prints a line matching expect."""
        loop = (f"for i in $(seq {seconds}); do out=$({command}); "
                f"printf '%s\\n' \"$out\" | grep -qxE '{expect}' && break; sleep 1; done; printf '%s\\n' \"$out\"")
        return self.check(loop, expect, seconds + 60)

    def info(self, command: str) -> None:
        print(f"[info] {command[:60]}  ->  {' | '.join(self.con.run(command, 60))[-300:]}")


def restart_tty1(c: Checker) -> None:
    """Log tty1 in again (autologin), so it starts whatever the config now says."""
    c.con.run("sudo systemctl restart getty@tty1", 60)


def sound_tour(c: Checker, mon: Monitor, rec: Recording) -> None:
    for command, expect in SOUND_CHECKS:
        c.check(command, expect)
    c.wait("nullgrid-shell status", r".* audio=true", 20)  # the bar's volume control has a sink
    # a sound played in the VM reaches its sound card
    time.sleep(6)  # PipeWire suspends the idle card after ~5 s: start from silence
    before = rec.size()
    c.con.run("nullgrid sound test notification", 30)
    time.sleep(1)
    peak = rec.peak(before)
    c.verify("sound reaches the VM's sound card", peak > 0.02,
             f"peak {peak:.3f} in {rec.size() - before} bytes recorded")
    # the volume-up key: a Hyprland bind -> nullgrid-media -> wpctl, plus a tick
    c.con.run("wpctl set-volume @DEFAULT_AUDIO_SINK@ 0.5", 30)
    mon.keys("volumeup")
    c.wait("wpctl get-volume @DEFAULT_AUDIO_SINK@", r"Volume: 0\.55", 10)
    c.wait("nullgrid-sfx status", r'.*"recent": \[[^]]*"volume_change".*', 10)


def desktop_tour(c: Checker, mon: Monitor, rec: Recording) -> None:
    # -- Hyprland (desktop mode is the default) --
    if not c.wait("pgrep -x Hyprland >/dev/null && echo UP", "UP", 120):
        c.info("cat ~/.local/state/nullgrid/session-*.log | tail -20")
        return
    c.wait("pgrep -x swaybg >/dev/null && echo UP", "UP", 60)
    c.con.run(ENV, 30)
    c.wait("nullgrid-shell status 2>/dev/null", r"theme=\S+ wm=HYPRLAND .*", 60)
    # the test VM's virtio-gpu has no 3D: the session must notice (the shell then skips animations)
    c.check("tr '\\0' '\\n' < /proc/$(pgrep -x Hyprland)/environ | grep -x NULLGRID_SOFTWARE_RENDER=1",
            r"NULLGRID_SOFTWARE_RENDER=1")
    for command, expect in HYPRLAND_CHECKS:
        c.check(command, expect)
    sound_tour(c, mon, rec)
    # the login terminal (kitty takes a few seconds to map under software rendering)
    if not c.wait("hyprctl clients | grep -c 'class: nullgrid-welcome'", "1", 30):
        c.info("pgrep -a kitty; hyprctl clients | grep -E 'class|title'; ls -t ~/.local/state/nullgrid/")
    time.sleep(4)  # kitty draws fastfetch
    mon.screenshot("desktop-hyprland")
    c.info("free -m | awk '/Mem/ {print \"used MB:\", $3}'")
    c.check("nullgrid theme set toxic-grid | grep -o 'reloaded: .*'", r"reloaded: .*hyprland.*wallpaper.*")
    c.wait("nullgrid-shell status", r"theme=toxic-grid .*", 20)     # the shell restyled itself
    time.sleep(5)
    mon.screenshot("desktop-hyprland-toxic-grid")
    c.con.run("notify-send -a nullgrid 'Uplink established' 'Node 2.2 is online.';"
              " notify-send -a battery -u critical 'Battery critical' '5% left, plug in the charger.'", 30)
    time.sleep(3)
    mon.screenshot("desktop-hyprland-notifications")
    mon.keys("meta_l-spc")         # start menu
    if c.wait("nullgrid-shell status", r".* menu=true .*", 20):
        time.sleep(2)
        mon.screenshot("desktop-hyprland-menu")
    mon.keys("esc")
    c.wait("nullgrid-shell status", r".* menu=false .*", 20)
    mon.keys("meta_l-slash")       # keybind help popup
    time.sleep(4)
    mon.screenshot("desktop-hyprland-keys")
    c.check("hyprctl clients | grep -c 'class: nullgrid-keys'", r"1")
    mon.keys("meta_l-q", "meta_l-d")  # close it, open the launcher
    time.sleep(3)
    mon.screenshot("desktop-hyprland-launcher")
    mon.keys("esc")
    time.sleep(1)
    # lock screen (with its sounds): the live user's password is "nullgrid"
    c.con.run("setsid -f nullgrid-lock </dev/null >/dev/null 2>&1", 30)  # detached: not a job of this tty
    if c.wait("pgrep -x hyprlock >/dev/null && echo LOCKED", "LOCKED", 20):
        time.sleep(4)
        mon.screenshot("desktop-lock")
        mon.keys("n", "u", "l", "l", "g", "r", "i", "d", "ret")
        c.wait("pgrep -x hyprlock >/dev/null || echo UNLOCKED", "UNLOCKED", 20)
        c.wait("nullgrid-sfx status", r'.*"recent": \[[^]]*"lock", "unlock".*', 10)
    mon.keys("meta_l-shift-e")     # the "leave the desktop" keybind (plays the logout sound first)
    if not c.wait("pgrep -x Hyprland >/dev/null || echo GONE", "GONE", 20):
        c.info("pgrep -a Hyprland; pgrep -a start-hyprland; tail -5 ~/.local/state/nullgrid/session-hyprland.log")
    c.wait("pgrep -x nullgrid-sfx >/dev/null || echo GONE", "GONE", 10)  # the daemon ends with the session

    # -- Sway, chosen by the lite profile --
    c.con.run("sed -i 's/^profile = \"full\"/profile = \"lite\"/' ~/.config/nullgrid/nullgrid.toml"
              " && nullgrid theme reload >/dev/null", 60)
    restart_tty1(c)
    if c.wait("pgrep -x sway >/dev/null && echo UP", "UP", 90):
        c.wait("pgrep -x swaybg >/dev/null && echo UP", "UP", 60)
        c.con.run(ENV, 30)
        c.check("swaymsg -t get_version | grep -o '\"human_readable\": \"[0-9.]*'", r'"human_readable": "1\.\d+.*')
        c.check("swaymsg -t get_tree | grep -c '\"app_id\": \"nullgrid-welcome\"'", r"1")
        c.wait("nullgrid-shell status 2>/dev/null", r"theme=\S+ wm=SWAY .*", 60)
        # same boot, new session: the login sound, Sway's events
        c.wait("nullgrid-sfx status", r'.*"recent": \[[^]]*"login".*"sources": \["sway", "udev"\].*', 20)
        time.sleep(4)
        mon.screenshot("desktop-sway")
        c.info("free -m | awk '/Mem/ {print \"used MB:\", $3}'")
        c.con.run("swaymsg exit >/dev/null; sleep 2", 30)
    else:
        c.info("tail -20 ~/.local/state/nullgrid/session-sway.log")
    c.con.run("sed -i 's/^profile = \"lite\"/profile = \"full\"/' ~/.config/nullgrid/nullgrid.toml", 30)

    # -- TTY mode: the dashboard on tty1 --
    c.con.run("nullgrid mode tty >/dev/null", 60)
    restart_tty1(c)
    c.wait("pgrep -f nullgrid-dash >/dev/null && echo UP", "UP", 60)
    time.sleep(4)


def main() -> int:
    tmp = tempfile.mkdtemp()
    mon_path = os.path.join(tmp, "monitor.sock")
    rec = Recording(os.path.join(tmp, "audio.wav"))
    con = Console([os.path.join(ROOT, "build", "run-vm.sh"), "--serial", f"--monitor={mon_path}",
                   f"--audio-wav={rec.path}", *sys.argv[1:]])
    mon = Monitor(mon_path)
    c = Checker(con)
    failures = c.failures
    try:
        t0 = time.monotonic()
        con.wait_for(PROMPT, BOOT_TIMEOUT)
        print(f"[ok] reached shell prompt in {time.monotonic() - t0:.0f}s")
        # A plain shell without line editing or echo keeps the output parseable.
        con.send("exec bash --norc --noprofile --noediting")
        time.sleep(2)  # zsh drops typed-ahead input when it execs
        con.run("stty -echo; PS1=''; export TERM=dumb SYSTEMD_COLORS=0", 30)
        for command, expect in CHECKS:
            c.check(command, expect)
        try:
            desktop_tour(c, mon, rec)
            tty1_tour(mon)
        except OSError as exc:
            print(f"[FAIL] screenshots: {exc}")
            failures.append("screenshots")
        if failures:
            print("---- diagnostics ----")
            print("\n".join(con.run(DIAGNOSTICS, 60)))
        con.send("sudo poweroff")
        con.vm.wait(timeout=120)
    except (TimeoutError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"[FAIL] {exc}")
        print("---- last serial output ----")
        print(con.text[-3000:])
        failures.append(str(exc))
    finally:
        if con.vm.poll() is None:
            con.vm.kill()

    print("PASS" if not failures else f"FAIL ({len(failures)} problem(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

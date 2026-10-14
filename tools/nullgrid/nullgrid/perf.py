"""`nullgrid perf`: what the system costs at idle, per NULLGRID component.

Memory is PSS (each process's share of the pages it uses, so shared libraries are counted
once overall), CPU is measured over a window, both summed per component (compositor, shell,
sound...). "Used" memory is MemTotal - MemAvailable: what the kernel can't give back. Run it
as root to see the PSS of every process (otherwise other users' processes fall back to RSS).
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

# component -> process names (comm, as in /proc/PID/comm; 15 characters at most)
COMPONENTS: list[tuple[str, tuple[str, ...]]] = [
    ("compositor", ("Hyprland", "sway", "Xwayland", "hyprland", "start-hyprland")),
    ("shell", ("quickshell", "qs")),
    ("wallpaper", ("swaybg",)),
    ("sound", ("nullgrid-sfx", "pw-play")),
    ("audio", ("pipewire", "wireplumber", "pipewire-pulse")),
    ("lock", ("hyprlock",)),
    ("launcher", ("fuzzel",)),
    ("terminal", ("kitty", "zsh", "bash", "tmux", "starship")),
    ("dashboard", ("nullgrid-dash",)),
    ("login", ("greetd", "tuigreet", "agetty", "login", "nullgrid-login")),
    ("desktop services", ("dbus-daemon", "dbus-broker", "dbus-broker-lau", "xdg-desktop-por", "xdg-document-po",
                          "xdg-permission-", "dconf-service", "gvfsd", "at-spi-bus-laun", "at-spi2-registr")),
    ("network", ("NetworkManager", "wpa_supplicant", "dhcpcd")),
    ("system", ("systemd", "systemd-journal", "systemd-logind", "systemd-udevd", "systemd-userdbd",
                "systemd-timesyn", "systemd-resolve", "systemd-oomd", "systemd-userwor", "(sd-pam)",
                "polkitd", "rtkit-daemon", "udisksd", "upowerd", "plymouthd")),
]
NULLGRID = ("compositor", "shell", "wallpaper", "sound", "lock", "launcher", "dashboard")


def component_of(comm: str, cmdline: str = "") -> str:
    for name, comms in COMPONENTS:
        if comm in comms:
            return name
    # Python tools show up as "python3" unless they rename themselves
    for tool, name in (("nullgrid-sfx", "sound"), ("nullgrid-dash", "dashboard"), ("nullgrid-welcome", "login")):
        if tool in cmdline:
            return name
    return "other"


@dataclass
class Proc:
    pid: int
    comm: str
    cmdline: str
    mem: int            # bytes: PSS if readable, else RSS
    exact: bool         # True when mem is PSS
    ticks: int          # utime + stime
    start: float        # seconds after boot

    @property
    def component(self) -> str:
        return component_of(self.comm, self.cmdline)


def _stat_fields(text: str) -> list[str]:
    # the comm field may contain spaces and parentheses: split after the last ')'
    return text[text.rindex(")") + 2:].split()


def read_procs(proc: Path = Path("/proc")) -> dict[int, Proc]:
    hz = os.sysconf("SC_CLK_TCK")
    page = os.sysconf("SC_PAGE_SIZE")
    procs = {}
    for d in proc.iterdir():
        if not d.name.isdigit():
            continue
        try:
            stat = _stat_fields((d / "stat").read_text())
            comm = (d / "comm").read_text().strip()
            cmdline = (d / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace").strip()
        except (OSError, ValueError):
            continue
        if not cmdline:          # kernel threads
            continue
        ticks = int(stat[11]) + int(stat[12])
        start = int(stat[19]) / hz
        mem, exact = 0, False
        try:
            m = re.search(r"^Pss:\s+(\d+) kB", (d / "smaps_rollup").read_text(), re.M)
            if m:
                mem, exact = int(m.group(1)) * 1024, True
        except OSError:
            pass
        if not exact:
            try:
                mem = int((d / "statm").read_text().split()[1]) * page
            except (OSError, ValueError, IndexError):
                pass
        procs[int(d.name)] = Proc(int(d.name), comm, cmdline, mem, exact, ticks, start)
    return procs


def meminfo(proc: Path = Path("/proc")) -> dict[str, int]:
    info = {}
    for line in (proc / "meminfo").read_text().splitlines():
        key, _, rest = line.partition(":")
        parts = rest.split()
        if parts:
            info[key] = int(parts[0]) * (1024 if parts[1:] == ["kB"] else 1)
    return info


def _cpu_line(proc: Path) -> tuple[int, int]:
    """(busy, total) jiffies of all CPUs, from the first line of /proc/stat."""
    values = [int(x) for x in (proc / "stat").read_text().splitlines()[0].split()[1:]]
    idle = values[3] + (values[4] if len(values) > 4 else 0)   # idle + iowait
    total = sum(values[:8])                                     # guest time is already in user
    return total - idle, total


@dataclass
class Usage:
    mem: int = 0
    cpu: float = 0.0        # percent of one core
    procs: int = 0
    started: float | None = None   # earliest start, seconds after boot


@dataclass
class Report:
    seconds: float
    mem_total: int
    mem_used: int
    cpus: int
    cpu_total: float               # percent of the whole machine
    components: dict[str, Usage] = field(default_factory=dict)
    top: list[tuple[str, int, float, str]] = field(default_factory=list)  # (comm, mem, cpu, component)
    exact: bool = True

    def as_dict(self) -> dict:
        return {
            "seconds": self.seconds, "mem_total": self.mem_total, "mem_used": self.mem_used,
            "cpus": self.cpus, "cpu_total": round(self.cpu_total, 2), "exact": self.exact,
            "components": {k: {"mem": v.mem, "cpu": round(v.cpu, 2), "procs": v.procs,
                               "started": None if v.started is None else round(v.started, 1)}
                           for k, v in self.components.items()},
            "top": [{"name": n, "mem": m, "cpu": round(c, 2), "component": k} for n, m, c, k in self.top],
        }


def _self_and_sudo(proc: Path, pid: int) -> set[int]:
    """This process and the sudo it may run under (left out: the measurement isn't the system)."""
    found = {pid}
    for _ in range(3):
        try:
            ppid = int(_stat_fields((proc / str(pid) / "stat").read_text())[1])
            if (proc / str(ppid) / "comm").read_text().strip() != "sudo":
                break
        except (OSError, ValueError, IndexError):
            break
        found.add(ppid)
        pid = ppid
    return found


def measure(seconds: float = 10.0, top: int = 12, proc: Path = Path("/proc"), sleep=time.sleep,
            me: int | None = None) -> Report:
    skip = _self_and_sudo(proc, os.getpid() if me is None else me)
    before, cpu0 = read_procs(proc), _cpu_line(proc)
    sleep(seconds)
    after, cpu1 = read_procs(proc), _cpu_line(proc)
    hz = os.sysconf("SC_CLK_TCK")
    info = meminfo(proc)
    used = info["MemTotal"] - info.get("MemAvailable", info.get("MemFree", 0))
    busy, total = cpu1[0] - cpu0[0], cpu1[1] - cpu0[1]
    report = Report(seconds, info["MemTotal"], used, os.cpu_count() or 1,
                    busy / total * 100 if total > 0 else 0.0)
    rows = []
    for pid, p in after.items():
        if pid in skip:
            report.mem_used -= p.mem   # what `used` would be without this measurement
            continue
        old = before.get(pid)
        # a process that started during the window (or a reused pid) counts from 0
        cpu = (p.ticks - old.ticks) / hz / seconds * 100 if old and old.start == p.start else 0.0
        u = report.components.setdefault(p.component, Usage())
        u.mem += p.mem
        u.cpu += cpu
        u.procs += 1
        u.started = p.start if u.started is None else min(u.started, p.start)
        report.exact &= p.exact
        rows.append((p.comm, p.mem, cpu, p.component))
    report.top = sorted(rows, key=lambda r: (-r[1], r[0]))[:top]
    return report

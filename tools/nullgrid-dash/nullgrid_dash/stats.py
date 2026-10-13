"""Sample system state with psutil. One Sampler, polled by the dashboard's timer."""
from __future__ import annotations

import os
import platform
import time
from collections import deque
from dataclasses import dataclass, field

import psutil

HISTORY = 240  # samples kept for graphs


@dataclass
class Snapshot:
    cores: list[float]
    cpu: float
    load: tuple[float, float, float]
    mem_used: int
    mem_total: int
    swap_used: int
    swap_total: int
    disk_used: int
    disk_total: int
    down: float                    # bytes/s
    up: float
    battery: tuple[float, bool] | None   # (percent, plugged in)
    temp: float | None             # hottest CPU-ish sensor, °C
    uptime: float
    host: str
    kernel: str


@dataclass
class Sampler:
    down_hist: deque = field(default_factory=lambda: deque(maxlen=HISTORY))
    up_hist: deque = field(default_factory=lambda: deque(maxlen=HISTORY))
    cpu_hist: deque = field(default_factory=lambda: deque(maxlen=HISTORY))   # percent
    mem_hist: deque = field(default_factory=lambda: deque(maxlen=HISTORY))   # percent
    _net: tuple[float, int, int] | None = None

    def __post_init__(self):
        psutil.cpu_percent(percpu=True)  # the first call only primes the counters

    def _rates(self) -> tuple[float, float]:
        now, io = time.monotonic(), psutil.net_io_counters()
        prev, self._net = self._net, (now, io.bytes_recv, io.bytes_sent)
        if prev is None or now <= prev[0]:
            return 0.0, 0.0
        dt = now - prev[0]
        return max(0, io.bytes_recv - prev[1]) / dt, max(0, io.bytes_sent - prev[2]) / dt

    def sample(self) -> Snapshot:
        cores = psutil.cpu_percent(percpu=True)
        mem, swap, disk = psutil.virtual_memory(), psutil.swap_memory(), psutil.disk_usage("/")
        down, up = self._rates()
        self.down_hist.append(down)
        self.up_hist.append(up)
        bat = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None
        cpu = sum(cores) / len(cores) if cores else 0.0
        self.cpu_hist.append(cpu)
        self.mem_hist.append(100 * (mem.total - mem.available) / mem.total if mem.total else 0.0)
        return Snapshot(
            cores=cores,
            cpu=cpu,
            load=os.getloadavg(),
            mem_used=mem.total - mem.available, mem_total=mem.total,
            swap_used=swap.used, swap_total=swap.total,
            disk_used=disk.used, disk_total=disk.total,
            down=down, up=up,
            battery=(bat.percent, bool(bat.power_plugged)) if bat else None,
            temp=_cpu_temp(),
            uptime=time.time() - psutil.boot_time(),
            host=platform.node(),
            kernel=platform.release(),
        )


def _cpu_temp() -> float | None:
    try:
        sensors = psutil.sensors_temperatures()
    except (AttributeError, OSError):
        return None
    for name in ("coretemp", "k10temp", "zenpower", "cpu_thermal", "acpitz"):
        readings = [t.current for t in sensors.get(name, []) if t.current]
        if readings:
            return max(readings)
    return None

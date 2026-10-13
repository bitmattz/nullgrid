"""Event sources: turn compositor, udev and power-supply news into sound event names.

Each parser takes one line of its source's output and returns an event name or None, so the
daemon stays a plain loop and the parsing is unit-tested on recorded lines.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

# --------------------------------------------------------------------------- Hyprland
# Lines from $XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock: "event>>data".
# The start menu and other shell layers make their own sounds; only the keyboard launcher
# (fuzzel, layer namespace "launcher") is heard here.
_HYPR = {
    "workspace": "workspace_switch",
    "openwindow": "window_open",
    "closewindow": "window_close",
    "activewindowv2": "window_focus",
}


def hyprland_event(line: str) -> str | None:
    name, sep, data = line.strip().partition(">>")
    if not sep:
        return None
    if name in ("openlayer", "closelayer"):
        return ("launcher_open" if name == "openlayer" else "launcher_close") if data == "launcher" else None
    if name == "activewindowv2" and not data:  # focus moved to an empty workspace
        return None
    return _HYPR.get(name)


def hyprland_socket() -> Path | None:
    sig, runtime = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"), os.environ.get("XDG_RUNTIME_DIR")
    if not (sig and runtime):
        return None
    p = Path(runtime) / "hypr" / sig / ".socket2.sock"
    return p if p.exists() else None


# --------------------------------------------------------------------------- Sway
# Lines from `swaymsg -t subscribe -m -r '["workspace","window"]'`: one JSON object each.
SWAY_SUBSCRIBE = ["swaymsg", "-t", "subscribe", "-m", "-r", '["workspace","window"]']
_SWAY_WINDOW = {"new": "window_open", "close": "window_close", "focus": "window_focus"}


def sway_event(line: str) -> str | None:
    try:
        ev = json.loads(line)
    except ValueError:
        return None
    if not isinstance(ev, dict):
        return None
    change = ev.get("change")
    if "container" in ev:
        return _SWAY_WINDOW.get(change)
    if "current" in ev and change == "focus":
        return "workspace_switch"
    return None


# --------------------------------------------------------------------------- udev
# Lines from `udevadm monitor --udev -s usb/usb_device -s power_supply`:
#   "UDEV  [1234.567890] add      /devices/pci0000:00/0000:00:14.0/usb1/1-2 (usb)"
UDEV_MONITOR = ["udevadm", "monitor", "--udev", "-s", "usb/usb_device", "-s", "power_supply"]


def udev_event(line: str) -> tuple[str, str] | None:
    """(action, subsystem) of a udev event line, e.g. ("add", "usb")."""
    parts = line.split()
    if len(parts) < 5 or parts[0] != "UDEV" or not parts[-1].startswith("("):
        return None
    return parts[2], parts[-1].strip("()")


def usb_event(action: str) -> str | None:
    return {"add": "usb_connect", "remove": "usb_disconnect"}.get(action)


# --------------------------------------------------------------------------- power supply
BATTERY_LOW = (15, 5)  # percent: one warning when the charge drops through each


@dataclass
class PowerState:
    ac_online: bool | None       # None: no mains adapter (desktop or VM)
    battery: int | None          # percent; None: no battery
    discharging: bool


def read_power(root: Path = Path("/sys/class/power_supply")) -> PowerState:
    ac, levels, discharging = None, [], False
    if root.is_dir():
        for d in sorted(root.iterdir()):
            kind = _read(d / "type")
            if kind == "Mains":
                ac = bool(ac) or _read(d / "online") == "1"
            elif kind == "Battery" and _read(d / "scope") != "Device":  # not a mouse's battery
                cap = _read(d / "capacity")
                if cap and cap.isdigit():
                    levels.append(int(cap))
                discharging = discharging or _read(d / "status") == "Discharging"
    return PowerState(ac, min(levels) if levels else None, discharging)


def power_events(before: PowerState, after: PowerState) -> list[str]:
    events = []
    if before.ac_online is False and after.ac_online:
        events.append("charger_plug")
    if after.discharging and after.battery is not None and before.battery is not None:
        if any(after.battery <= level < before.battery for level in BATTERY_LOW):
            events.append("battery_low")
    return events


def _read(path: Path) -> str:
    try:
        return path.read_text().strip()
    except OSError:
        return ""

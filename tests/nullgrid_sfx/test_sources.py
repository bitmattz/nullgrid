"""Event parsing: compositor, udev and power-supply lines -> sound events."""
import json

import pytest

from nullgrid_sfx import sources


@pytest.mark.parametrize("line, event", [
    ("workspace>>2", "workspace_switch"),
    ("workspacev2>>2,2", None),                 # the same switch again; counted once
    ("openwindow>>55d1a0,1,kitty,~", "window_open"),
    ("closewindow>>55d1a0", "window_close"),
    ("activewindowv2>>55d1a0", "window_focus"),
    ("activewindowv2>>", None),                 # focus went to an empty workspace
    ("openlayer>>launcher", "launcher_open"),   # fuzzel
    ("closelayer>>launcher", "launcher_close"),
    ("openlayer>>nullgrid-menu", None),         # the shell plays its own menu sounds
    ("monitoradded>>HDMI-A-1", None),
    ("garbage", None),
    ("", None),
])
def test_hyprland_events(line, event):
    assert sources.hyprland_event(line) == event


@pytest.mark.parametrize("payload, event", [
    ({"change": "focus", "current": {"num": 2}, "old": {"num": 1}}, "workspace_switch"),
    ({"change": "init", "current": {"num": 3}}, None),
    ({"change": "new", "container": {"app_id": "kitty"}}, "window_open"),
    ({"change": "close", "container": {}}, "window_close"),
    ({"change": "focus", "container": {}}, "window_focus"),
    ({"change": "title", "container": {}}, None),
])
def test_sway_events(payload, event):
    assert sources.sway_event(json.dumps(payload)) == event


def test_sway_ignores_non_json():
    assert sources.sway_event("not json") is None
    assert sources.sway_event("[1, 2]") is None


def test_udev_lines():
    assert sources.udev_event("UDEV  [1234.567890] add      /devices/pci0000:00/0000:00:14.0/usb1/1-2 (usb)") \
        == ("add", "usb")
    assert sources.udev_event("UDEV  [99.1] change   /devices/LNXSYSTM:00/ACPI0003:00/power_supply/AC (power_supply)") \
        == ("change", "power_supply")
    assert sources.udev_event("monitor will print the received events for:") is None
    assert sources.udev_event("UDEV - the event which udev sends out after rule processing") is None
    assert sources.usb_event("add") == "usb_connect"
    assert sources.usb_event("remove") == "usb_disconnect"
    assert sources.usb_event("bind") is None


def supply(root, name, **files):
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    for k, v in files.items():
        (d / k).write_text(f"{v}\n")


def test_power_state(tmp_path):
    assert sources.read_power(tmp_path / "missing") == sources.PowerState(None, None, False)
    supply(tmp_path, "AC", type="Mains", online=0)
    supply(tmp_path, "BAT0", type="Battery", capacity=40, status="Discharging")
    supply(tmp_path, "hidpp_battery_0", type="Battery", capacity=3, status="Discharging", scope="Device")  # a mouse
    assert sources.read_power(tmp_path) == sources.PowerState(False, 40, True)


def test_power_events():
    P = sources.PowerState
    assert sources.power_events(P(False, 50, False), P(True, 50, False)) == ["charger_plug"]
    assert sources.power_events(P(True, 50, False), P(False, 50, True)) == []           # unplugged: silent
    assert sources.power_events(P(None, 16, True), P(None, 15, True)) == ["battery_low"]
    assert sources.power_events(P(None, 15, True), P(None, 14, True)) == []             # warned already
    assert sources.power_events(P(None, 6, True), P(None, 5, True)) == ["battery_low"]  # the last warning
    assert sources.power_events(P(None, 30, True), P(None, 4, True)) == ["battery_low"]  # one, not two
    assert sources.power_events(P(None, 16, False), P(None, 15, False)) == []           # charging
    assert sources.power_events(P(None, None, False), P(None, None, False)) == []       # no battery

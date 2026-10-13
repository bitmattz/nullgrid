"""The daemon: what plays and how loud, rate limits, commands, and the whole process end to end
(fake pw-play, fake Hyprland event socket)."""
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from nullgrid import sound
from nullgrid_sfx import cli, daemon

REPO = Path(__file__).resolve().parents[2]


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def make(paths, fake_player, **kw):
    d = daemon.Daemon(paths, player=[str(fake_player.path)], **kw)
    d.load()
    return d


def wait_played(d):
    for p in d.playing:
        p.proc.wait(5)
    d.reap()


def test_plays_with_volume_from_config(paths, pack, fake_player):
    paths.config_file.write_text('[sound]\npack = "test-pack"\nvolume = 0.5\n'
                                 '[sound.events]\nnotification = { volume = 0.5 }\n')
    d = make(paths, fake_player)
    assert d.trigger("notification")
    wait_played(d)
    assert fake_player.played() == ["notification"]
    assert "--volume=0.250" in fake_player.lines()[0]


def test_switches(paths, pack, fake_player):
    d = make(paths, fake_player)
    assert not d.trigger("window_focus")     # off by default
    assert not d.trigger("no_such_event")
    paths.config_file.write_text('[sound]\npack = "test-pack"\nenabled = false\n')
    d.load()
    assert not d.trigger("notification")     # muted
    assert d.status()["enabled"] is False


def test_rate_limits(paths, pack, fake_player):
    clock = Clock()
    d = make(paths, fake_player, clock=clock)
    assert d.trigger("window_open")
    assert not d.trigger("window_open")      # same event, same instant: a burst
    assert d.trigger("window_close")         # another event is fine
    clock.t += daemon.MIN_GAP + 0.001
    assert d.trigger("window_open")
    for i in range(daemon.MAX_PLAYING):
        clock.t += 1
        d.trigger("button_click")
    assert len(d.playing) == daemon.MAX_PLAYING
    wait_played(d)
    assert d.playing == []


def test_missing_pack_is_silent(paths, fake_player):
    paths.config_dir.mkdir(parents=True)
    paths.config_file.write_text('[sound]\npack = "nope"\n')
    d = make(paths, fake_player)
    assert d.pack is None and not d.trigger("notification")
    assert d.status()["pack"] is None


def test_generated_config_wins(paths, pack, fake_player):
    gen = paths.config_dir / "generated" / "sfx.json"
    gen.parent.mkdir(parents=True)
    cfg = json.loads(json.dumps(daemon.cfgmod.load(paths).config["sound"]))
    cfg["events"]["notification"]["enabled"] = False
    gen.write_text(json.dumps(cfg))
    d = make(paths, fake_player)
    assert not d.trigger("notification")
    assert d.trigger("login")


def test_commands(paths, pack, fake_player):
    d = make(paths, fake_player)
    assert d.command("play login") is None
    status = json.loads(d.command("status"))
    assert status["pack"] == "test-pack" and status["played"] == 1 and status["recent"] == ["login"]
    assert d.command("reload") == "ok"
    assert d.command("bogus") is None
    assert d.command("quit") == "bye" and not d.running


def test_power_events_play(paths, pack, fake_player, tmp_path):
    sysfs = tmp_path / "power"
    (sysfs / "AC").mkdir(parents=True)
    (sysfs / "AC" / "type").write_text("Mains\n")
    (sysfs / "AC" / "online").write_text("0\n")
    d = make(paths, fake_player, sysfs=sysfs)
    (sysfs / "AC" / "online").write_text("1\n")
    d.on_udev("UDEV  [5.0] change   /devices/LNXSYSTM:00/ACPI0003:00/power_supply/AC (power_supply)")
    d.on_udev("UDEV  [6.0] add      /devices/pci0000:00/0000:00:14.0/usb1/1-2 (usb)")
    wait_played(d)
    assert sorted(fake_player.played()) == ["charger_plug", "usb_connect"]  # (logged in either order)


def test_first_sound(paths):
    assert daemon.first_sound(paths) == "boot"
    assert daemon.first_sound(paths) == "login"  # same boot, next session


# --------------------------------------------------------------------------- end to end
@pytest.fixture
def running(paths, pack, fake_player, tmp_path):
    """The daemon as a real process, with a fake Hyprland event socket to talk to."""
    sig = "testsig"
    hypr_dir = Path(os.environ["XDG_RUNTIME_DIR"]) / "hypr" / sig
    hypr_dir.mkdir(parents=True)
    hypr = socket.socket(socket.AF_UNIX)
    hypr.bind(str(hypr_dir / ".socket2.sock"))
    hypr.listen(1)
    env = dict(os.environ, HYPRLAND_INSTANCE_SIGNATURE=sig, PYTHONDONTWRITEBYTECODE="1",
               PATH=f"{fake_player.dir}:{os.environ['PATH']}",
               PYTHONPATH=f"{REPO / 'tools/nullgrid'}:{REPO / 'tools/nullgrid-sfx'}")
    proc = subprocess.Popen([sys.executable, "-m", "nullgrid_sfx", "daemon", "--no-startup-sound"], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    hypr.settimeout(10)
    conn, _ = hypr.accept()
    for _ in range(100):
        if sound.request("status", reply=True):
            break
        time.sleep(0.05)
    yield proc, conn
    conn.close()
    hypr.close()
    if proc.poll() is None:
        proc.kill()
    proc.wait(5)


def until(check, seconds=5.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if check():
            return True
        time.sleep(0.05)
    return False


def test_daemon_process(running, paths, fake_player, monkeypatch):
    proc, hypr = running
    status = json.loads(sound.request("status", reply=True))
    assert status["pack"] == "test-pack" and "hyprland" in status["sources"]

    # the client command, as key bindings and scripts use it
    assert cli.main(["play", "notification"]) == 0
    assert until(lambda: fake_player.played() == ["notification"])
    # playwait answers once the sound is over (nullgrid-power waits for it before logging out)
    assert sound.request("playwait logout", timeout=5, reply=True) == "done"
    assert sound.request("playwait window_focus", timeout=5, reply=True) == "skipped"  # off by default

    # compositor events
    hypr.sendall(b"openwindow>>abc,1,kitty,kitty\nworkspace>>2\nactivewindowv2>>abc\n")
    # (two players start at once, so they may log in either order)
    assert until(lambda: sorted(fake_player.played()[-2:]) == ["window_open", "workspace_switch"])

    # a config change + SIGHUP (what `nullgrid sound mute` does through the manifest hook)
    paths.config_file.write_text('[sound]\npack = "test-pack"\nenabled = false\n')
    proc.send_signal(signal.SIGHUP)
    assert until(lambda: json.loads(sound.request("status", reply=True))["enabled"] is False)
    count = len(fake_player.played())
    cli.main(["play", "notification"])
    time.sleep(0.3)
    assert len(fake_player.played()) == count

    # the compositor going away ends the session, and the daemon with it
    hypr.close()
    assert proc.wait(5) == 0
    assert not sound.socket_path().exists()


def test_new_daemon_replaces_old(running, paths):
    proc, _ = running
    srv = daemon.take_socket(sound.socket_path())  # what a second session's daemon does
    try:
        assert proc.wait(5) == 0
    finally:
        srv.close()


def test_play_without_daemon(paths, pack, fake_player, monkeypatch):
    monkeypatch.setenv("PATH", f"{fake_player.dir}:{os.environ['PATH']}")
    assert cli.main(["play", "unlock", "--wait"]) == 0
    assert fake_player.played() == ["unlock"]
    assert cli.main(["play", "window_focus"]) == 0     # off: nothing played
    assert fake_player.played() == ["unlock"]
    assert cli.main(["play", "nonsense"]) == 2
    assert cli.main(["status"]) == 1

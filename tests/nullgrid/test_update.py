"""nullgrid update: pacman -Syu, then refresh the configs; notes about what needs a restart."""
import subprocess
from pathlib import Path

from nullgrid import cli


class FakeRun:
    def __init__(self, versions_after, rc=0):
        self.calls = []
        self.versions = [{"hyprland": "0.56.0-1", "linux": "7.2.9-1", "quickshell": "0.3.2-1"}, versions_after]
        self.rc = rc

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        if cmd[:2] == ["pacman", "-Q"]:
            v = self.versions[0] if len([c for c in self.calls if c[:2] == ["pacman", "-Q"]]) == 1 else self.versions[1]
            return subprocess.CompletedProcess(cmd, 0, "".join(f"{k} {v}\n" for k, v in v.items()), "")
        return subprocess.CompletedProcess(cmd, self.rc if cmd[0] == "sudo" else 0, "", "")


def test_update_refreshes_and_reports(isolated, monkeypatch, capsys):
    fake = FakeRun({"hyprland": "0.57.0-1", "linux": "7.2.9-1", "quickshell": "0.3.3-1"})
    monkeypatch.setattr(cli.subprocess, "run", fake)
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
    monkeypatch.setattr(cli.shutil, "which", lambda n: "/usr/bin/" + n)
    cli.main(["update", "--yes"])
    out = capsys.readouterr().out
    assert ["sudo", "pacman", "-Syu", "--noconfirm"] in fake.calls
    assert ["nullgrid-shell", "restart"] in fake.calls                  # quickshell changed
    assert "Hyprland was updated" in out and "the kernel" not in out
    assert (isolated / ".config" / "nullgrid" / "nullgrid.toml").is_file()   # configs refreshed
    assert (isolated / ".local/state/nullgrid/initialized").exists()


def test_update_stops_when_pacman_fails(isolated, monkeypatch, capsys):
    fake = FakeRun({}, rc=1)
    monkeypatch.setattr(cli.subprocess, "run", fake)
    assert cli.main(["update"]) == 1
    assert "system update failed" in capsys.readouterr().err
    assert not (isolated / ".local/state/nullgrid/initialized").exists()


def test_update_no_system(isolated, monkeypatch):
    fake = FakeRun({"hyprland": "0.56.0-1", "linux": "7.2.9-1", "quickshell": "0.3.2-1"})
    monkeypatch.setattr(cli.subprocess, "run", fake)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    cli.main(["update", "--no-system"])
    assert not any(c[0] == "sudo" for c in fake.calls)
    assert ["nullgrid-shell", "restart"] not in fake.calls


def test_refresh_hook_and_zsh():
    repo = Path(__file__).resolve().parents[2]
    hook = (repo / "config/pacman/nullgrid-refresh.hook").read_text()
    assert "Target = nullgrid-*" in hook and "/var/lib/nullgrid/updated" in hook
    zsh = (repo / "config/zsh/nullgrid.zsh").read_text()
    assert "/var/lib/nullgrid/updated -nt $XDG_STATE_HOME/nullgrid/initialized" in zsh

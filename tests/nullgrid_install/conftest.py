"""Fixtures for the installer tests: an empty HOME, a fake live image built from iso/airootfs,
and a fake System that records commands instead of touching disks (insttest.FakeSystem)."""
import shutil

import pytest

from insttest import KVER, LOCALE_GEN, REPO, FakeSystem


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    for var, value in {"HOME": home, "XDG_CONFIG_HOME": home / ".config", "XDG_STATE_HOME": home / ".local/state",
                       "XDG_DATA_HOME": home / ".local/share"}.items():
        monkeypatch.setenv(var, str(value))
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("NULLGRID_DATA_DIR", raising=False)
    return home


@pytest.fixture
def fake():
    return FakeSystem()


@pytest.fixture
def live(tmp_path):
    """A live image: the ISO's airootfs plus what the packages would have put there."""
    src = tmp_path / "src"
    shutil.copytree(REPO / "iso" / "airootfs", src, symlinks=True)
    (src / "usr/lib/modules" / KVER).mkdir(parents=True)
    (src / "usr/lib/modules" / KVER / "vmlinuz").write_text("kernel")
    (src / "etc/locale.gen").write_text(LOCALE_GEN)
    (src / "etc/passwd").write_text("root:x:0:0:root:/root:/usr/bin/zsh\nnullgrid:x:1000:1000::/home/nullgrid:/usr/bin/zsh\n")
    (src / "usr/local/share/applications").mkdir(parents=True, exist_ok=True)
    (src / "usr/local/share/applications/nullgrid-install.desktop").write_text("[Desktop Entry]\n")
    target = tmp_path / "mnt"
    target.mkdir()
    return src, target

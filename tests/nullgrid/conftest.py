"""Shared fixtures: every test gets an empty HOME and the repo's themes/templates."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "nullgrid"))

from nullgrid import cli, paths as pathmod, render  # noqa: E402


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(home / ".local/state"))
    for var in ("NULLGRID_DATA_DIR", "HYPRLAND_INSTANCE_SIGNATURE", "WAYLAND_DISPLAY", "SWAYSOCK", "VISUAL", "EDITOR",
                "XDG_CACHE_HOME"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("TERM", "dumb")
    # Never signal real apps (e.g. the developer's own kitty) from a test.
    monkeypatch.setattr(render, "_processes", lambda name: [])
    return home


@pytest.fixture
def paths():
    return pathmod.resolve()


@pytest.fixture
def run(capsys):
    """run("theme", "set", "x") -> (exit code, stdout, stderr)"""
    def _run(*argv):
        code = cli.main(list(argv))
        out = capsys.readouterr()
        return code, out.out, out.err
    return _run

"""Fixtures for the sound daemon tests: an empty HOME and runtime dir, a fake pw-play that
records what it was asked to play, and a small generated-looking sound pack."""
import os
import sys
import wave
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
for p in (REPO / "tools" / "nullgrid", REPO / "tools" / "nullgrid-sfx"):
    sys.path.insert(0, str(p))

from nullgrid import config, paths as pathmod  # noqa: E402

EVENTS = list(config.SOUND_EVENTS)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    runtime = tmp_path / "run"
    runtime.mkdir(mode=0o700)
    for var, value in {"HOME": home, "XDG_CONFIG_HOME": home / ".config", "XDG_STATE_HOME": home / ".local/state",
                       "XDG_DATA_HOME": home / ".local/share", "XDG_RUNTIME_DIR": runtime}.items():
        monkeypatch.setenv(var, str(value))
    for var in ("NULLGRID_DATA_DIR", "HYPRLAND_INSTANCE_SIGNATURE", "WAYLAND_DISPLAY", "SWAYSOCK", "XDG_CACHE_HOME"):
        monkeypatch.delenv(var, raising=False)
    return home


@pytest.fixture
def paths():
    return pathmod.resolve()


def silent_wav(path: Path, ms: int = 60) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(48000)
        w.writeframes(b"\0\0" * (48 * ms))


@pytest.fixture
def pack(paths):
    """A user pack 'test-pack' (the default config's pack is replaced by it) with every event."""
    d = paths.sounds[0] / "test-pack"
    d.mkdir(parents=True)
    lines = ['[meta]\nname = "test-pack"\ndescription = "for tests"\n[events]']
    for e in EVENTS:
        silent_wav(d / f"{e}.wav")
        lines.append(f'{e} = "{e}.wav"')
    (d / "pack.toml").write_text("\n".join(lines) + "\n")
    paths.config_dir.mkdir(parents=True, exist_ok=True)
    paths.config_file.write_text('[sound]\npack = "test-pack"\n')
    return d


@pytest.fixture
def fake_player(tmp_path):
    """A pw-play stand-in that logs its arguments (one line per call) and exits."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "played.log"
    exe = bindir / "pw-play"
    exe.write_text(f'#!/bin/sh\necho "$@" >> {log}\n')
    exe.chmod(0o755)

    class Player:
        path = exe
        dir = bindir

        @staticmethod
        def played() -> list[str]:
            """Event names played so far, in order."""
            if not log.exists():
                return []
            return [Path(line.split()[-1]).stem for line in log.read_text().splitlines() if line.strip()]

        @staticmethod
        def lines() -> list[str]:
            return log.read_text().splitlines() if log.exists() else []

    return Player

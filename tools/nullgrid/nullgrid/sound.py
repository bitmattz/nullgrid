"""Sound packs and the rules for when (and how loud) an event sounds.

A pack is a directory sounds/<name>/ with a pack.toml and the sound files it names:

    [meta]
    name = "neural-link"
    description = "..."

    [events]                      # event = file, or { file = ..., volume = 0-1 }
    boot = "boot.wav"
    notification = { file = "notify.wav", volume = 0.8 }

Packs are looked up in ~/.local/share/nullgrid/sounds/ first, then the system dir
(/usr/share/nullgrid/sounds, or out/sounds in a git checkout after `make sounds`). An event a
pack leaves out is silent. The daemon (nullgrid-sfx) and `nullgrid sound` share this module.
"""
from __future__ import annotations

import difflib
import os
import shutil
import socket
import subprocess
from dataclasses import dataclass
from datetime import datetime
from datetime import time as dtime
from pathlib import Path

from .config import SOUND_EVENTS, ConfigError, read_toml
from .paths import Paths
from .schema import Field, Float, Invalid, Mapping, Str, Table

AUDIO_TYPES = (".wav", ".ogg", ".oga", ".flac")


class Entry(Field):
    """An event's sound: "file.wav" or { file = "file.wav", volume = 0.8 }."""

    def check(self, value):
        if isinstance(value, str):
            value = {"file": value}
        if not isinstance(value, dict):
            raise Invalid(f"expected a file name or {{ file = ..., volume = ... }}, got {value!r}")
        errors: list[str] = []
        out = ENTRY.validate(value, "", errors)
        if errors:
            raise Invalid("; ".join(errors))
        return out


ENTRY = Table({"file": Str(), "volume": Float(0, 1, default=1.0)})

PACK = Table({
    "meta": Table({
        "name": Str(r"[a-z0-9][a-z0-9-]*", hint="a lowercase name like 'neural-link'"),
        "description": Str(default=""),
        "author": Str(default=""),
        "license": Str(default=""),
    }),
    "events": Mapping(default={}),
})


@dataclass
class Sound:
    path: Path
    volume: float  # the pack's own gain for this event


@dataclass
class Pack:
    name: str
    description: str
    path: Path                 # the pack directory
    sounds: dict[str, Sound]   # event -> sound


# --------------------------------------------------------------------------- packs
def find_pack(paths: Paths, name: str) -> Path | None:
    for d in paths.sounds:
        if (d / name / "pack.toml").is_file():
            return d / name
    return None


def list_packs(paths: Paths) -> dict[str, Path]:
    """Every pack name -> directory, user packs shadowing system ones."""
    found: dict[str, Path] = {}
    for d in reversed(paths.sounds):
        if d.is_dir():
            for f in sorted(d.glob("*/pack.toml")):
                found[f.parent.name] = f.parent
    return dict(sorted(found.items()))


def load_pack(directory: Path) -> Pack:
    """Validate pack.toml and check that every file it names exists. Raises ConfigError."""
    source = directory / "pack.toml"
    errors: list[str] = []
    raw = PACK.validate(read_toml(source), "", errors)
    sounds: dict[str, Sound] = {}
    if not errors:
        if raw["meta"]["name"] != directory.name:
            errors.append(f"meta.name: is {raw['meta']['name']!r} but the directory is named {directory.name!r}")
        for event, value in raw["events"].items():
            where = f"events.{event}"
            if event not in SOUND_EVENTS:
                hint = difflib.get_close_matches(event, SOUND_EVENTS, n=1)
                errors.append(f"{where}: unknown event" + (f" (did you mean {hint[0]!r}?)" if hint else ""))
                continue
            try:
                entry = Entry().check(value)
            except Invalid as exc:
                errors.append(f"{where}: {exc}")
                continue
            f = (directory / entry["file"]).resolve()
            if not f.is_relative_to(directory.resolve()):
                errors.append(f"{where}: {entry['file']!r} is outside the pack directory")
            elif f.suffix.lower() not in AUDIO_TYPES:
                errors.append(f"{where}: {entry['file']!r} is not a {'/'.join(AUDIO_TYPES)} file")
            elif not f.is_file():
                errors.append(f"{where}: {entry['file']!r} does not exist")
            else:
                sounds[event] = Sound(f, entry["volume"])
    if errors:
        raise ConfigError(source, errors)
    return Pack(raw["meta"]["name"], raw["meta"]["description"], directory, sounds)


# --------------------------------------------------------------------------- rules
def _hm(text: str) -> dtime:
    h, m = text.split(":")
    return dtime(int(h), int(m))


def in_quiet_hours(quiet: dict, now: datetime) -> bool:
    if not quiet["enabled"]:
        return False
    start, end, t = _hm(quiet["start"]), _hm(quiet["end"]), now.time()
    if start <= end:
        return start <= t < end
    return t >= start or t < end  # e.g. 22:00-07:00, across midnight


def volume(sound_cfg: dict, event: str, pack_gain: float = 1.0, now: datetime | None = None,
           test: bool = False) -> float:
    """How loud `event` plays (0-1), or 0 when it shouldn't play at all. `sound_cfg` is the
    validated [sound] table. test=True ignores the on/off switches (for `nullgrid sound test`)."""
    ev = sound_cfg["events"].get(event)
    if ev is None:
        return 0.0
    if not test and not (sound_cfg["enabled"] and ev["enabled"]):
        return 0.0
    v = sound_cfg["volume"] * ev["volume"] * pack_gain
    if in_quiet_hours(sound_cfg["quiet_hours"], now or datetime.now()):
        v *= sound_cfg["quiet_hours"]["volume"]
    return round(min(1.0, v), 3)


# --------------------------------------------------------------------------- playback
def player() -> list[str] | None:
    """The command that plays a file, first one found: pw-play (PipeWire), paplay, aplay."""
    if shutil.which("pw-play"):
        return ["pw-play", "--media-role", "Notification", "-P", "{ application.name = nullgrid-sfx }"]
    if shutil.which("paplay"):
        return ["paplay"]
    if shutil.which("aplay"):
        return ["aplay", "-q"]
    return None


def play_command(path: Path, vol: float, base: list[str] | None = None) -> list[str] | None:
    base = base if base is not None else player()
    if base is None:
        return None
    name = Path(base[0]).name
    if name == "pw-play":
        return [*base, f"--volume={vol:.3f}", str(path)]
    if name == "paplay":
        return [*base, f"--volume={round(vol * 65536)}", str(path)]
    return [*base, str(path)]  # aplay: no volume control


def play(path: Path, vol: float, wait: bool = False) -> subprocess.Popen | None:
    """Start playing (never blocks unless wait=True). None when there's no player or vol is 0."""
    cmd = play_command(path, vol)
    if cmd is None or vol <= 0:
        return None
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)
    if wait:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    return proc


# --------------------------------------------------------------------------- daemon socket
def socket_path() -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime and os.path.isdir(runtime):
        return Path(runtime) / "nullgrid-sfx.sock"
    return Path(f"/tmp/nullgrid-sfx-{os.getuid()}.sock")


def request(line: str, timeout: float = 0.5, reply: bool = False) -> str | None:
    """Send one command line to the running daemon. Returns its reply line (reply=True), ""
    when sent, or None when no daemon is listening."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(str(socket_path()))
        s.sendall(line.encode() + b"\n")
        if not reply:
            return ""
        s.shutdown(socket.SHUT_WR)
        data = b""
        while chunk := s.recv(4096):
            data += chunk
        return data.decode(errors="replace").strip()
    except OSError:
        return None
    finally:
        s.close()

"""Sound packs: the generator's output, pack validation, the volume rules, `nullgrid sound`,
and the sound bits of the generated configs."""
import importlib.util
import json
import sys
import wave
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from nullgrid import config, render, sound

from ngtest import REPO, write_config

EVENTS = list(config.SOUND_EVENTS)


def _generator():
    spec = importlib.util.spec_from_file_location("ng_sound_generate", REPO / "assets/sounds/generate.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclasses look their module up there
    spec.loader.exec_module(mod)
    return mod


gen = _generator()


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    out = tmp_path_factory.mktemp("sounds")
    gen.main(["--out", str(out)])
    return out


def read_wav(path: Path):
    with wave.open(str(path)) as w:
        params = (w.getnchannels(), w.getsampwidth(), w.getframerate())
        x = np.frombuffer(w.readframes(w.getnframes()), "<i2") / 32768
    return params, x


# --------------------------------------------------------------------------- generator
@pytest.mark.parametrize("name", ["neural-link", "minimal-ops"])
def test_packs_cover_every_event(generated, name):
    pack = sound.load_pack(generated / name)
    assert pack.name == name and pack.description
    assert set(pack.sounds) == set(EVENTS)


@pytest.mark.parametrize("name", ["neural-link", "minimal-ops"])
def test_sounds_are_short_clean_and_balanced(generated, name):
    p = gen.PACKS[name]
    for event in EVENTS:
        params, x = read_wav(generated / name / f"{event}.wav")
        assert params == (1, 2, 48000), event
        ms = len(x) / 48
        assert gen.MIN_MS <= ms <= gen.MAX_MS, f"{event}: {ms:.0f} ms"
        peak = 20 * np.log10(np.abs(x).max())
        assert -40 < peak <= gen.PEAK_DB + 0.1, f"{event}: peak {peak:.1f} dBFS"
        # matched loudness, unless the peak limit held it back
        assert gen.loudness(x) <= p.level_of(event) + 0.2, event
        if peak < gen.PEAK_DB - 0.2:
            assert abs(gen.loudness(x) - p.level_of(event)) < 0.5, event
        # no click at either end, no DC offset
        assert abs(x[0]) < 0.01 and abs(x[-1]) < 0.01, event
        assert abs(x.mean()) < 0.01, event


def test_generator_is_deterministic():
    p = gen.PACKS["neural-link"]
    assert np.array_equal(gen.render(p, "launcher_open"), gen.render(p, "launcher_open"))
    assert not np.array_equal(gen.render(p, "launcher_open"), gen.render(p, "launcher_close"))


def test_minimal_is_quieter_than_neural():
    assert gen.PACKS["minimal-ops"].level < gen.PACKS["neural-link"].level
    p = gen.PACKS["neural-link"]
    assert p.level_of("menu_hover") < p.level_of("login") < p.level_of("notification_critical")


# --------------------------------------------------------------------------- packs
def make_pack(paths, name, events: str, files=("a.wav",)):
    d = paths.sounds[0] / name
    d.mkdir(parents=True, exist_ok=True)
    for f in files:
        (d / f).write_bytes(b"RIFF")
    (d / "pack.toml").write_text(f'[meta]\nname = "{name}"\n[events]\n{events}\n')
    return d


def test_pack_entries(paths):
    d = make_pack(paths, "p", 'login = "a.wav"\nlogout = { file = "a.wav", volume = 0.5 }')
    pack = sound.load_pack(d)
    assert pack.sounds["login"].volume == 1.0 and pack.sounds["logout"].volume == 0.5
    assert pack.sounds["login"].path == (d / "a.wav").resolve()


@pytest.mark.parametrize("events, problem", [
    ('logn = "a.wav"', "events.logn: unknown event (did you mean 'login'?)"),
    ('login = "missing.wav"', "events.login: 'missing.wav' does not exist"),
    ('login = "../../x.wav"', "events.login: '../../x.wav' is outside the pack directory"),
    ('login = "a.mp3"', "is not a .wav/.ogg/.oga/.flac file"),
    ('login = { file = "a.wav", volume = 3 }', "events.login: volume: must be between 0 and 1"),
    ('login = 5', "events.login: expected a file name"),
])
def test_pack_problems(paths, events, problem):
    d = make_pack(paths, "p", events, files=("a.wav", "a.mp3"))
    with pytest.raises(config.ConfigError) as exc:
        sound.load_pack(d)
    assert any(problem in p for p in exc.value.problems), exc.value.problems


def test_pack_name_must_match_dir(paths):
    d = make_pack(paths, "p", "")
    (d / "pack.toml").write_text('[meta]\nname = "other"\n')
    with pytest.raises(config.ConfigError, match="directory is named 'p'"):
        sound.load_pack(d)


def test_user_packs_shadow_system(paths, tmp_path):
    system = tmp_path / "system"
    for name in ("neural-link", "minimal-ops"):
        (system / name).mkdir(parents=True)
        (system / name / "pack.toml").write_text(f'[meta]\nname = "{name}"\n')
    paths = _with_sounds(paths, system)
    make_pack(paths, "neural-link", "")
    assert sound.list_packs(paths) == {"minimal-ops": system / "minimal-ops",
                                      "neural-link": paths.sounds[0] / "neural-link"}
    assert sound.find_pack(paths, "minimal-ops") == system / "minimal-ops"
    assert sound.find_pack(paths, "nope") is None


# --------------------------------------------------------------------------- rules
def cfg(text=""):
    return config.validate_config(config.tomllib.loads(text), "test")["sound"]


NOON = datetime(2026, 10, 13, 12, 0)


def test_volume():
    c = cfg('[sound]\nvolume = 0.5\n[sound.events]\nnotification = { volume = 0.4 }\n')
    assert sound.volume(c, "notification", 1.0, NOON) == 0.2
    assert sound.volume(c, "notification", 0.5, NOON) == 0.1   # the pack's own gain
    assert sound.volume(c, "login", 1.0, NOON) == 0.5
    assert sound.volume(c, "window_focus", 1.0, NOON) == 0      # off by default
    assert sound.volume(c, "window_focus", 1.0, NOON, test=True) == 0.5
    assert sound.volume(c, "not_an_event", 1.0, NOON) == 0
    muted = cfg('[sound]\nenabled = false\n')
    assert sound.volume(muted, "login", 1.0, NOON) == 0
    assert sound.volume(muted, "login", 1.0, NOON, test=True) == 0.6


@pytest.mark.parametrize("start, end, hour, quiet", [
    ("22:00", "07:00", 23, True), ("22:00", "07:00", 3, True), ("22:00", "07:00", 7, False),
    ("22:00", "07:00", 12, False), ("13:00", "14:00", 13, True), ("13:00", "14:00", 14, False),
])
def test_quiet_hours(start, end, hour, quiet):
    c = cfg(f'[sound.quiet_hours]\nenabled = true\nstart = "{start}"\nend = "{end}"\nvolume = 0.5\n')
    assert sound.in_quiet_hours(c["quiet_hours"], datetime(2026, 1, 1, hour, 0)) is quiet
    assert sound.volume(c, "login", 1.0, datetime(2026, 1, 1, hour, 0)) == (0.3 if quiet else 0.6)


def test_play_commands():
    f = Path("/s/x.wav")
    assert sound.play_command(f, 0.25, ["pw-play", "--media-role", "Notification"]) == \
        ["pw-play", "--media-role", "Notification", "--volume=0.250", "/s/x.wav"]
    assert sound.play_command(f, 0.5, ["paplay"]) == ["paplay", "--volume=32768", "/s/x.wav"]
    assert sound.play_command(f, 0.5, ["aplay", "-q"]) == ["aplay", "-q", "/s/x.wav"]


def test_request_without_daemon():
    assert sound.request("status", reply=True) is None


# --------------------------------------------------------------------------- CLI
@pytest.fixture
def played(monkeypatch):
    calls = []
    monkeypatch.setattr(sound, "player", lambda: ["pw-play"])
    monkeypatch.setattr(sound, "play", lambda path, vol, wait=False: calls.append((path.stem, vol, wait)))
    return calls


def _with_sounds(paths, system):
    """paths with `system` as the system sound dir (the repo's out/sounds may not exist)."""
    return replace(paths, sounds=[paths.sounds[0], system])


@pytest.fixture
def cli_paths(paths, generated, monkeypatch):
    p = _with_sounds(paths, generated)
    monkeypatch.setattr("nullgrid.paths.resolve", lambda: p)
    return p


def test_sound_list(run, cli_paths):
    code, out, _ = run("sound", "list")
    assert code == 0
    assert "* neural-link  Glitchy digital blips" in out and "  minimal-ops" in out and "(27 sounds)" in out


def test_sound_set(run, cli_paths):
    code, out, _ = run("sound", "set", "minimal-ops")
    assert code == 0 and "sound pack: minimal-ops (27 sounds)" in out
    assert 'pack = "minimal-ops"' in cli_paths.config_file.read_text()
    sfx = json.loads((cli_paths.config_dir / "generated" / "sfx.json").read_text())
    assert sfx["pack"] == "minimal-ops" and sfx["events"]["window_focus"]["enabled"] is False

    code, _, err = run("sound", "set", "minimal-op")
    assert code == 1 and "did you mean 'minimal-ops'" in err


def test_sound_test(run, cli_paths, played):
    code, out, _ = run("sound", "test", "notification")
    assert code == 0 and played == [("notification", 0.6, True)]
    played.clear()
    code, out, _ = run("sound", "test", "all")
    assert code == 0 and len(played) == 27 and "window_focus" in out and "(off in your config)" in out
    code, _, err = run("sound", "test", "notifcation")
    assert code == 1 and "did you mean 'notification'" in err


def test_sound_mute_and_volume(run, cli_paths, played, capsys):
    assert run("sound", "mute")[1].strip() == "sound: muted"
    assert run("sound", "mute")[1].strip() == "sound: on"
    assert run("sound", "mute", "on")[1].strip() == "sound: muted"
    assert run("sound", "mute", "on")[1].strip() == "sound: muted"
    code, out, _ = run("sound", "test", "login")
    assert "sound is muted" in out and played  # test plays anyway
    assert run("sound", "volume", "0.3")[0] == 0
    assert run("sound", "volume")[1].strip() == "0.3"
    with pytest.raises(SystemExit) as exc:
        run("sound", "volume", "2")
    assert exc.value.code == 2 and "from 0 to 1" in capsys.readouterr().err
    text = cli_paths.config_file.read_text()
    assert "enabled = false" in text and "volume = 0.3" in text


def test_doctor_reports_missing_pack(run, cli_paths):
    write_config(cli_paths, '[sound]\npack = "gone"\n')
    code, out, _ = run("doctor")
    assert "no sound pack named 'gone' (minimal-ops, neural-link)" in out


# --------------------------------------------------------------------------- generated configs
def rendered(paths, text):
    write_config(paths, text)
    settings = config.load(paths)
    return render.render_all(settings, paths, render.load_manifest(paths))


def test_shell_hooks_follow_the_config(paths):
    out = rendered(paths, "")
    assert 'NULLGRID_SFX_SHELL=""' in out["shell-env"]
    assert "command_on_bell" not in out["kitty"]
    out = rendered(paths, "[sound.events]\ncommand_failed = { enabled = true }\nterminal_bell = { enabled = true }\n")
    assert 'NULLGRID_SFX_SHELL="command_failed"' in out["shell-env"]
    assert "command_on_bell nullgrid-sfx play terminal_bell" in out["kitty"]
    out = rendered(paths, "[sound]\nenabled = false\n[sound.events]\ncommand_failed = { enabled = true }\n")
    assert 'NULLGRID_SFX_SHELL=""' in out["shell-env"]


def test_hardware_keys_work_when_locked(paths):
    out = rendered(paths, "")
    assert ('hl.bind("XF86AudioRaiseVolume", hl.dsp.exec_cmd("nullgrid-media volume up"), '
            "{ locked = true, repeating = true })") in out["hyprland-keys"]
    assert 'bindsym --locked XF86MonBrightnessDown exec "nullgrid-media brightness down"' in out["sway-keys"]
    assert 'hl.dsp.exec_cmd("nullgrid-power logout"))' in out["hyprland-keys"]
    assert 'bindsym Mod4+Control+l exec "nullgrid-lock"' in out["sway-keys"]

import os
from pathlib import Path

import pytest

from conftest import REPO, write_config
from nullgrid import config, render

SNAPSHOTS = Path(__file__).parent / "snapshots"
UPDATE = os.environ.get("NULLGRID_UPDATE_SNAPSHOTS") == "1"


def rendered(paths, config_text=""):
    if config_text:
        write_config(paths, config_text)
    settings = config.load(paths)
    targets = render.load_manifest(paths)
    return targets, render.render_all(settings, paths, targets)


@pytest.mark.parametrize("preset", ["crimson-hud", "ice-protocol", "toxic-grid"])
def test_snapshots(paths, preset):
    """Every template, rendered for every preset. Update: NULLGRID_UPDATE_SNAPSHOTS=1 pytest"""
    targets, out = rendered(paths, f'[theme]\npreset = "{preset}"\n')
    assert {t.name for t in targets} == {"kitty", "hyprland", "hyprlock", "quickshell", "mako", "fuzzel",
                                         "btop", "nvim", "gtk", "qt", "tty"}
    snap_dir = SNAPSHOTS / preset
    for t in targets:
        snap = snap_dir / f"{t.name}{''.join(Path(t.template).suffixes[:-1]) or '.txt'}"
        if UPDATE:
            snap_dir.mkdir(parents=True, exist_ok=True)
            snap.write_text(out[t.name])
        assert snap.is_file(), f"missing snapshot {snap}; run with NULLGRID_UPDATE_SNAPSHOTS=1"
        assert out[t.name] == snap.read_text(), f"{t.name} differs from {snap}"


def test_quickshell_json_is_valid(paths):
    import json
    _, out = rendered(paths)
    data = json.loads(out["quickshell"])
    assert data["colors"]["primary"] == "#5ef2f2"
    assert data["widgets"]["ram_gauge"]["visible"] is True
    assert data["durations"] == {"fast": 120, "normal": 180, "slow": 220}


def test_lite_profile_and_reduce_motion(paths):
    _, out = rendered(paths, '[performance]\nprofile = "lite"\n')
    assert "enabled = false" in out["hyprland"].split("blur {")[1].split("}")[0]
    assert "animation =" not in out["hyprland"]
    assert '"refresh_ms": 3000' in out["quickshell"]

    _, out = rendered(paths, '[behavior]\nreduce_motion = true\n')
    assert "animation =" not in out["hyprland"]
    assert '"fast": 0' in out["quickshell"]
    assert "enabled = true" in out["hyprland"].split("blur {")[1].split("}")[0]


def test_animation_speed_scales_durations(paths):
    _, out = rendered(paths, '[behavior]\nanimation_speed = 2.0\n')
    assert '"normal": 90' in out["quickshell"]


def test_apply_is_idempotent(paths):
    s = config.load(paths)
    first = render.apply(s, paths)
    assert len(first.written) == 11 and not first.backups
    assert all(t.path.is_file() for t in first.written)
    second = render.apply(s, paths)
    assert second.written == [] and len(second.unchanged) == 11


def test_hand_edits_are_backed_up(paths):
    s = config.load(paths)
    render.apply(s, paths)
    kitty = paths.config_home / "kitty" / "nullgrid-theme.conf"
    kitty.write_text(kitty.read_text() + "font_size 20\n")
    assert render.check_drift(render.load_manifest(paths)[0], render.read_state(paths)) == "edited"
    # Same content as before the edit -> not "unchanged": the file must be restored.
    report = render.apply(s, paths)
    assert [t.name for t in report.written] == ["kitty"]
    assert report.backups == [kitty.with_name("nullgrid-theme.conf.bak")]
    assert "font_size 20" in report.backups[0].read_text()
    assert "font_size 20" not in kitty.read_text()


def test_foreign_file_is_backed_up(paths):
    mako = paths.config_home / "mako" / "config"
    mako.parent.mkdir(parents=True)
    mako.write_text("my own mako config\n")
    report = render.apply(config.load(paths), paths)
    assert mako.with_name("config.bak").read_text() == "my own mako config\n"
    assert mako in [b.with_name("config") for b in report.backups]


def test_template_error_writes_nothing(paths):
    paths.user_templates.mkdir(parents=True)
    (paths.user_templates / "mako.conf.j2").write_text("{{ c.no_such_color }}\n")
    with pytest.raises(render.RenderError, match="mako"):
        render.apply(config.load(paths), paths)
    assert not (paths.config_home / "kitty").exists()


def test_user_manifest_overrides(paths):
    paths.user_templates.mkdir(parents=True)
    (paths.user_templates / "manifest.toml").write_text("""
[btop]
enabled = false
[foot]
template = "foot.ini.j2"
target = "{config_home}/foot/colors.ini"
""")
    (paths.user_templates / "foot.ini.j2").write_text("[colors]\nbackground={{ t.background.bare }}\n")
    targets, out = rendered(paths)
    names = {t.name for t in targets}
    assert "btop" not in names and "foot" in names
    assert out["foot"] == "[colors]\nbackground=1a0b0f\n"


def test_bad_manifest_entry(paths):
    paths.user_templates.mkdir(parents=True)
    (paths.user_templates / "manifest.toml").write_text('[kitty]\nreload = "kitty"\n')
    with pytest.raises(render.RenderError, match="kitty.reload"):
        render.load_manifest(paths)


def test_dry_run_writes_nothing(paths):
    report = render.apply(config.load(paths), paths, dry_run=True)
    assert len(report.written) == 11
    assert not paths.config_home.exists()


# -- reload hooks --------------------------------------------------------------
def target(**kw):
    return render.Target(name="x", template="x", path=Path("/tmp/x"), **kw)


def test_reload_command_and_gates(monkeypatch):
    assert render.run_reload(target()) is None                         # no hook
    assert render.run_reload(target(reload=["true"])) is True
    assert render.run_reload(target(reload=["false"])) is False
    assert render.run_reload(target(reload=["no-such-binary-xyz"])) is None
    assert render.run_reload(target(reload=["true"], env="NG_TEST")) is None
    monkeypatch.setenv("NG_TEST", "a")
    assert render.run_reload(target(reload=["true"], env="NG_TEST")) is True
    assert render.run_reload(target(reload=["true"], env="NG_TEST=b")) is None
    assert render.run_reload(target(reload=["true"], process="kitty")) is None  # not running


def test_reload_signal(monkeypatch):
    sent = []
    monkeypatch.setattr(render, "_processes", lambda name: [111, 222] if name == "kitty" else [])
    monkeypatch.setattr(render.os, "kill", lambda pid, sig: sent.append((pid, sig)))
    assert render.run_reload(target(process="kitty", signal="USR1")) is True
    assert sent == [(111, render.signals.SIGUSR1), (222, render.signals.SIGUSR1)]


def test_reload_only_changed(paths, monkeypatch):
    calls = []
    monkeypatch.setattr(render, "run_reload", lambda t: calls.append(t.name) or True)
    s = config.load(paths)
    render.apply(s, paths)
    calls.clear()
    assert render.apply(s, paths).reloaded == []
    assert len(render.apply(s, paths, reload="all").reloaded) == 11

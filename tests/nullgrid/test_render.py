import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from ngtest import REPO, write_config
from nullgrid import config, render

SNAPSHOTS = Path(__file__).parent / "snapshots"
UPDATE = os.environ.get("NULLGRID_UPDATE_SNAPSHOTS") == "1"
ALL_TARGETS = {"kitty", "hyprland", "hyprland-keys", "sway", "sway-keys", "wallpaper", "hyprlock", "sfx",
               "quickshell", "fuzzel", "btop", "nvim", "toolkit", "gtk", "gtk-dark", "gtk4", "qt", "qt-style",
               "qt6ct", "zathura", "tty", "shell-env", "starship",
               "starship-tty", "fastfetch", "tmux", "yazi", "yazi-tty", "lazygit", "cava", "cava-tty", "banner"}
N = len(ALL_TARGETS)
SHARED_RELOADS = 5  # hyprland(-keys), sway(-keys), toolkit + gtk + gtk-dark + gtk4: one reload each


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
    assert {t.name for t in targets} == ALL_TARGETS
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


def _lua_flag(lua: str, table: str) -> str:
    return re.search(table + r" = \{\s*enabled = (\w+)", lua).group(1)


def test_lite_profile_and_reduce_motion(paths):
    _, out = rendered(paths, '[performance]\nprofile = "lite"\n')
    assert _lua_flag(out["hyprland"], "blur") == "false"
    assert _lua_flag(out["hyprland"], "glow") == "false"
    assert "hl.animation(" not in out["hyprland"]
    assert '"refresh_ms": 3000' in out["quickshell"]

    _, out = rendered(paths, '[behavior]\nreduce_motion = true\n')
    assert "hl.animation(" not in out["hyprland"]
    assert '"fast": 0' in out["quickshell"]
    assert _lua_flag(out["hyprland"], "blur") == "true"

    _, out = rendered(paths, "[behavior]\n")  # defaults: 180 ms -> 1.8 ds
    assert 'leaf = "windowsIn", enabled = true, speed = 1.8,' in out["hyprland"]


def test_animation_speed_scales_durations(paths):
    _, out = rendered(paths, '[behavior]\nanimation_speed = 2.0\n')
    assert '"normal": 90' in out["quickshell"]


def test_apply_is_idempotent(paths):
    s = config.load(paths)
    first = render.apply(s, paths)
    assert len(first.written) == N and not first.backups
    assert all(t.path.is_file() for t in first.written)
    second = render.apply(s, paths)
    assert second.written == [] and len(second.unchanged) == N


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
    fuzzel = paths.config_home / "fuzzel" / "fuzzel.ini"
    fuzzel.parent.mkdir(parents=True)
    fuzzel.write_text("my own fuzzel config\n")
    report = render.apply(config.load(paths), paths)
    assert fuzzel.with_name("fuzzel.ini.bak").read_text() == "my own fuzzel config\n"
    assert fuzzel in [b.with_name("fuzzel.ini") for b in report.backups]


def test_template_error_writes_nothing(paths):
    paths.user_templates.mkdir(parents=True)
    (paths.user_templates / "fuzzel.ini.j2").write_text("{{ c.no_such_color }}\n")
    with pytest.raises(render.RenderError, match="fuzzel"):
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
    assert len(report.written) == N
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
    # {target} is the generated file; other braces (awk, shell) pass through untouched
    assert render.run_reload(target(reload=["sh", "-c", "test {target} = /tmp/x && echo '{x}' | awk '{print $1}'"])) is True


def test_reload_signal(monkeypatch):
    sent = []
    monkeypatch.setattr(render, "_processes", lambda name: [111, 222, 333] if name == "kitty" else [])
    monkeypatch.setattr(render, "_catches", lambda pid, sig: pid != 333)  # 333 is still starting up
    monkeypatch.setattr(render.os, "kill", lambda pid, sig: sent.append((pid, sig)))
    assert render.run_reload(target(process="kitty", signal="USR1")) is True
    assert sent == [(111, render.signals.SIGUSR1), (222, render.signals.SIGUSR1)]
    monkeypatch.setattr(render, "_catches", lambda pid, sig: False)
    assert render.run_reload(target(process="kitty", signal="USR1")) is None


def test_catches_reads_the_signal_mask():
    import signal
    import subprocess
    import sys
    code = "import signal, sys, time; signal.signal(signal.SIGUSR1, lambda *a: None); print(1, flush=True); time.sleep(30)"
    proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE)
    try:
        proc.stdout.readline()  # the handler is installed
        assert render._catches(proc.pid, signal.SIGUSR1)
        assert not render._catches(proc.pid, signal.SIGUSR2)
    finally:
        proc.kill()
        proc.wait()
    assert not render._catches(999_999_999, signal.SIGUSR1)


def test_reload_only_changed(paths, monkeypatch):
    calls = []
    monkeypatch.setattr(render, "run_reload", lambda t: calls.append(t.name) or True)
    s = config.load(paths)
    render.apply(s, paths)
    calls.clear()
    assert render.apply(s, paths).reloaded == []
    assert len(render.apply(s, paths, reload="all").reloaded) == N - SHARED_RELOADS


def test_generated_toml_and_json_parse(paths):
    import json
    import tomllib
    _, out = rendered(paths)
    for name in ("starship", "starship-tty", "yazi", "yazi-tty"):
        tomllib.loads(out[name])
    json.loads("\n".join(l for l in out["fastfetch"].splitlines() if not l.lstrip().startswith("//")))  # JSONC
    json.loads(out["quickshell"])
    json.loads(out["wallpaper"])


@pytest.mark.skipif(shutil.which("luac") is None, reason="needs luac (package lua)")
@pytest.mark.parametrize("preset", ["crimson-hud", "toxic-grid"])
def test_generated_lua_compiles(paths, tmp_path, preset):
    """Hyprland's config is Lua: a syntax error would leave the desktop unconfigured."""
    _, out = rendered(paths, f'[theme]\npreset = "{preset}"\n')
    for name in ("hyprland", "hyprland-keys", "nvim"):
        f = tmp_path / f"{name}.lua"
        f.write_text(out[name])
        result = subprocess.run(["luac", "-p", str(f)], capture_output=True, text=True)
        assert result.returncode == 0, f"{name}: {result.stderr}"
    for f in (REPO / "config/hypr/nullgrid.lua", REPO / "config/skel/.config/hypr/hyprland.lua"):
        result = subprocess.run(["luac", "-p", str(f)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr


def test_tty_variants_use_only_console_glyphs(paths):
    """The console font (Terminus) has no powerline/Nerd glyphs; TTY variants must not use them."""
    _, out = rendered(paths)
    console = set("─│┌┐└┘├┤┬┴┼█░▒■▲▼►◄◆·•›»↑↓")  # non-ASCII glyphs the Terminus font has
    for name in ("starship-tty", "yazi-tty", "tmux", "cava-tty", "tty", "banner"):
        bad = {ch for ch in out[name] if ord(ch) > 127 and ch not in console}
        assert not bad, f"{name} uses glyphs the console font lacks: {bad}"
    assert any(0xE000 <= ord(ch) <= 0xF8FF for ch in out["starship"])  # desktop prompt does
    assert "[icon]" in out["yazi-tty"] and "[icon]" not in out["yazi"]


def test_ansi_roles_follow_the_palette(paths):
    _, out = rendered(paths, '[theme]\npreset = "toxic-grid"\n')
    assert "NULLGRID_ANSI_PRIMARY=2" in out["shell-env"]        # acid green is slot 2
    assert '"primary": 2' in out["quickshell"]
    assert "colour2" in out["tmux"]
    _, out = rendered(paths, '[theme]\npreset = "crimson-hud"\n')
    assert "NULLGRID_ANSI_PRIMARY=6" in out["shell-env"]        # neon cyan is slot 6
    assert "NULLGRID_ANSI_DIM=7" in out["shell-env"]            # a gray, not green

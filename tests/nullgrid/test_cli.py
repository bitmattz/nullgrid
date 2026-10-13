import json
import stat

from ngtest import write_config


def test_version(run, capsys):
    import pytest
    with pytest.raises(SystemExit):
        run("--version")
    assert "nullgrid" in capsys.readouterr().out


def test_theme_list_marks_active(run):
    code, out, _ = run("theme", "list")
    assert code == 0
    assert "* crimson-hud" in out and "  ice-protocol" in out


def test_theme_set_restyles_everything(run, paths):
    assert run("theme", "set", "ice-protocol")[0] == 0
    assert 'preset = "ice-protocol"' in paths.config_file.read_text()
    kitty = (paths.config_home / "kitty" / "nullgrid-theme.conf").read_text()
    assert "background           #070a0f" in kitty
    data = json.loads((paths.config_dir / "generated" / "theme.json").read_text())
    assert data["name"] == "ice-protocol"

    code, out, _ = run("theme", "set", "crimson-hud")
    assert code == 0 and "updated" in out and "kitty" in out


def test_theme_set_unknown(run, paths):
    code, _, err = run("theme", "set", "ice-protocl")
    assert code == 1 and "did you mean 'ice-protocol'" in err
    assert not paths.config_file.exists()


def test_theme_set_keeps_or_resets_color_overrides(run, paths):
    write_config(paths, '[theme.colors]\nprimary = "#123456"\n')
    code, out, _ = run("theme", "set", "toxic-grid")
    assert code == 0 and "still overrides theme.colors.primary" in out
    code, out, _ = run("theme", "set", "toxic-grid", "--reset-colors")
    assert code == 0 and "primary" not in paths.config_file.read_text()


def test_theme_reload_and_dry_run(run, paths):
    code, out, _ = run("theme", "reload", "--dry-run")
    assert code == 0 and "would update" in out and not paths.config_home.exists()
    assert run("theme", "reload")[0] == 0
    code, out, _ = run("theme", "reload")
    assert "already up to date" in out


def test_invalid_config_fails_without_touching_files(run, paths):
    run("theme", "reload")
    kitty = paths.config_home / "kitty" / "nullgrid-theme.conf"
    before = kitty.read_text()
    write_config(paths, '[theme]\npreset = "ice-protocol"\n[sound]\nvolume = 9\n')
    code, _, err = run("theme", "reload")
    assert code == 1 and "sound.volume" in err
    assert kitty.read_text() == before


def test_widget_toggle(run, paths):
    code, out, _ = run("widget", "toggle", "ram_gauge")
    assert code == 0 and "ram_gauge: off" in out
    data = json.loads((paths.config_dir / "generated" / "theme.json").read_text())
    assert data["widgets"]["ram_gauge"]["visible"] is False
    run("widget", "toggle", "ram_gauge")
    assert "on   ram_gauge" in run("widget", "list")[1]
    code, _, err = run("widget", "toggle", "ram")
    assert code == 1 and "ram_gauge" in err


def test_mode(run, paths):
    assert run("mode")[1].strip() == "desktop"
    assert run("mode", "tty")[0] == 0
    assert run("mode")[1].strip() == "tty"
    data = json.loads((paths.config_dir / "generated" / "theme.json").read_text())
    assert data["behavior"]["default_mode"] == "tty"


def test_doctor(run, paths):
    code, out, _ = run("doctor")
    assert code == 0 and "not generated yet" in out
    run("theme", "reload")
    code, out, _ = run("doctor")
    assert code == 0 and "up to date" in out
    write_config(paths, '[theme]\npreset = "gone"\n')
    code, out, _ = run("doctor")
    assert code == 1 and "no theme named 'gone'" in out


def test_doctor_checks_the_compositor_configs(run, paths, monkeypatch):
    from nullgrid import doctor
    monkeypatch.setattr(doctor.shutil, "which", lambda name: f"/usr/bin/{name}" if name != "swaybg" else None)
    run("init", "-q")
    code, out, _ = run("doctor")
    assert "hyprland.lua" not in out and "swaybg not found (package swaybg): no wallpaper" in out
    (paths.config_home / "hypr" / "hyprland.lua").write_text('hl.config({})\n')
    code, out, _ = run("doctor")
    assert code == 0
    assert "doesn't load nullgrid-theme.lua or nullgrid-keys.lua: theme and keybind changes won't reach Hyprland" in out


def test_doctor_reports_a_failed_desktop_start(run, paths):
    paths.state_dir.mkdir(parents=True)
    (paths.state_dir / "session-status").write_text(
        "2026-10-13 10:00:00 hyprland could not start (status 1, log: x)\n"
        "2026-10-13 10:00:02 sway ran and was left normally\n")
    code, out, _ = run("doctor")
    assert code == 0 and "last desktop start: 2026-10-13 10:00:00 hyprland could not start" in out


def test_doctor_flags_low_contrast(run, paths):
    write_config(paths, '[theme.colors]\ntext = "#222222"\n')
    code, out, _ = run("doctor")
    assert code == 0 and "low contrast: colors.text on colors.bg" in out


def test_theme_edit(run, paths, tmp_path, monkeypatch):
    editor = tmp_path / "editor.sh"
    editor.write_text('#!/bin/sh\nsed -i \'s/^preset = .*/preset = "toxic-grid"/\' "$1"\n')
    editor.chmod(editor.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("EDITOR", str(editor))
    code, out, _ = run("theme", "edit")
    assert code == 0 and "updated" in out
    assert json.loads((paths.config_dir / "generated" / "theme.json").read_text())["name"] == "toxic-grid"


def test_theme_edit_reverts_invalid_edit_without_a_terminal(run, paths, tmp_path, monkeypatch):
    editor = tmp_path / "editor.sh"
    editor.write_text('#!/bin/sh\necho "[bogus]" >> "$1"\n')
    editor.chmod(editor.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("EDITOR", str(editor))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    code, _, err = run("theme", "edit")
    assert code == 1 and "reverted" in err
    assert "[bogus]" not in paths.config_file.read_text()


def test_init_copies_dotfiles_without_overwriting(run, paths):
    kitty = paths.config_home / "kitty" / "kitty.conf"
    kitty.parent.mkdir(parents=True)
    kitty.write_text("# mine\n")
    code, out, _ = run("init")
    assert code == 0
    assert kitty.read_text() == "# mine\n"                              # kept
    assert (paths.config_home / "nvim" / "colors" / "nullgrid.lua").is_file()
    assert (paths.config_home / "tmux" / "tmux.conf").is_file()
    assert paths.config_file.is_file() and paths.init_marker.is_file()
    assert (paths.config_home / "starship.toml").is_file()               # theme rendered too
    assert "kept 1 existing file" in out

    code, _, _ = run("init", "--reset", "--quiet")
    assert code == 0 and "include nullgrid-theme.conf" in kitty.read_text()
    assert kitty.with_name("kitty.conf.bak").read_text() == "# mine\n"


def test_skel_files_follow_xdg_config_home(run, paths, monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "elsewhere"))
    assert run("init", "-q")[0] == 0
    assert (tmp_path / "elsewhere" / "kitty" / "kitty.conf").is_file()


def test_init_sets_up_the_desktop_configs(run, paths):
    assert run("init", "-q")[0] == 0
    hypr = paths.config_home / "hypr"
    assert 'load(config .. "nullgrid-theme.lua")' in (hypr / "hyprland.lua").read_text()
    assert (hypr / "nullgrid-theme.lua").is_file() and (hypr / "nullgrid-keys.lua").is_file()
    assert "include ~/.config/sway/nullgrid-keys" in (paths.config_home / "sway" / "config").read_text()
    assert (paths.config_home / "sway" / "nullgrid-theme").is_file()


def test_theme_next_and_prev_cycle(run, paths):
    code, out, _ = run("theme", "next")
    assert code == 0 and out.startswith("theme: ice-protocol")
    assert run("theme", "next")[1].startswith("theme: toxic-grid")
    assert run("theme", "next")[1].startswith("theme: crimson-hud")   # wraps around
    assert run("theme", "prev")[1].startswith("theme: toxic-grid")


def test_keys_lists_the_active_set(run):
    code, out, _ = run("keys")
    assert code == 0
    assert "keybinds: default" in out
    assert "SUPER+ENTER" in out and "terminal" in out
    assert "SUPER+SHIFT+1..0" in out and "move window to workspace 1-10" in out


def test_wallpaper_render(run, paths, tmp_path):
    code, out, _ = run("wallpaper", "render", "--size", "1024x768")
    assert code == 0 and out.startswith('<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="768"')
    assert (paths.config_dir / "generated" / "wallpaper.json").is_file()  # generated on demand
    dest = tmp_path / "wp.svg"
    assert run("wallpaper", "render", "-o", str(dest))[0] == 0
    assert 'width="1920"' in dest.read_text()


def test_wallpaper_render_bad_size(run, capsys):
    import pytest
    with pytest.raises(SystemExit):
        run("wallpaper", "render", "--size", "huge")
    assert "expected a size like 1920x1080" in capsys.readouterr().err


def test_wallpaper_apply_outside_wayland(run):
    code, _, err = run("wallpaper", "apply")
    assert code == 1 and "WAYLAND_DISPLAY" in err

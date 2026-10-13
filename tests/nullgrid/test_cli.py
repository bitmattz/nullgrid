import json
import stat

from conftest import write_config


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
    assert code == 0 and "updated 11 file(s)" in out


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
    assert code == 0 and "would update 11" in out and not paths.config_home.exists()
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
    assert code == 0 and "updated 11" in out
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

import json
import tomllib

import pytest

from ngtest import REPO, write_config
from nullgrid import config, keybinds, render


def load_default():
    data, errors = keybinds.validate(config.read_toml(REPO / "config/keybinds/default.toml"),
                                     REPO / "config/keybinds/default.toml")
    assert errors == []
    return data


def write_set(paths, name, text):
    d = paths.keybinds[0]
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.toml").write_text(text)


def test_default_set_binds_every_action():
    data = load_default()
    bound = {b.action for b in keybinds.binds(data)}
    assert bound >= set(keybinds.ACTIONS) | set(keybinds.PREFIX_ACTIONS)
    ws = [b for b in keybinds.binds(data) if b.action == "workspace"]
    assert [(b.combo, b.workspace) for b in ws][::9] == [("SUPER+1", 1), ("SUPER+0", 10)]


def test_summary_and_essentials():
    data = load_default()
    rows = keybinds.summary(data)
    assert ("SUPER+LEFT / SUPER+H", "focus left", "focus_left") in rows
    assert ("SUPER+1..0", "go to workspace 1-10", "workspace") in rows
    assert sum(r[2] == "workspace" for r in rows) == 1
    ess = keybinds.essentials(data)
    assert ess[0] == ("SUPER+ENTER", "terminal")
    assert len(ess) == len(keybinds.ESSENTIALS)


@pytest.mark.parametrize("text, problem", [
    ('[keys]\nterminal = "SUPER+Return"\nlauncher = "SUPER+return"\n', "already bound by keys.terminal"),
    ('[keys]\nterminl = "SUPER+X"\n', "did you mean 'terminal'"),
    ('[keys]\nterminal = "WIN+Return"\n', "keys.terminal: expected a combo"),
    ('[keys]\nworkspace = "SUPER+1"\n', "keys.workspace: expected modifiers only"),
    ('[keys]\nworkspace = "SUPER"\n[exec]\n"SUPER+3" = "foot"\n', "exec.SUPER+3: SUPER+3 is already bound"),
    ('[exec]\n"SUPER+B" = ""\n', "exec.SUPER+B: expected a command"),
])
def test_validation_errors(text, problem):
    _, errors = keybinds.validate(tomllib.loads(f'[meta]\nname = "x"\n{text}'), "x.toml")
    assert any(problem in e for e in errors), errors


def test_user_set_is_selected_and_rendered(paths):
    write_set(paths, "mine", '[meta]\nname = "mine"\n[keys]\nterminal = "ALT+Return"\nclose = "ALT+SHIFT+Q"\n'
                             'workspace = "ALT"\n[exec]\n"ALT+W" = "firefox --new-window"\n')
    write_config(paths, '[behavior]\nkeybinds = "mine"\n')
    settings = config.load(paths)
    targets = render.load_manifest(paths)
    out = render.render_all(settings, paths, targets)
    assert 'hl.bind("ALT + Return", hl.dsp.exec_cmd("kitty"))' in out["hyprland-keys"]
    assert 'hl.bind("ALT + SHIFT + Q", hl.dsp.window.close())' in out["hyprland-keys"]
    assert 'hl.bind("ALT + 0", hl.dsp.focus({ workspace = 10 }))' in out["hyprland-keys"]
    assert 'hl.dsp.exec_cmd("firefox --new-window")' in out["hyprland-keys"]
    assert "SUPER + D" not in out["hyprland-keys"]          # nothing from the default set
    assert "bindsym Mod1+Return exec \"kitty\"" in out["sway-keys"]
    assert "bindsym Mod1+Shift+q kill" in out["sway-keys"]  # letters lowercase for sway
    assert "bindsym Mod1+0 workspace number 10" in out["sway-keys"]
    assert json.loads(out["wallpaper"])["keymap"][0] == ["ALT+ENTER", "terminal"]


def test_empty_list_unbinds(paths):
    write_set(paths, "few", '[meta]\nname = "few"\n[keys]\nterminal = "SUPER+Return"\nlauncher = []\n')
    write_config(paths, '[behavior]\nkeybinds = "few"\n')
    data = config.load(paths).keybinds
    assert [b.action for b in keybinds.binds(data)] == ["terminal"]


def test_missing_set_is_a_config_error(paths):
    write_config(paths, '[behavior]\nkeybinds = "nope"\n')
    with pytest.raises(config.ConfigError, match="no keybind set named 'nope' .*default"):
        config.load(paths)


def test_broken_set_names_its_file(paths):
    write_set(paths, "bad", '[meta]\nname = "bad"\n[keys]\nclose = 3\n')
    write_config(paths, '[behavior]\nkeybinds = "bad"\n')
    with pytest.raises(config.ConfigError) as exc:
        config.load(paths)
    assert str(exc.value.source).endswith("keybinds/bad.toml")


def test_combo_filters():
    assert render.hypr_combo("SUPER+SHIFT+Return") == "SUPER + SHIFT + Return"
    assert render.sway_combo("SUPER+CTRL+ALT+L") == "Mod4+Control+Mod1+l"
    assert render.sway_combo("Print") == "Print"
    assert render.lua_string('say "hi"\\n\n') == '"say \\"hi\\"\\\\n\\n"'

import tomllib

import pytest

from conftest import REPO, write_config
from nullgrid import config


def test_default_config_file_matches_schema_defaults():
    raw = tomllib.loads((REPO / "config" / "nullgrid.toml").read_text())
    assert config.validate_config(raw, "default") == config.CONFIG.validate({}, "", [])


@pytest.mark.parametrize("name", ["crimson-hud", "ice-protocol", "toxic-grid"])
def test_presets_are_valid_and_readable(name):
    theme = config.load_theme(REPO / "themes" / f"{name}.toml")
    c = theme["colors"]
    assert c["text"].contrast(c["bg"]) >= 4.5
    assert c["text"].contrast(c["surface"]) >= 4.5
    assert c["primary"].contrast(c["bg"]) >= 3


def test_no_config_uses_defaults(paths):
    s = config.load(paths)
    assert s.config_path is None
    assert s.theme["meta"]["name"] == "crimson-hud"
    assert s.config["behavior"]["default_mode"] == "desktop"


def test_overrides_beat_the_preset(paths):
    write_config(paths, """
[theme]
preset = "ice-protocol"
[theme.colors]
primary = "#123456"
[theme.colors.terminal]
color1 = "#abcdef"
[theme.style]
corners = "round"
""")
    s = config.load(paths)
    assert str(s.theme["colors"]["primary"]) == "#123456"
    assert str(s.theme["colors"]["terminal"]["color1"]) == "#abcdef"
    assert str(s.theme["colors"]["terminal"]["color2"]) == "#5fe0c0"  # rest of the preset kept
    assert s.theme["style"]["corners"] == "round"
    assert config.overrides_in_use(s.config) == [
        "theme.colors.primary", "theme.colors.terminal.color1", "theme.style.corners"]


def test_unknown_preset_lists_available(paths):
    write_config(paths, '[theme]\npreset = "nope"\n')
    with pytest.raises(config.ConfigError) as exc:
        config.load(paths)
    assert "no theme named 'nope'" in exc.value.problems[0]
    assert "crimson-hud" in exc.value.problems[0]


def test_bad_values_are_all_reported(paths):
    write_config(paths, """
[theme.colors]
primary = "cyan"
[sound]
volume = 3
[widgets.ram_gauge]
visble = false
""")
    with pytest.raises(config.ConfigError) as exc:
        config.load(paths)
    problems = exc.value.problems
    assert any(p.startswith("theme.colors.primary:") for p in problems)
    assert any(p.startswith("sound.volume: must be between 0 and 1") for p in problems)
    assert "widgets.ram_gauge.visble: unknown key (did you mean 'visible'?)" in problems


def test_toml_syntax_error(paths):
    write_config(paths, "[theme\n")
    with pytest.raises(config.ConfigError) as exc:
        config.load(paths)
    assert "not valid TOML" in exc.value.problems[0]


def test_user_theme_shadows_system_theme(paths):
    src = (REPO / "themes" / "crimson-hud.toml").read_text()
    paths.user_themes.mkdir(parents=True)
    (paths.user_themes / "crimson-hud.toml").write_text(src.replace('"#5ef2f2"', '"#00ff00"', 1))
    (paths.user_themes / "mine.toml").write_text(src.replace('name = "crimson-hud"', 'name = "mine"'))
    assert set(config.list_themes(paths)) == {"crimson-hud", "ice-protocol", "toxic-grid", "mine"}
    assert str(config.load(paths).theme["colors"]["primary"]) == "#00ff00"


def test_theme_name_must_match_file(paths):
    paths.user_themes.mkdir(parents=True)
    (paths.user_themes / "other.toml").write_text((REPO / "themes" / "crimson-hud.toml").read_text())
    with pytest.raises(config.ConfigError, match="meta.name"):
        config.load_theme(paths.user_themes / "other.toml")


def test_document_edit_keeps_comments_and_refuses_invalid(paths):
    doc = config.ConfigDocument(paths)
    doc.set("behavior.default_mode", "tty")
    doc.save()
    text = paths.config_file.read_text()
    assert "# NULLGRID configuration" in text and 'default_mode = "tty"' in text
    doc.set("behavior.default_mode", "nope")
    with pytest.raises(config.ConfigError):
        doc.save()
    assert 'default_mode = "tty"' in paths.config_file.read_text()

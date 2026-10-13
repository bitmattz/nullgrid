import json
import xml.etree.ElementTree as ET

import pytest

from ngtest import REPO, write_config
from nullgrid import config, logo, render, wallpaper

SVG = "{http://www.w3.org/2000/svg}"


def spec(paths, config_text=""):
    if config_text:
        write_config(paths, config_text)
    targets = [t for t in render.load_manifest(paths) if t.name == "wallpaper"]
    return json.loads(render.render_all(config.load(paths), paths, targets)["wallpaper"])


def texts(svg: str) -> str:
    root = ET.fromstring(svg)
    return " ".join("".join(t.itertext()) for t in root.iter(f"{SVG}text"))


# -- logo ------------------------------------------------------------------------
def test_ascii_logo_matches_the_shipped_file():
    """assets/logo/nullgrid.txt is generated; regenerate with assets/logo/generate.py."""
    assert "\n".join(logo.ascii_art()) + "\n" == (REPO / "assets/logo/nullgrid.txt").read_text()


def test_lattice_has_a_hole():
    edges = logo.FULL.edges()
    assert len(edges) == 2 * 4 * 5 - 4
    assert ((2, 2), (2, 3)) not in edges and ((2, 1), (2, 2)) in edges
    assert len(logo.SMALL.edges()) == 2 * 2 * 3 - 4


def test_logo_svg_parses_and_is_recolorable():
    root = ET.fromstring(logo.svg("#112233", "#445566"))
    assert root.get("width") == "256"
    svg = logo.svg("#112233", "#445566")
    assert "#112233" in svg and "#445566" in svg and "#5ef2f2" not in svg


# -- wallpaper ---------------------------------------------------------------------
@pytest.mark.parametrize("preset", ["crimson-hud", "ice-protocol", "toxic-grid"])
@pytest.mark.parametrize("size", [(1920, 1080), (1366, 768), (3840, 2160), (1080, 1920), (800, 600)])
def test_wallpaper_renders_for_every_theme_and_size(paths, preset, size):
    s = spec(paths, f'[theme]\npreset = "{preset}"\n')
    svg = wallpaper.render(s, *size)
    root = ET.fromstring(svg)  # well-formed XML
    assert (root.get("width"), root.get("height")) == tuple(map(str, size))
    words = texts(svg)
    assert "NULLGRID" in words and f"THEME :: {preset.upper()}" in words
    assert s["colors"]["primary"] in svg


def test_wallpaper_is_deterministic(paths):
    s = spec(paths)
    assert wallpaper.render(s, 1920, 1080) == wallpaper.render(s, 1920, 1080)
    assert wallpaper.render(s, 1920, 1080) != wallpaper.render({**s, "seed": 8}, 1920, 1080)


def test_decor_switches(paths):
    full = wallpaper.render(spec(paths), 1920, 1080)
    assert "url(#scan)" not in full.split("</defs>")[1]  # scanlines are off by default
    assert "KEYMAP" in texts(full) and "SUPER+ENTER" in texts(full)

    bare = wallpaper.render(spec(paths, "[decor]\ncircuit_lines = false\nmatrix_rain = false\n"
                                        "data_text = false\nscanlines = true\n"), 1920, 1080)
    assert "url(#scan)" in bare.split("</defs>")[1]
    assert "<circle" not in bare.split("</defs>")[1]       # no trace vias
    assert texts(bare).split() == ["NULLGRID", "OPERATING", "SYSTEM", "//", f"v{render.__version__}",
                                   "THEME", "::", "CRIMSON-HUD", "NG-UNIT", "04", "//", "SECTOR", "7F",
                                   "//", "NODE", "2.2"]
    assert len(bare) < len(full) / 3


def test_wallpaper_text_is_escaped(paths):
    s = spec(paths)
    s["keymap"] = [["SUPER+<", "a & b"]]
    s["fonts"] = {**s["fonts"], "mono": 'Odd "Font" & Co'}
    ET.fromstring(wallpaper.render(s, 1280, 720))


def test_layers_are_independent(paths):
    """Turning the matrix columns off leaves the circuit traces where they were."""
    traces = lambda svg: [l for l in svg.split("<path") if "stroke-linejoin" in l]  # noqa: E731
    full = wallpaper.render(spec(paths), 1920, 1080)
    no_matrix = wallpaper.render(spec(paths, "[decor]\nmatrix_rain = false\n"), 1920, 1080)
    assert traces(full) == traces(no_matrix) and len(traces(full)) > 5


# -- screens, cache, swaybg -----------------------------------------------------------
def test_outputs_from_hyprland_and_sway(monkeypatch):
    monkeypatch.setenv("HYPRLAND_INSTANCE_SIGNATURE", "x")
    monkeypatch.setattr(wallpaper, "_json_cmd", lambda argv: [
        {"name": "eDP-1", "width": 1920, "height": 1200, "transform": 0},
        {"name": "DP-2", "width": 2560, "height": 1440, "transform": 1}])
    assert wallpaper.outputs() == [wallpaper.Output("eDP-1", 1920, 1200), wallpaper.Output("DP-2", 1440, 2560)]

    monkeypatch.delenv("HYPRLAND_INSTANCE_SIGNATURE")
    monkeypatch.setenv("SWAYSOCK", "x")
    monkeypatch.setattr(wallpaper, "_json_cmd", lambda argv: [
        {"name": "HDMI-A-1", "active": True, "transform": "flipped-270",
         "current_mode": {"width": 1920, "height": 1080}},
        {"name": "off", "active": False}])
    assert wallpaper.outputs() == [wallpaper.Output("HDMI-A-1", 1080, 1920)]

    monkeypatch.delenv("SWAYSOCK")
    assert wallpaper.outputs() == []


def test_cached_png_renders_once(paths, monkeypatch):
    rendered = []

    def fake_png(svg, dest):
        rendered.append(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"png")
    monkeypatch.setattr(wallpaper, "to_png", fake_png)
    s = spec(paths)
    a = wallpaper.cached_png(paths, s, 1920, 1080)
    assert wallpaper.cached_png(paths, s, 1920, 1080) == a and len(rendered) == 1
    b = wallpaper.cached_png(paths, {**s, "theme": "x"}, 1920, 1080)
    assert b != a and b.parent == paths.cache_dir / "wallpaper" and len(rendered) == 2


def test_apply_starts_swaybg_once(paths, monkeypatch, tmp_path):
    render.apply(config.load(paths), paths, reload="none")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-9")
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(wallpaper.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(wallpaper, "outputs", lambda: [wallpaper.Output("Virtual-1", 1280, 800)])
    monkeypatch.setattr(wallpaper, "cached_png", lambda paths, s, w, h: tmp_path / f"{w}x{h}.png")
    started = []

    class Proc:
        pid = 4242

        def __init__(self, argv, **kw):
            started.append(argv)
    monkeypatch.setattr(wallpaper.subprocess, "Popen", Proc)
    monkeypatch.setattr(wallpaper, "_alive", lambda pid: pid == 4242)
    wallpaper.apply(paths)
    assert started == [["swaybg", "-o", "Virtual-1", "-i", str(tmp_path / "1280x800.png"), "-m", "fill"]]
    wallpaper.apply(paths)  # same picture, swaybg still running: nothing to do
    assert len(started) == 1


def test_apply_needs_a_wayland_session(paths):
    with pytest.raises(wallpaper.WallpaperError, match="WAYLAND_DISPLAY"):
        wallpaper.apply(paths)

"""GTK/Qt/icon/cursor theming: the icon and cursor generators, `nullgrid toolkit apply` (with a
fake gsettings), and the templates behind them."""
import json
import os
import re
import shutil
import xml.etree.ElementTree as ET

import pytest

from ngtest import REPO, write_config
from nullgrid import config, cursors, glyphs, icons, render, toolkit

needs_rsvg = pytest.mark.skipif(shutil.which("rsvg-convert") is None, reason="needs rsvg-convert (librsvg)")
SPEC = {"colors": {"bg": "#1a0b0f", "surface": "#24111a", "primary": "#5ef2f2", "secondary": "#ff3b4e",
                   "dim": "#7a8a8f", "text": "#e6f7f7"}, "cursor_size": 24}


# --------------------------------------------------------------------------- glyphs + icons
def test_shell_icons_match_the_glyph_library():
    """shell/Icons.js and glyphs.py draw the same symbols."""
    js = dict(re.findall(r'^\s*(\w+): "([^"]*)",?$', (REPO / "shell/Icons.js").read_text(), re.M))
    assert js, "no paths found in Icons.js"
    for name, path in js.items():
        assert glyphs.GLYPHS.get(name) == path, f"{name} differs between Icons.js and glyphs.py"


def test_every_icon_is_valid_svg_in_the_palette():
    seen = set()
    for context, entries in icons.ICONS.items():
        for frame, glyph, names in entries:
            assert glyph is None or glyph == "logo" or glyph in glyphs.GLYPHS, glyph
            for n in names:
                assert (context, n) not in seen, f"{n} listed twice in {context}"
                seen.add((context, n))
            svg = icons.svg(frame, glyph, SPEC["colors"])
            root = ET.fromstring(svg)
            assert root.get("viewBox") == "0 0 48 48"
            assert SPEC["colors"]["primary"] in svg
    # the names GTK and the start menu ask for on NULLGRID
    names = {n for _, n in seen}
    for need in ("kitty", "firefox", "org.xfce.thunar", "org.pwmt.zathura", "folder", "user-home",
                 "text-x-generic", "application-pdf", "drive-harddisk", "nullgrid", "start-here"):
        assert need in names, need


def test_build_icon_theme(tmp_path):
    d = tmp_path / "NULLGRID"
    n = icons.build(d, SPEC)
    assert n == sum(len(names) for e in icons.ICONS.values() for _, _, names in e)
    index = (d / "index.theme").read_text()
    assert "Inherits=Adwaita,hicolor" in index and "[scalable/places]" in index
    assert (d / "scalable/apps/kitty.svg").is_file()
    assert (d / "scalable/apps/utilities-terminal.svg").is_symlink()
    assert "#5ef2f2" in (d / "scalable/places/folder.svg").read_text()
    # rebuilt in other colors: replaced, not added to
    (d / "cursors").mkdir()
    icons.build(d, {"colors": dict(SPEC["colors"], primary="#b6ff3b")})
    assert "#b6ff3b" in (d / "scalable/places/folder.svg").read_text()
    assert (d / "cursors").is_dir(), "the cursors are left alone"
    assert not list(tmp_path.glob(".*tmp"))


def test_icon_stamp_follows_colors_only():
    other = {"colors": dict(SPEC["colors"], primary="#000000")}
    assert icons.stamp(SPEC) == icons.stamp(dict(SPEC, cursor_size=48))
    assert icons.stamp(SPEC) != icons.stamp(other)


# --------------------------------------------------------------------------- cursors
def test_cursor_names_are_unique_and_cover_the_basics():
    names = [n for c in cursors.CURSORS for n in (c.name, *c.aliases)]
    assert len(names) == len(set(names))
    for need in ("default", "left_ptr", "pointer", "hand2", "text", "xterm", "wait", "progress", "not-allowed",
                 "move", "grab", "grabbing", "ew-resize", "ns-resize", "nwse-resize", "nesw-resize",
                 "col-resize", "row-resize", "crosshair", "help", "copy", "alias", "zoom-in"):
        assert need in names, need
    for c in cursors.CURSORS:
        assert 0 <= c.hotspot[0] < cursors.CANVAS and 0 <= c.hotspot[1] < cursors.CANVAS


def test_xcursor_round_trip():
    px = bytes(range(16)) * 4  # 4x4 ARGB
    data = cursors.xcursor([(4, 4, 1, 2, 0, px), (4, 4, 1, 2, 50, px)])
    imgs = cursors.read_xcursor(data)
    assert [(i["size"], i["width"], i["xhot"], i["yhot"], i["delay"]) for i in imgs] == [(4, 4, 1, 2, 0), (4, 4, 1, 2, 50)]
    assert imgs[0]["pixels"] == px


def test_decode_png_filters():
    """A PNG using every filter type decodes to the right pixels."""
    import struct
    import zlib
    w, h = 3, 5
    rows = [b"".join(bytes(p) for p in [[(x * 40 + y) % 256, (y * 30) % 256, (200 - x - y) % 256, 255 - y * 20]
                                         for x in range(w)]) for y in range(h)]

    def paeth(a, b, c):
        p = a + b - c
        pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
        return a if pa <= pb and pa <= pc else (b if pb <= pc else c)

    raw, prev = b"", bytes(w * 4)
    for y, row in enumerate(rows):
        ftype = y % 5
        out = bytearray()
        for i, v in enumerate(row):
            a = row[i - 4] if i >= 4 else 0
            b = prev[i]
            c = prev[i - 4] if i >= 4 else 0
            pred = (0, a, b, (a + b) >> 1, paeth(a, b, c))[ftype]
            out.append((v - pred) & 0xFF)
        raw += bytes([ftype]) + bytes(out)
        prev = row

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    assert cursors.decode_png(png) == (w, h, bytearray(b"".join(rows)))


@needs_rsvg
def test_build_cursors(tmp_path):
    d = tmp_path / "cursors"
    n = cursors.build(d, SPEC, sizes=(24, 32))
    assert n == sum(1 + len(c.aliases) for c in cursors.CURSORS)
    default = cursors.read_xcursor((d / "default").read_bytes())
    assert [i["size"] for i in default] == [24, 32]
    assert (default[0]["xhot"], default[0]["yhot"]) == (3, 2)  # (4, 3) on the 32 canvas, scaled
    assert any(p != 0 for p in default[0]["pixels"]), "the cursor isn't blank"
    wait = cursors.read_xcursor((d / "wait").read_bytes())
    assert len(wait) == 2 * cursors.FRAMES and wait[0]["delay"] == cursors.FRAME_MS
    assert os.readlink(d / "left_ptr") == "default"


# --------------------------------------------------------------------------- toolkit apply
FAKE_GSETTINGS = """#!/usr/bin/env python3
import json, os, sys
f = os.environ["FAKE_GSETTINGS"]
db = json.load(open(f)) if os.path.exists(f) else {}
args = sys.argv[1:]
with open(f + ".log", "a") as log:
    log.write(" ".join(args) + "\\n")
if args[0] == "list-keys":
    print("gtk-theme")
elif args[0] == "get":
    print(db.get(args[2], "''"))
elif args[0] == "set":
    db[args[2]] = args[3]
    json.dump(db, open(f, "w"))
"""


@pytest.fixture
def gsettings(tmp_path, monkeypatch):
    """A fake gsettings on PATH, with a session bus "available". Returns (db, log) readers."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "gsettings").write_text(FAKE_GSETTINGS)
    (bindir / "gsettings").chmod(0o755)
    store = tmp_path / "gsettings.json"
    monkeypatch.setenv("FAKE_GSETTINGS", str(store))
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/nonexistent")
    monkeypatch.setattr(toolkit.time, "sleep", lambda s: None)

    def db():
        return json.loads(store.read_text()) if store.exists() else {}

    def log():
        p = store.with_name(store.name + ".log")
        lines = p.read_text().splitlines() if p.exists() else []
        p.unlink(missing_ok=True)
        return [l for l in lines if l.startswith("set ")]
    return db, log


def generated(paths, config_text=""):
    if config_text:
        write_config(paths, config_text)
    render.apply(config.load(paths), paths, reload="none")


@needs_rsvg
def test_toolkit_apply(paths, gsettings):
    db, log = gsettings
    generated(paths)
    res = toolkit.apply(paths)
    assert res.icons and res.cursors and not res.notes
    d = toolkit.theme_dir(paths)
    assert (d / "scalable/apps/kitty.svg").is_file() and (d / "cursors/default").is_file()
    assert db() == {"gtk-theme": "'NULLGRID'", "icon-theme": "'NULLGRID'", "cursor-theme": "'NULLGRID'",
                    "cursor-size": "24", "font-name": "'Rajdhani Medium 11'",
                    "monospace-font-name": "'JetBrains Mono 11'", "color-scheme": "'prefer-dark'"}
    log()

    # nothing changed: nothing regenerated, nothing written
    res = toolkit.apply(paths)
    assert not res.icons and not res.cursors and res.settings == [] and log() == []

    # the manifest hook (GTK theme files changed): the theme name flips and comes back
    res = toolkit.apply(paths, reload=True)
    assert log() == ["set org.gnome.desktop.interface gtk-theme 'Adwaita'",
                     "set org.gnome.desktop.interface gtk-theme 'NULLGRID'"]
    assert db()["gtk-theme"] == "'NULLGRID'"

    # a theme switch: new icons and cursors; GTK reloads them by name
    generated(paths, '[theme]\npreset = "toxic-grid"\n')
    old_cursors = os.readlink(d / "cursors")
    res = toolkit.apply(paths, reload=True)
    assert res.icons and res.cursors
    assert os.readlink(d / "cursors") != old_cursors
    flipped = {l.split()[2] for l in log()}
    assert flipped == {"gtk-theme", "icon-theme", "cursor-theme"}
    # and back: the old cursors come from the cache
    generated(paths, '[theme]\npreset = "crimson-hud"\n')
    toolkit.apply(paths)
    assert os.readlink(d / "cursors") == old_cursors


@needs_rsvg
def test_toolkit_follows_config(paths, gsettings):
    db, _ = gsettings
    generated(paths, '[theme.fonts]\nui = "Oxanium"\nsize = 13\n[theme.style]\ncursor_size = 36\n')
    toolkit.apply(paths)
    assert db()["font-name"] == "'Oxanium Medium 13'" and db()["cursor-size"] == "36"
    sizes = [i["size"] for i in cursors.read_xcursor((toolkit.theme_dir(paths) / "cursors/default").read_bytes())]
    assert 36 in sizes


@needs_rsvg
def test_toolkit_without_a_session_bus(paths, monkeypatch):
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(paths.data_home / "no-run"))
    generated(paths)
    res = toolkit.apply(paths)
    assert res.icons and res.settings == []
    assert any("session bus" in n or "gsettings" in n for n in res.notes)


def test_toolkit_spec_missing(paths):
    with pytest.raises(toolkit.ToolkitError, match="theme reload"):
        toolkit.load_spec(paths)


# --------------------------------------------------------------------------- templates
def test_toolkit_targets(paths):
    targets = {t.name: t for t in render.load_manifest(paths)}
    assert targets["gtk"].path == paths.data_home / "themes/NULLGRID/gtk-3.0/gtk.css"
    assert targets["gtk4"].path == paths.data_home / "themes/NULLGRID/gtk-4.0/gtk.css"
    # all GTK files and the toolkit spec share one reload command (it runs once)
    hooks = {tuple(targets[n].reload) for n in ("toolkit", "gtk", "gtk-dark", "gtk4")}
    assert hooks == {("nullgrid", "toolkit", "apply", "--reload", "--quiet")}
    names = list(targets)
    assert names.index("qt6ct") > max(names.index("qt"), names.index("qt-style")), \
        "qt6ct.conf must be written after the files it points to"


def test_gtk_theme_uses_the_palette(paths):
    _, out = _render(paths, '[theme]\npreset = "toxic-grid"\n[theme.style]\ncorners = "round"\n')
    css = out["gtk"]
    assert '@import url("file:///usr/share/themes/adw-gtk3-dark/gtk-3.0/gtk.css")' in css
    toxic = config.load(paths).theme["colors"]
    assert f"@define-color window_bg_color {toxic['bg']};" in css
    assert "border-radius: 6px;" in css and "-gtk-outline-radius" in css
    assert "--window-bg-color" not in css  # GTK 3 has no CSS variables
    css4 = out["gtk4"]
    assert f"--window-bg-color: {toxic['bg']};" in css4 and "-gtk-outline-radius" not in css4
    assert out["gtk-dark"] == css


def test_qt6ct_conf_changes_with_the_theme(paths):
    _, a = _render(paths)
    _, b = _render(paths, '[theme]\npreset = "ice-protocol"\n')
    rev = lambda text: re.search(r"^revision=(.+)$", text, re.M).group(1)  # noqa: E731
    assert rev(a["qt6ct"]) != rev(b["qt6ct"])
    assert "color_scheme_path=~/.config/qt6ct/colors/nullgrid.conf" in a["qt6ct"]
    assert 'general="Rajdhani,11,-1,5,500,' in a["qt6ct"]
    assert "icon_theme=NULLGRID" in a["qt6ct"]


def test_toolkit_json(paths):
    _, out = _render(paths, '[theme.style]\ncursor_size = 32\n')
    spec = json.loads(out["toolkit"])
    assert spec["cursor_size"] == 32 and spec["color_scheme"] == "prefer-dark"
    assert spec["colors"]["primary"] == "#5ef2f2"


def _render(paths, config_text=""):
    if config_text:
        write_config(paths, config_text)
    targets = render.load_manifest(paths)
    return targets, render.render_all(config.load(paths), paths, targets)


# --------------------------------------------------------------------------- CLI
def test_theme_palette_vtrgb(run):
    code, out, _ = run("theme", "palette", "--preset", "crimson-hud", "--format", "vtrgb")
    lines = out.splitlines()
    assert code == 0 and len(lines) == 3
    assert all(len(l.split(",")) == 16 for l in lines)
    assert [int(l.split(",")[6]) for l in lines] == [0x5e, 0xf2, 0xf2]  # color6 = the neon cyan
    code, out, _ = run("theme", "palette")
    assert "primary    #5ef2f2" in out
    code, _, err = run("theme", "palette", "--preset", "nope")
    assert code == 1 and "no theme named" in err


@needs_rsvg
def test_toolkit_cli(run, paths):
    code, out, _ = run("toolkit", "apply")
    assert code == 0 and "icons: regenerated" in out
    code, out, _ = run("toolkit", "apply")
    assert "icons: up to date" in out and "cursors: up to date" in out

import asyncio
import json
import os

import pytest

from nullgrid_dash import app as dash
from nullgrid_dash import gfx
from nullgrid_dash.stats import Sampler

CONSOLE_GLYPHS = set("─│┌┐└┘├┤┬┴┼█░▒■▲▼►◄◆·•›»↑↓ ")  # what the Terminus console font has


# -- gfx ----------------------------------------------------------------------
def test_bar():
    g = gfx.CONSOLE
    assert gfx.bar(0.5, 10, g) == "■■■■■·····"
    assert gfx.bar(2, 4, g) == "■■■■" and gfx.bar(-1, 4, g) == "····"
    assert gfx.bar(0.5, 0, g) == ""


def test_graph_shape_and_glyphs():
    # newest values on the right, left-padded; 3 glyph steps per row (░ ▒ █)
    rows = gfx.graph([0, 50, 100], width=5, height=3, top=100, g=gfx.CONSOLE)
    assert rows == ["    █",
                    "   ░█",
                    "   ██"]
    # any non-zero value shows up, even far below the scale
    assert gfx.graph([1], 1, 2, top=10**9, g=gfx.CONSOLE)[-1] != " "
    assert gfx.graph([], 0, 3, 1, gfx.CONSOLE) == []


def test_nice_top_and_formatting():
    assert gfx.nice_top(0) == 1
    assert gfx.nice_top(48_000) == 50 * 1024
    assert gfx.human_bytes(gfx.nice_top(48_000), rate=True) == "50K/s"
    assert gfx.human_bytes(3 * 1024**3) == "3G"
    assert gfx.human_bytes(1536) == "1.5K"
    assert gfx.human_bytes(512) == "512B"
    assert gfx.duration(3 * 86400 + 3600 * 5 + 61) == "3d 05:01"


# -- theme --------------------------------------------------------------------
def write_theme(home, name="toxic-grid", primary=2, refresh=1000):
    f = home / ".config" / "nullgrid" / "generated" / "theme.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"name": name, "refresh_ms": refresh,
                             "ansi": {"primary": primary, "secondary": 3},
                             "colors": {"terminal": {f"color{i}": "#10%02x20" % i for i in range(16)}}}))
    return f


def test_load_theme_and_fallback(isolated):
    ui = dash.load_theme(dash.theme_path())
    assert ui.slot("primary") == 6 and ui.name == "default"  # no theme.json yet
    write_theme(isolated)
    ui = dash.load_theme(dash.theme_path())
    assert ui.name == "toxic-grid" and ui.slot("primary") == 2 and ui.slot("dim") == 8
    assert ui.style("primary", bold=True) == "bold color(2)"
    t = dash.textual_theme(ui, "x")
    assert t.primary == "ansi_green" and t.secondary == "ansi_yellow" and t.ansi
    assert dash.console_palette(ui).startswith("\033]P0100020")


def test_launcher_only_lists_installed_apps(monkeypatch):
    monkeypatch.setattr(dash.shutil, "which", lambda c: c in ("nvim", "cava"))
    monkeypatch.setenv("TERM", "linux")
    entries = dash.launcher_entries()
    assert [(e.key, e.label) for e in entries] == [("1", "nvim"), ("2", "cava")]
    assert entries[1].argv[-1].endswith("cava/config-tty")  # console variant on a TTY


def test_sampler():
    s = Sampler().sample()
    assert s.cores and 0 <= s.cpu <= 100 and s.mem_total > 0 and s.disk_total > 0
    assert len(s.load) == 3


# -- app ------------------------------------------------------------------------
def run(coro):
    return asyncio.run(coro)


def test_dashboard_renders_and_restyles_live(isolated, monkeypatch):
    theme_file = write_theme(isolated, name="crimson-hud", primary=6)

    async def scenario():
        app = dash.Dashboard()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            text = "\n".join(str(w.render()) for w in app.query(dash.Panel))
            assert "TOTAL" in text and "RAM" in text and "DOWN" in text and "crimson-hud" in text
            assert app.theme.startswith("nullgrid-")
            # the theme engine rewrites theme.json -> the dashboard picks it up
            write_theme(isolated, name="ice-protocol", primary=4)
            os.utime(theme_file, (1, 1))
            app._clock()
            await pilot.pause()
            assert app.ui.name == "ice-protocol"
            assert app.get_theme(app.theme).primary == "ansi_blue"
            await pilot.press("q")
        return app

    app = run(scenario())
    assert app.return_code in (0, None)


def test_panels_fit_small_terminals(isolated, monkeypatch):
    monkeypatch.setenv("TERM", "linux")

    async def scenario():
        app = dash.Dashboard()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            for panel in app.query(dash.Panel):
                rendered = panel.render()
                width = panel.content_size.width
                assert all(len(line) <= width for line in rendered.plain.splitlines())
                assert set(rendered.plain) - {"\n"} <= CONSOLE_GLYPHS | set(
                    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789%./:-_()+")
            await pilot.press("q")

    run(scenario())


def test_launch_suspends_and_runs(isolated, monkeypatch):
    ran = []
    monkeypatch.setattr(dash, "launcher_entries",
                        lambda: [dash.Entry("1", "thing", "x", ["thing", "--flag"])])
    monkeypatch.setattr(dash.subprocess, "run", lambda argv, **kw: ran.append(argv))

    async def scenario():
        app = dash.Dashboard()
        monkeypatch.setattr(app, "suspend", _null_context)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press("1")
            await pilot.press("9")  # nothing bound there: ignored
            await pilot.press("q")

    run(scenario())
    assert ran == [["thing", "--flag"]]


class _null_context:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_check_mode(capsys):
    assert dash.main(["--check"]) == 0
    assert "DASH_OK" in capsys.readouterr().out

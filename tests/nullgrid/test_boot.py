"""The boot splash generator (plymouth/generate.py) and the greeter files (nullgrid-boot)."""
import importlib.util
import shutil
import sys
import tomllib

import pytest

from ngtest import REPO
from nullgrid import logo


@pytest.fixture(scope="module")
def gen():
    spec = importlib.util.spec_from_file_location("plymouth_generate", REPO / "plymouth/generate.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_hole_walks_between_neighbors_and_comes_home(gen):
    path = gen.hole_path()
    cells = [(int(p[0]), int(p[1])) for p in path]
    for (r1, c1), (r2, c2) in zip(cells, cells[1:]):
        assert abs(r1 - r2) + abs(c1 - c2) <= 1
    assert cells[-1] == logo.FULL.hole
    assert all(0 <= r < logo.FULL.cells and 0 <= c < logo.FULL.cells for r, c in cells)


def test_script_gets_every_image_it_names(gen):
    colors = gen.load_colors("crimson-hud")
    imgs = gen.images(colors)
    header = gen.script_header(colors, gen.hole_path())
    script = header + (REPO / "plymouth/nullgrid.script").read_text()
    # images loaded by literal name, by generated name lists, and by "logo-" + cell
    literal = set(__import__("re").findall(r'(?:scaled|Image)\("([a-z0-9-]+)(?:\.png)?"\)', script))
    named = set(__import__("re").findall(r'(?:log_names|cell_names)\[\d+\] = "([^"]+)";', header))
    wanted = literal | {n for n in named if n.startswith("log-")} | {f"logo-{n}" for n in named if n.isdigit()}
    wanted |= {f"tagline-{m}" for m in ("boot", "shutdown", "reboot", "update")}
    wanted.discard("tagline_name")
    assert wanted <= set(imgs), wanted - set(imgs)
    assert script.count("{") == script.count("}")


@pytest.mark.skipif(shutil.which("rsvg-convert") is None, reason="needs rsvg-convert")
def test_build_writes_the_theme(gen, tmp_path):
    gen.build(tmp_path, "crimson-hud")
    conf = (tmp_path / "nullgrid.plymouth").read_text()
    assert "ModuleName=script" in conf and "ScriptFile=/usr/share/plymouth/themes/nullgrid/nullgrid.script" in conf
    assert (tmp_path / "logo-22.png").read_bytes()[:4] == b"\x89PNG"
    assert len(list(tmp_path.glob("*.png"))) == len(gen.images(gen.load_colors("crimson-hud")))


def test_greeter_files():
    cfg = tomllib.loads((REPO / "config/greetd/tuigreet.toml").read_text())
    assert cfg["session"]["sessions_dirs"] == ["/usr/share/nullgrid/sessions"]
    assert cfg["background"]["kind"] == "matrix"
    greetd = tomllib.loads((REPO / "config/greetd/greetd.toml").read_text())
    assert greetd["default_session"]["command"] == "tuigreet" and greetd["terminal"]["vt"] == 1
    sessions = sorted((REPO / "config/greetd/sessions").glob("*.desktop"))
    execs = sorted(l.split("=", 1)[1] for f in sessions for l in f.read_text().splitlines() if l.startswith("Exec="))
    assert execs == ["nullgrid-login desktop", "nullgrid-login tty"]

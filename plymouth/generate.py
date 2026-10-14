#!/usr/bin/env python3
"""Build the NULLGRID Plymouth theme: "system boot" HUD with the lattice logo, a scanline, a
segmented progress bar and a scrolling fake boot log.

Plymouth's script plugin only shows images, so everything (text included) is drawn here as SVG
and rendered to PNG with rsvg-convert; the boot needs no fonts. nullgrid.script animates it.

  generate.py [--theme crimson-hud] [--out DIR]     (default out/plymouth/nullgrid)

Needs rsvg-convert (librsvg) and the fonts Orbitron and JetBrains Mono (nullgrid-fonts,
ttf-jetbrains-mono). Colors come from themes/<theme>.toml: the splash shows before any user is
logged in, so it uses one theme for the whole system.
"""
from __future__ import annotations

import argparse
import random
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "tools" / "nullgrid"))
from nullgrid import logo  # noqa: E402

# reference layout: 1920x1080, nullgrid.script scales to the screen
LOGO = 220
CELLS = logo.FULL.cells
LOG_LINES = [
    ("OK", "kernel handoff", "0x00F3"),
    ("OK", "memory lattice mapped", "16 / 16"),
    ("OK", "entropy pool seeded", "4096b"),
    ("OK", "mounting root grid", "/"),
    ("OK", "udev: device graph", "sync"),
    ("OK", "neural link daemon", "ready"),
    ("OK", "network uplink", "standby"),
    ("OK", "audio bus (pipewire)", "armed"),
    ("..", "dead pixel located", "[2,2]"),
    ("OK", "compositor handshake", "ok"),
    ("OK", "decrypting user space", "done"),
    ("OK", "hud overlay", "online"),
    ("OK", "sound pack neural-link", "loaded"),
    ("OK", "session manager", "waiting"),
]
SEGMENTS = 24
MONO = "JetBrains Mono"
DISPLAY = "Orbitron"


def load_colors(theme: str) -> dict:
    data = tomllib.loads((REPO / "themes" / f"{theme}.toml").read_text())
    return data["colors"]


def svg(width: float, height: float, body: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:g}" height="{height:g}" '
            f'viewBox="0 0 {width:g} {height:g}">{body}</svg>')


def text(x: float, y: float, s: str, *, size: float, fill: str, font: str = MONO, weight: int = 400,
         anchor: str = "start", spacing: float = 0, opacity: float = 1) -> str:
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (f'<text x="{x:g}" y="{y:g}" font-family="{font}" font-size="{size:g}" font-weight="{weight}" '
            f'fill="{fill}" fill-opacity="{opacity:g}" text-anchor="{anchor}" letter-spacing="{spacing:g}">'
            f'{s}</text>')


def images(c: dict) -> dict[str, str]:
    """name -> SVG, for every image the script uses."""
    out = {}
    # the mark, once per position of the dead pixel: the script moves the hole around
    for r in range(CELLS):
        for col in range(CELLS):
            out[f"logo-{r}{col}"] = logo.svg(c["primary"], c["secondary"], lattice=logo.Lattice(CELLS, (r, col)),
                                             size=LOGO)
    # wordmark: NULL in the primary accent, GRID in the second
    w, h = 560, 64
    out["wordmark"] = svg(w, h,
                          f'<text x="{w / 2:g}" y="48" font-family="{DISPLAY}" font-size="46" font-weight="700" '
                          f'text-anchor="middle" letter-spacing="14"><tspan fill="{c["primary"]}">NULL</tspan>'
                          f'<tspan fill="{c["secondary"]}">GRID</tspan></text>')
    for name, label in (("tagline-boot", "SYSTEM BOOT // ESTABLISHING GRID"),
                        ("tagline-shutdown", "SYSTEM HALT // RELEASING GRID"),
                        ("tagline-reboot", "SYSTEM REBOOT // CYCLING GRID"),
                        ("tagline-update", "SYSTEM UPDATE // DO NOT POWER OFF")):
        out[name] = svg(560, 24, text(280, 17, label, size=14, fill=c["dim"], anchor="middle", spacing=4))
    # progress segments
    out["seg-on"] = svg(14, 8, f'<rect width="14" height="8" fill="{c["primary"]}"/>')
    out["seg-off"] = svg(14, 8, f'<rect x="0.5" y="0.5" width="13" height="7" fill="none" '
                                f'stroke="{c["dim"]}" stroke-opacity="0.6"/>')
    # a HUD frame around the logo block: corner brackets with ticks
    fw, fh, k = 640, 470, 34
    lines = [f"M1 {k} L1 1 L{k} 1", f"M{fw - k} 1 L{fw - 1} 1 L{fw - 1} {k}",
             f"M1 {fh - k} L1 {fh - 1} L{k} {fh - 1}", f"M{fw - k} {fh - 1} L{fw - 1} {fh - 1} L{fw - 1} {fh - k}"]
    ticks = "".join(f'<rect x="{fw / 2 - 60 + i * 12:g}" y="0" width="6" height="3" fill="{c["primary"]}" '
                    f'fill-opacity="0.5"/>' for i in range(11))
    out["frame"] = svg(fw, fh, f'<path d="{" ".join(lines)}" fill="none" stroke="{c["primary"]}" '
                               f'stroke-width="2" stroke-opacity="0.7"/>{ticks}'
                       + text(12, fh - 12, "NG//BOOT", size=11, fill=c["dim"], spacing=2)
                       + text(fw - 12, fh - 12, "LAT 4x4 // HOLE MOBILE", size=11, fill=c["dim"],
                              anchor="end", spacing=2))
    # top-left ID strip with a barcode
    rng = random.Random("nullgrid-boot")
    x, bars = 0, []
    while x < 180:
        bw = rng.choice((1, 1, 2, 3))
        bars.append(f'<rect x="{x}" y="0" width="{bw}" height="26" fill="{c["text"]}" fill-opacity="0.75"/>')
        x += bw + rng.choice((1, 2, 2, 3))
    out["idstrip"] = svg(420, 30, "".join(bars) + text(196, 20, "NULLGRID OS // NODE-0", size=13,
                                                       fill=c["dim"], spacing=2))
    # boot log lines
    for i, (status, msg, value) in enumerate(LOG_LINES):
        ok = status == "OK"
        tag = c["primary"] if ok else c["warning"]
        body = (text(0, 16, "[", size=14, fill=c["dim"]) + text(26, 16, status, size=14, fill=tag, weight=700,
                                                                 anchor="middle")
                + text(44, 16, "]", size=14, fill=c["dim"])
                + text(66, 16, f"{msg.upper():<30}", size=14, fill=c["text"], opacity=0.8)
                + text(360, 16, value, size=14, fill=c["dim"]))
        out[f"log-{i:02d}"] = svg(460, 22, body)
    # the scanline: a soft bright band (stretched to the screen width)
    out["scanline"] = svg(64, 40,
                          f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
                          f'<stop offset="0" stop-color="{c["primary"]}" stop-opacity="0"/>'
                          f'<stop offset="0.85" stop-color="{c["primary"]}" stop-opacity="0.18"/>'
                          f'<stop offset="0.95" stop-color="{c["primary"]}" stop-opacity="0.55"/>'
                          f'<stop offset="1" stop-color="{c["primary"]}" stop-opacity="0"/></linearGradient></defs>'
                          f'<rect width="64" height="40" fill="url(#g)"/>')
    # password / question prompt
    pw, ph = 560, 120
    cut = 16
    shape = f"M{cut} 1 L{pw - 1} 1 L{pw - 1} {ph - cut} L{pw - cut} {ph - 1} L1 {ph - 1} L1 {cut} Z"
    out["prompt"] = svg(pw, ph, f'<path d="{shape}" fill="{c["surface"]}" fill-opacity="0.92" '
                                f'stroke="{c["secondary"]}" stroke-width="2"/>'
                        + text(pw / 2, 34, "AUTHENTICATION REQUIRED", size=16, fill=c["secondary"],
                               font=DISPLAY, weight=700, anchor="middle", spacing=4)
                        + f'<path d="M24 92 L{pw - 24} 92" stroke="{c["primary"]}" stroke-opacity="0.5"/>')
    out["bullet"] = svg(14, 14, f'<rect x="2" y="2" width="10" height="10" fill="{c["primary"]}"/>')
    return out


def script_header(c: dict, order: list[str]) -> str:
    """Values nullgrid.script needs: colors (0-1), image names and the path the hole walks.
    (Names are spelled out: the script language has no reliable number formatting.)"""
    lines = ["# --- generated by plymouth/generate.py ---"]
    for var, key in (("bg_top", "bg"), ("bg_bottom", "bg_alt"), ("text", "text")):
        h = c[key].lstrip("#")
        for ch, i in zip("rgb", (0, 2, 4)):
            lines.append(f"{var}_{ch} = {int(h[i:i + 2], 16) / 255:.3f};")
    lines += [f"log_count = {len(LOG_LINES)};", f"segments = {SEGMENTS};", f"hole_path_len = {len(order)};"]
    lines += [f'log_names[{i}] = "log-{i:02d}";' for i in range(len(LOG_LINES))]
    cells = [f"{r}{col}" for r in range(CELLS) for col in range(CELLS)]
    lines.append(f"cell_count = {len(cells)};")
    lines += [f'cell_names[{i}] = "{cell}";' for i, cell in enumerate(cells)]
    hr, hc = logo.FULL.hole
    lines.append(f'home_cell = "{hr}{hc}";')
    lines += [f'hole_path[{i}] = "{cell}";' for i, cell in enumerate(order)]
    return "\n".join(lines) + "\n# --- end of generated values ---\n\n"


def hole_path(seed: str = "dead-pixel", steps: int = 24) -> list[str]:
    """A walk of the dead pixel between neighboring cells, starting and ending at its home."""
    rng = random.Random(seed)
    home = logo.FULL.hole
    pos, path = home, []
    for _ in range(steps - 4):
        r, c = pos
        moves = [(r + dr, c + dc) for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0))
                 if 0 <= r + dr < CELLS and 0 <= c + dc < CELLS]
        pos = rng.choice(moves)
        path.append(pos)
    # walk home in a straight line, then rest there a moment
    while pos != home:
        r, c = pos
        pos = (r + (home[0] > r) - (home[0] < r), c) if r != home[0] else (r, c + (home[1] > c) - (home[1] < c))
        path.append(pos)
    path += [home] * 4
    return [f"{r}{c}" for r, c in path]


def render(svg_text: str, dest: Path) -> None:
    subprocess.run(["rsvg-convert", "-o", str(dest)], input=svg_text.encode(), check=True)


def build(out: Path, theme: str) -> None:
    if shutil.which("rsvg-convert") is None:
        sys.exit("rsvg-convert not found (package librsvg)")
    c = load_colors(theme)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.png"):
        old.unlink()
    for name, s in images(c).items():
        render(s, out / f"{name}.png")
    script = (HERE / "nullgrid.script").read_text()
    (out / "nullgrid.script").write_text(script_header(c, hole_path()) + script)
    (out / "nullgrid.plymouth").write_text(
        "[Plymouth Theme]\nName=NULLGRID\n"
        "Description=NULLGRID system boot: lattice logo with a wandering dead pixel, scanline, boot log\n"
        "ModuleName=script\n\n[script]\n"
        "ImageDir=/usr/share/plymouth/themes/nullgrid\n"
        "ScriptFile=/usr/share/plymouth/themes/nullgrid/nullgrid.script\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--theme", default="crimson-hud")
    ap.add_argument("--out", type=Path, default=REPO / "out" / "plymouth" / "nullgrid")
    args = ap.parse_args()
    build(args.out, args.theme)
    print(f"plymouth theme written to {args.out}")

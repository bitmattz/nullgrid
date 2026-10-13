"""The HUD wallpaper: a procedurally drawn SVG for any resolution, in the theme's colors.

Layers (bottom to top), switched by [decor] in nullgrid.toml:
  background gradient, dot grid, a faint lattice watermark      always
  matrix-style character columns                                decor.matrix_rain
  vignette                                                      always
  circuit traces along the edges with vias, corner brackets     decor.circuit_lines
  logo plate (top right)                                        always
  barcode/ID strip, data blocks, warning triangle, keymap       decor.data_text
  scanlines                                                     decor.scanlines

Its input is the spec the theme engine writes to ~/.config/nullgrid/generated/wallpaper.json
(template wallpaper.json.j2), so a theme change re-renders it. The layout keeps the important
parts clear of where the shell widgets go (dock left, bar bottom, HUD cluster bottom right).
Everything random comes from a seeded RNG: the same spec and size give the same picture.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

from . import logo
from .paths import Paths

GENERATOR_VERSION = 3  # bump when the drawing changes, so cached renders are redone

GLYPHS = "0123456789ABCDEF:./<>|=+*#"


def _f(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


DOCK_PX = 72  # the dock's width in pixels (shell/Dock.qml): text on the left starts after it


class Canvas:
    def __init__(self, width: int, height: int):
        self.w, self.h = width, height
        self.u = min(width / 1920, height / 1080)  # 1 unit = 1 px at 1920x1080
        self.left = max(52 * self.u, DOCK_PX + 20)  # x of the text blocks on the left
        self.parts: list[str] = []

    def add(self, s: str) -> None:
        self.parts.append(s)

    def text(self, x: float, y: float, s: str, *, size: float, fill: str, font: str,
             opacity: float = 1.0, anchor: str = "start", weight: str = "normal", spacing: float = 0) -> None:
        extra = f' letter-spacing="{_f(spacing)}"' if spacing else ""
        extra += f' text-anchor="{anchor}"' if anchor != "start" else ""
        extra += f' font-weight="{weight}"' if weight != "normal" else ""
        extra += f' fill-opacity="{_f(opacity)}"' if opacity < 1 else ""
        self.add(f'<text x="{_f(x)}" y="{_f(y)}" font-family="{font}" font-size="{_f(size)}" '
                 f'fill="{fill}"{extra}>{escape(s)}</text>')


def render(spec: dict, width: int, height: int) -> str:
    c = spec["colors"]
    decor = spec["decor"]
    def rng(layer: str) -> random.Random:
        """One generator per layer: switching a layer off doesn't move the others."""
        return random.Random(f"{spec.get('seed', 7)}:{width}x{height}:{layer}")

    cv = Canvas(width, height)
    u = cv.u
    attr = {"'": "&apos;", '"': "&quot;"}
    mono = escape(f"'{spec['fonts']['mono']}', monospace", attr)
    display = escape(f"'{spec['fonts']['display']}', sans-serif", attr)
    glow = spec.get("glow", 0.6)

    cv.add(f'<defs>'
           f'<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
           f'<stop offset="0" stop-color="{c["bg"]}"/><stop offset="1" stop-color="{c["bg_alt"]}"/></linearGradient>'
           f'<radialGradient id="haze" cx="0.62" cy="0.38" r="0.6">'
           f'<stop offset="0" stop-color="{c["primary"]}" stop-opacity="0.07"/>'
           f'<stop offset="1" stop-color="{c["primary"]}" stop-opacity="0"/></radialGradient>'
           f'<radialGradient id="vignette" cx="0.5" cy="0.5" r="0.75">'
           f'<stop offset="0.55" stop-color="#000" stop-opacity="0"/>'
           f'<stop offset="1" stop-color="#000" stop-opacity="0.5"/></radialGradient>'
           f'<pattern id="dots" width="{_f(32 * u)}" height="{_f(32 * u)}" patternUnits="userSpaceOnUse">'
           f'<circle cx="{_f(16 * u)}" cy="{_f(16 * u)}" r="{_f(max(0.6, 1.1 * u))}" fill="{c["primary"]}" '
           f'fill-opacity="0.11"/></pattern>'
           f'<pattern id="scan" width="4" height="3" patternUnits="userSpaceOnUse">'
           f'<rect width="4" height="1" fill="#000" fill-opacity="0.28"/></pattern>'
           f'<filter id="glow" x="-1" y="-1" width="3" height="3">'
           f'<feGaussianBlur stdDeviation="{_f(5 * u)}"/></filter>'
           f'</defs>')
    cv.add(f'<rect width="{width}" height="{height}" fill="url(#bg)"/>')
    cv.add(f'<rect width="{width}" height="{height}" fill="url(#haze)"/>')
    cv.add(f'<rect width="{width}" height="{height}" fill="url(#dots)"/>')
    _watermark(cv, c)
    if decor["matrix_rain"]:
        _matrix(cv, c, rng("matrix"), mono, _text_zones(cv, decor["data_text"], bool(spec.get("keymap"))))
    cv.add(f'<rect width="{width}" height="{height}" fill="url(#vignette)"/>')
    if decor["circuit_lines"]:
        _traces(cv, c, rng("traces"))
        _corners(cv, c)
    plate = _logo_plate(cv, spec, c, display, mono, glow)
    if decor["data_text"]:
        _barcode(cv, c, rng("barcode"), mono)
        _manifest(cv, spec, c, mono)
        _hexdump(cv, c, mono)
        if spec.get("keymap"):
            _keymap(cv, spec["keymap"], c, mono, plate)
    if decor["scanlines"]:
        cv.add(f'<rect width="{width}" height="{height}" fill="url(#scan)"/>')

    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">' + "".join(cv.parts) + "</svg>\n")


# --------------------------------------------------------------------------- layers
def _watermark(cv: Canvas, c: dict) -> None:
    """A large, very faint lattice behind the windows."""
    size = cv.h * 0.46
    x, y = (cv.w - size) / 2, (cv.h - size) / 2
    cv.add(f'<g opacity="0.045">{logo.svg_group(x, y, size, c["primary"], c["secondary"], stroke=2 * cv.u)}</g>')


def _text_zones(cv: Canvas, data_text: bool, keymap: bool) -> list[tuple[float, float, float, float]]:
    """Boxes (x0, y0, x1, y1) the matrix columns keep out of, so the text blocks stay readable."""
    u = cv.u
    plate_x = cv.w - 548 * u
    zones = [(plate_x - 20 * u, 20 * u, cv.w - 30 * u, 210 * u)]           # logo plate
    if data_text:
        zones += [(cv.left - 20 * u, 30 * u, cv.left + 280 * u, 420 * u),     # barcode + manifest
                  (cv.left, cv.h - 185 * u, cv.left + 330 * u, cv.h - 80 * u)]  # hex dump
        if keymap:
            zones.append((plate_x - 20 * u, 210 * u, plate_x + 380 * u, 460 * u))
    return zones


def _matrix(cv: Canvas, c: dict, rng: random.Random, font: str, keep_out: list) -> None:
    """Static character columns, brightest at the head (the falling end)."""
    u = cv.u
    step, line, size = 26 * u, 19 * u, 13 * u
    x = step / 2
    while x < cv.w:
        if rng.random() < 0.22:
            n = rng.randint(6, 26)
            top = rng.uniform(-0.2, 0.85) * cv.h
            color = c["secondary"] if rng.random() < 0.15 else c["primary"]
            for i in range(n):
                y = top + i * line
                if 0 < y < cv.h and not any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in keep_out):
                    head = i == n - 1
                    opacity = 0.45 if head else 0.04 + 0.2 * (i / n) ** 1.6
                    cv.text(x, y, rng.choice(GLYPHS), size=size, fill=c["text"] if head else color,
                            font=font, opacity=opacity, anchor="middle")
        x += step


def _edge_point(cv: Canvas, edge: str, a: float, b: float) -> tuple[float, float]:
    """(along the edge, inward from it) -> screen coordinates."""
    return {"top": (a, b), "bottom": (a, cv.h - b), "left": (b, a), "right": (cv.w - b, a)}[edge]


def _traces(cv: Canvas, c: dict, rng: random.Random) -> None:
    """Bundles of parallel traces that leave an edge, bend 45 degrees and end in vias."""
    u = cv.u
    # (edge, position along it as a fraction, traces, direction of the bend, color, depth range)
    bundles = [
        ("top", 0.30, 4, 1, "primary", (34, 70)), ("top", 0.56, 3, -1, "primary", (34, 70)),
        ("left", 0.12, 3, 1, "primary", (8, 12)),  # hugs the edge, left of the data blocks
        ("left", 0.86, 4, -1, "secondary", (34, 70)),
        ("right", 0.46, 5, 1, "primary", (34, 70)), ("right", 0.36, 2, -1, "secondary", (34, 70)),
        ("bottom", 0.24, 3, 1, "primary", (34, 70)), ("bottom", 0.60, 4, -1, "primary", (34, 70)),
    ]
    s, k = 11 * u, 26 * u  # spacing between traces, length of the 45-degree leg
    for edge, frac, n, d, role, (dmin, dmax) in bundles:
        span = cv.w if edge in ("top", "bottom") else cv.h
        a0 = (frac + rng.uniform(-0.03, 0.03)) * span
        depth = rng.uniform(dmin, dmax) * u
        run = rng.uniform(140, 260) * u
        color = c[role]
        opacity = 0.5 if role == "secondary" else 0.34
        paths, vias = [], []
        for i in range(n):
            a = a0 + i * s
            b = depth + ((n - 1 - i) if d > 0 else i) * s  # outer traces turn later: no crossings
            end = a + d * (k + run - rng.uniform(0, 3) * s)
            pts = [(a, -2), (a, b - k), (a + d * k, b), (end, b)]
            if rng.random() < 0.4:  # some traces dive back toward the edge
                pts.append((end + d * k * 0.6, b - k * 0.6))
            xy = [_edge_point(cv, edge, pa, pb) for pa, pb in pts]
            paths.append("M" + " L".join(f"{_f(x)} {_f(y)}" for x, y in xy))
            vias.append(xy[-1])
        cv.add(f'<path d="{" ".join(paths)}" fill="none" stroke="{color}" stroke-opacity="{opacity}" '
               f'stroke-width="{_f(1.6 * u)}" stroke-linejoin="miter"/>')
        cv.add("".join(f'<circle cx="{_f(x)}" cy="{_f(y)}" r="{_f(3.4 * u)}" fill="{c["bg"]}" stroke="{color}" '
                       f'stroke-opacity="{_f(opacity + 0.25)}" stroke-width="{_f(1.6 * u)}"/>' for x, y in vias))


def _corners(cv: Canvas, c: dict) -> None:
    """Chamfered brackets in the screen corners."""
    u = cv.u
    m, L, ch = 16 * u, 64 * u, 10 * u
    paths = []
    for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        ox = m if sx > 0 else cv.w - m
        oy = m if sy > 0 else cv.h - m
        p = [(ox, oy + sy * L), (ox, oy + sy * ch), (ox + sx * ch, oy), (ox + sx * L, oy)]
        paths.append("M" + " L".join(f"{_f(x)} {_f(y)}" for x, y in p))
    cv.add(f'<path d="{" ".join(paths)}" fill="none" stroke="{c["primary"]}" stroke-opacity="0.55" '
           f'stroke-width="{_f(2 * u)}"/>')


def _chamfer(x: float, y: float, w: float, h: float, cut: float) -> str:
    """Rectangle with the top-left and bottom-right corners cut at 45 degrees."""
    p = [(x + cut, y), (x + w, y), (x + w, y + h - cut), (x + w - cut, y + h), (x, y + h), (x, y + cut)]
    return "M" + " L".join(f"{_f(px)} {_f(py)}" for px, py in p) + " Z"


def _logo_plate(cv: Canvas, spec: dict, c: dict, display: str, mono: str, glow: float) -> tuple[float, float, float, float]:
    """The OS name plate, top right. Returns its box."""
    u = cv.u
    w, h = 500 * u, 136 * u
    x, y = cv.w - w - 48 * u, 48 * u
    cut = 20 * u
    shape = _chamfer(x, y, w, h, cut)
    if glow > 0:
        cv.add(f'<path d="{shape}" fill="none" stroke="{c["glow"]}" stroke-width="{_f(6 * u)}" '
               f'stroke-opacity="{_f(0.5 * glow)}" filter="url(#glow)"/>')
    cv.add(f'<path d="{shape}" fill="{c["surface"]}" fill-opacity="{_f(spec.get("surface_opacity", 0.85))}" '
           f'stroke="{c["primary"]}" stroke-opacity="0.85" stroke-width="{_f(1.6 * u)}"/>')
    # accent bar and ticks under the plate
    cv.add(f'<rect x="{_f(x)}" y="{_f(y + h + 8 * u)}" width="{_f(130 * u)}" height="{_f(4 * u)}" fill="{c["secondary"]}"/>')
    ticks = "".join(f'<rect x="{_f(x + 150 * u + i * 14 * u)}" y="{_f(y + h + 8 * u)}" width="{_f(6 * u)}" '
                    f'height="{_f(4 * u)}"/>' for i in range(10))
    cv.add(f'<g fill="{c["primary"]}" fill-opacity="0.5">{ticks}</g>')
    mark = 92 * u
    cv.add(logo.svg_group(x + 26 * u, y + (h - mark) / 2, mark, c["primary"], c["secondary"],
                          glow=glow, glow_filter="glow"))
    tx = x + 148 * u
    cv.add(f'<text x="{_f(tx)}" y="{_f(y + 72 * u)}" font-family="{display}" font-size="{_f(44 * u)}" '
           f'font-weight="bold" letter-spacing="{_f(3 * u)}">'
           f'<tspan fill="{c["primary"]}">NULL</tspan><tspan fill="{c["secondary"]}">GRID</tspan></text>')
    cv.text(tx + 2 * u, y + 100 * u, f"OPERATING SYSTEM // v{spec.get('version', '')}", size=13 * u,
            fill=c["dim"], font=mono, spacing=1.5 * u)
    cv.text(tx + 2 * u, y + 118 * u, f"THEME :: {spec['theme'].upper()}", size=13 * u,
            fill=c["primary"], font=mono, opacity=0.8, spacing=1.5 * u)
    cv.text(x + w, y - 12 * u, "NG-UNIT 04 // SECTOR 7F // NODE 2.2", size=11 * u, fill=c["dim"],
            font=mono, anchor="end", spacing=1.5 * u)
    return x, y, w, h


def _barcode(cv: Canvas, c: dict, rng: random.Random, font: str) -> None:
    u = cv.u
    x0, y0, h = cv.left, 48 * u, 36 * u
    x, bars = x0, []
    while x < x0 + 230 * u:
        bw = rng.choice((1, 1, 2, 3)) * 1.6 * u
        bars.append(f'<rect x="{_f(x)}" y="{_f(y0)}" width="{_f(bw)}" height="{_f(h)}"/>')
        x += bw + rng.choice((1, 2, 2, 3)) * 1.6 * u
    cv.add(f'<g fill="{c["text"]}" fill-opacity="0.8">{"".join(bars)}</g>')
    cv.add(f'<rect x="{_f(x + 10 * u)}" y="{_f(y0)}" width="{_f(5 * u)}" height="{_f(h)}" fill="{c["secondary"]}"/>')
    cv.text(x0, y0 + h + 20 * u, "ID NG-7F3A-0C11-2.2", size=14 * u, fill=c["primary"], font=font,
            spacing=2 * u)
    cv.text(x0, y0 + h + 38 * u, "CLEARANCE: NULL  //  AUTH: GRID-4", size=11 * u, fill=c["dim"],
            font=font, spacing=1.2 * u)


def _rows(cv: Canvas, x: float, y: float, title: str, rows: list[tuple[str, str]], c: dict, font: str,
          *, key_width: float, key_color: str) -> float:
    """A titled two-column text block. Returns the y below it."""
    u = cv.u
    cv.text(x, y, title, size=12 * u, fill=c["primary"], font=font, spacing=2 * u)
    cv.add(f'<rect x="{_f(x)}" y="{_f(y + 7 * u)}" width="{_f(24 * u)}" height="{_f(2 * u)}" fill="{c["secondary"]}"/>')
    cv.add(f'<rect x="{_f(x + 28 * u)}" y="{_f(y + 7.5 * u)}" width="{_f(key_width + 120 * u)}" '
           f'height="{_f(1 * u)}" fill="{c["dim"]}" fill-opacity="0.5"/>')
    y += 28 * u
    for key, value in rows:
        cv.text(x, y, key, size=12 * u, fill=key_color, font=font, opacity=0.9)
        cv.text(x + key_width, y, value, size=12 * u, fill=c["dim"], font=font)
        y += 18 * u
    return y


def _manifest(cv: Canvas, spec: dict, c: dict, font: str) -> None:
    u = cv.u
    x = cv.left
    rows = [("KERNEL", "LINUX"), ("SESSION", "WAYLAND"), ("SHELL", "ZSH"),
            ("THEME", spec["theme"].upper()), ("LATTICE", "4x4 / HOLE 2.2"), ("UPLINK", "STABLE")]
    y = _rows(cv, x, 190 * u, "// SYS.MANIFEST", [(k.ljust(10, "."), v) for k, v in rows], c, font,
              key_width=100 * u, key_color=c["dim"])
    # warning triangle
    ty, s = y + 14 * u, 26 * u
    tri = f"M{_f(x + s / 2)} {_f(ty)} L{_f(x + s)} {_f(ty + s * 0.87)} L{_f(x)} {_f(ty + s * 0.87)} Z"
    cv.add(f'<path d="{tri}" fill="none" stroke="{c["warning"]}" stroke-width="{_f(2 * u)}" stroke-linejoin="miter"/>')
    cv.text(x + s / 2, ty + s * 0.78, "!", size=15 * u, fill=c["warning"], font=font, anchor="middle", weight="bold")
    cv.text(x + s + 12 * u, ty + 12 * u, "CAUTION", size=12 * u, fill=c["warning"], font=font, spacing=2 * u)
    cv.text(x + s + 12 * u, ty + 27 * u, "DEAD PIXEL IN SECTOR 2.2", size=11 * u, fill=c["dim"], font=font,
            spacing=1 * u)


def _hexdump(cv: Canvas, c: dict, font: str) -> None:
    """A few lines of 'memory', bottom left, above the bar and right of the dock."""
    u = cv.u
    word = "NULLGRID"
    lines = []
    for i in range(5):
        data = word[i:] + word[:i]
        lines.append(f"0x7F3A{i * 8:02X}  " + " ".join(f"{ord(ch):02X}" for ch in data) + f"  {data}")
    y = cv.h - 160 * u
    for i, line in enumerate(lines):
        cv.text(cv.left + 30 * u, y + i * 16 * u, line, size=11 * u, fill=c["primary"] if i == 0 else c["dim"],
                font=font, opacity=0.75)


def _keymap(cv: Canvas, keymap: list, c: dict, font: str, plate: tuple) -> None:
    """The main keybinds under the logo plate, so a new user sees where to start."""
    u = cv.u
    x, y, w, h = plate
    rows = [(k, v.upper()) for k, v in keymap[:12]]
    _rows(cv, x, y + h + 56 * u, "// KEYMAP", rows, c, font, key_width=190 * u, key_color=c["text"])


# --------------------------------------------------------------------------- screens
class WallpaperError(Exception):
    pass


@dataclass(frozen=True)
class Output:
    name: str      # compositor output name, "*" = all
    width: int     # pixels, as the output is shown (rotation applied)
    height: int


DEFAULT_OUTPUT = Output("*", 1920, 1080)


def _json_cmd(argv: list[str]) -> list | None:
    if shutil.which(argv[0]) is None:
        return None
    try:
        out = subprocess.run(argv, capture_output=True, text=True, timeout=10)
        return json.loads(out.stdout) if out.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def outputs() -> list[Output]:
    """The connected screens of the running Hyprland or Sway session (empty if neither)."""
    found = []
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        for m in _json_cmd(["hyprctl", "monitors", "-j"]) or []:
            w, h = m["width"], m["height"]
            found.append(Output(m["name"], *((h, w) if m.get("transform", 0) % 2 else (w, h))))
    elif os.environ.get("SWAYSOCK"):
        for o in _json_cmd(["swaymsg", "-t", "get_outputs", "-r"]) or []:
            mode = o.get("current_mode") or {}
            if o.get("active") and mode:
                w, h = mode["width"], mode["height"]
                turned = o.get("transform", "normal").removeprefix("flipped-").lstrip("-") in ("90", "270")
                found.append(Output(o["name"], *((h, w) if turned else (w, h))))
    return found


# --------------------------------------------------------------------------- files
def load_spec(paths: Paths) -> dict:
    f = paths.config_dir / "generated" / "wallpaper.json"
    try:
        return json.loads(f.read_text())
    except FileNotFoundError:
        raise WallpaperError(f"{f} is missing; run: nullgrid theme reload") from None
    except ValueError as exc:
        raise WallpaperError(f"{f}: not valid JSON: {exc}") from None


def to_png(svg: str, dest: Path) -> None:
    if shutil.which("rsvg-convert") is None:
        raise WallpaperError("rsvg-convert not found (package librsvg)")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".{dest.name}.{os.getpid()}.png")
    try:
        subprocess.run(["rsvg-convert", "-o", str(tmp)], input=svg.encode(), check=True,
                       capture_output=True, timeout=120)
        os.replace(tmp, dest)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise WallpaperError(f"rsvg-convert failed: {getattr(exc, 'stderr', b'').decode().strip() or exc}") from None
    finally:
        tmp.unlink(missing_ok=True)


def cached_png(paths: Paths, spec: dict, width: int, height: int) -> Path:
    """The wallpaper for this spec and size, rendered once and then reused."""
    key = hashlib.sha256(json.dumps([GENERATOR_VERSION, spec, width, height], sort_keys=True).encode())
    path = paths.cache_dir / "wallpaper" / f"{key.hexdigest()[:16]}-{width}x{height}.png"
    if not path.is_file():
        to_png(render(spec, width, height), path)
    return path


def prune(paths: Paths, keep: int = 12) -> None:
    current = paths.cache_dir / "wallpaper" / "current.png"
    keep_too = current.resolve() if current.is_symlink() else None
    files = sorted((p for p in (paths.cache_dir / "wallpaper").glob("*.png")
                    if not p.is_symlink() and p != keep_too), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[keep:]:
        old.unlink(missing_ok=True)


# --------------------------------------------------------------------------- swaybg
def _state_file(paths: Paths) -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    base = Path(runtime) if runtime else paths.cache_dir
    return base / f"nullgrid-swaybg-{os.environ.get('WAYLAND_DISPLAY', 'wayland')}.json"


def _alive(pid: int) -> bool:
    """A running swaybg (not a zombie that nobody reaped yet)."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return False
    name, _, rest = stat.partition(" (")[2].rpartition(") ")
    return name == "swaybg" and not rest.startswith(("Z", "X"))


def apply(paths: Paths) -> list[tuple[Output, Path]]:
    """Render the wallpaper for every screen and show it with swaybg (replacing ours, if running)."""
    if not os.environ.get("WAYLAND_DISPLAY"):
        raise WallpaperError("not in a Wayland session (WAYLAND_DISPLAY is unset)")
    if shutil.which("swaybg") is None:
        raise WallpaperError("swaybg not found")
    spec = load_spec(paths)
    shown = [(o, cached_png(paths, spec, o.width, o.height)) for o in outputs() or [DEFAULT_OUTPUT]]
    argv = ["swaybg"]
    for o, png in shown:
        argv += ["-o", o.name, "-i", str(png), "-m", "fill"]

    state_file = _state_file(paths)
    try:
        old = json.loads(state_file.read_text())
    except (OSError, ValueError):
        old = {}
    _link_current(paths, shown[0][1])
    if old.get("argv") == argv and _alive(old.get("pid", 0)):
        return shown
    proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps({"pid": proc.pid, "argv": argv}))
    if _alive(old.get("pid", 0)):
        time.sleep(0.4)  # let the new one draw first: no flash of bare background
        os.kill(old["pid"], signal.SIGTERM)
    prune(paths)
    return shown


def _link_current(paths: Paths, png: Path) -> None:
    """~/.cache/nullgrid/wallpaper/current.png -> the first screen's wallpaper (the lock screen uses it)."""
    link = paths.cache_dir / "wallpaper" / "current.png"
    link.parent.mkdir(parents=True, exist_ok=True)
    tmp = link.with_name(".current.png.tmp")
    tmp.unlink(missing_ok=True)
    tmp.symlink_to(png.name)
    os.replace(tmp, link)

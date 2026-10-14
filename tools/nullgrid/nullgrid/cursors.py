"""The NULLGRID cursors: angular shapes in the theme's colors, written as an Xcursor theme.

Each cursor is drawn as SVG on a 32x32 canvas: a dark body with a neon outline, and a dark halo
so it reads on light backgrounds too. All cursors of one size go into one sprite sheet, which
rsvg-convert renders in a single call; the PNG is decoded here and cut into Xcursor files
(pure Python, no xcursorgen needed). The busy cursors are animated.

Rendered themes are cached per palette in ~/.cache/nullgrid/cursors/<stamp>/, so switching back
to a theme used before is instant. icons.py's theme directory links its cursors/ there.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import struct
import subprocess
import zlib
from dataclasses import dataclass, field
from pathlib import Path

from .glyphs import GLYPHS

GENERATOR_VERSION = 1  # bump when the drawing changes
SIZES = (24, 32, 48)
CANVAS = 32
FRAMES = 8              # frames of the animated cursors
FRAME_MS = 70


class CursorError(Exception):
    pass


@dataclass
class Cursor:
    name: str
    hotspot: tuple[float, float]           # on the 32x32 canvas
    draw: object                           # (colors, frame) -> svg fragment
    aliases: list[str] = field(default_factory=list)
    animated: bool = False


# --------------------------------------------------------------------------- drawing helpers
ARROW = "M4 3 L4 24 L9.5 18.6 L13.5 27.5 L17 26 L13 17 L20.5 17 Z"


def _shape(d: str, c: dict, *, fill: str | None = None, line: str | None = None, width: float = 1.4) -> str:
    """A closed shape: dark halo, body fill, neon outline."""
    return (f'<path d="{d}" fill="none" stroke="{c["halo"]}" stroke-width="{width + 2.4}" stroke-linejoin="miter"/>'
            f'<path d="{d}" fill="{fill or c["body"]}" stroke="{line or c["primary"]}" stroke-width="{width}" '
            f'stroke-linejoin="miter"/>')


def _lines(d: str, c: dict, *, color: str | None = None, width: float = 1.8) -> str:
    """Open strokes with a dark halo."""
    return (f'<path d="{d}" fill="none" stroke="{c["halo"]}" stroke-width="{width + 2.4}" stroke-linecap="square" '
            f'stroke-linejoin="miter"/>'
            f'<path d="{d}" fill="none" stroke="{color or c["primary"]}" stroke-width="{width}" '
            f'stroke-linecap="square" stroke-linejoin="miter"/>')


def _badge(glyph: str, c: dict) -> str:
    """A small chamfered plate at the lower right with a glyph (copy, alias, help, menu)."""
    plate = "M19 18 L28 18 L30 20 L30 29 L28 31 L19 31 L17 29 L17 20 Z"
    g = GLYPHS[glyph]
    return (_shape(plate, c, width=1.2) +
            f'<path transform="translate(18.5 19.5) scale(0.42)" d="{g}" fill="none" stroke="{c["secondary"]}" '
            f'stroke-width="2.6" stroke-linecap="square"/>')


def _spinner(cx: float, cy: float, r: float, frame: int, c: dict, width: float = 2.2) -> str:
    """Four ring segments, turned a little further each frame (one quarter turn per cycle)."""
    angle = frame * 90 / FRAMES
    circ = 2 * math.pi * r
    dash = circ / 4
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{c["body"]}" stroke="{c["halo"]}" stroke-width="{width + 2.4}"/>'
            f'<g transform="rotate({angle:.2f} {cx} {cy})">'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{c["primary"]}" stroke-width="{width}" '
            f'stroke-dasharray="{dash * 0.6:.2f} {dash * 0.4:.2f}"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{c["secondary"]}" stroke-width="{width}" '
            f'stroke-dasharray="{dash * 0.6:.2f} {circ - dash * 0.6:.2f}"/></g>')


def _double_arrow(c: dict, angle: float) -> str:
    d = "M4 16 L28 16 M9 11 L4 16 L9 21 M23 11 L28 16 L23 21"
    return f'<g transform="rotate({angle} 16 16)">{_lines(d, c)}</g>'


def _bars(c: dict, angle: float) -> str:
    d = "M13 7 L13 25 M19 7 L19 25 M4 16 L9 16 M7 13 L4 16 L7 19 M23 16 L28 16 M25 13 L28 16 L25 19"
    return f'<g transform="rotate({angle} 16 16)">{_lines(d, c, width=1.6)}</g>'


def _ibeam(c: dict, angle: float = 0) -> str:
    d = "M11 4 L14 4 L16 6 L18 4 L21 4 M16 6 L16 26 M11 28 L14 28 L16 26 L18 28 L21 28"
    return f'<g transform="rotate({angle} 16 16)">{_lines(d, c, width=1.6)}</g>'


def _magnifier(c: dict, sign: str) -> str:
    d = "M13 6 A7 7 0 1 1 12.99 6 M18.5 18.5 L27 27 M10 13 L16 13" + (" M13 10 L13 16" if sign == "+" else "")
    return _lines(d, c)


def _hand(c: dict, closed: bool) -> str:
    if closed:
        d = "M8 13 L11 11 L14 12 L17 11 L20 12 L23 12 L25 14 L25 22 L21 28 L12 28 L7 22 Z"
        return _shape(d, c) + _lines("M14 12 L14 15 M17 11 L17 15 M20 12 L20 15", c, width=1.1)
    d = ("M11 5 L13 3 L15 5 L15 13 L17 12 L19 13 L19 14 L21 13 L23 14.5 L23 15.5 L25 15 L26 17 L26 22 "
         "L22 28 L12 28 L6 21 L6 17 L8 16 L11 18.5 Z")
    return _shape(d, c) + _lines("M15 13 L15 17 M19 14 L19 17 M23 15.5 L23 18", c, width=1.1)


# --------------------------------------------------------------------------- the set
def _set() -> list[Cursor]:
    arrow = lambda c, f: _shape(ARROW, c)  # noqa: E731
    return [
        Cursor("default", (4, 3), arrow, ["left_ptr", "arrow", "top_left_arrow", "left_arrow", "right_ptr",
                                          "draft_large", "draft_small"]),
        Cursor("pointer", (13, 3), lambda c, f: _hand(c, False),
               ["hand", "hand1", "hand2", "pointing_hand", "e29285e634086352946a0e7090d73106",
                "9d800788f1b08800ae810202380a0822"]),
        Cursor("text", (16, 16), lambda c, f: _ibeam(c), ["xterm", "ibeam"]),
        Cursor("vertical-text", (16, 16), lambda c, f: _ibeam(c, 90), []),
        Cursor("crosshair", (16, 16), lambda c, f: _lines(
            "M16 3 L16 12 M16 20 L16 29 M3 16 L12 16 M20 16 L29 16", c) + _shape("M15 15 L17 15 L17 17 L15 17 Z", c, fill=c["secondary"], line=c["secondary"], width=0.6),
               ["cross", "tcross", "cross_reverse", "diamond_cross", "target", "color-picker"]),
        Cursor("wait", (16, 16), lambda c, f: _spinner(16, 16, 10, f, c, 2.6), ["watch"], animated=True),
        Cursor("progress", (4, 3), lambda c, f: _shape(ARROW, c) + _spinner(24, 24, 5.5, f, c, 2),
               ["left_ptr_watch", "half-busy", "08e8e1c95fe2fc01f976f1e063a24ccd",
                "3ecb610c1bf2410f44200f48c40d3599"], animated=True),
        Cursor("not-allowed", (16, 16), lambda c, f: _lines(
            "M16 6 A10 10 0 1 1 15.99 6 M9 9 L23 23", c, color=c["secondary"], width=2.4),
               ["no-drop", "dnd-none", "dnd-no-drop", "crossed_circle", "forbidden", "circle", "X_cursor",
                "pirate", "03b6e0fcb3499374a867c041f52298f0"]),
        Cursor("help", (4, 3), lambda c, f: _shape(ARROW, c) + _badge("unknown", c),
               ["question_arrow", "whats_this", "left_ptr_help", "5c6cd98b3f3ebcb1f9c7f1c204630408",
                "d9ce0ab605698f320427677b458ad60b"]),
        Cursor("context-menu", (4, 3), lambda c, f: _shape(ARROW, c) + _badge("text", c), []),
        Cursor("copy", (4, 3), lambda c, f: _shape(ARROW, c) + _badge("download", c),
               ["dnd-copy", "1081e37283d90000800003c07f3ef6bf", "6407b0e94181790501fd1e167b474872"]),
        Cursor("alias", (4, 3), lambda c, f: _shape(ARROW, c) + _badge("share", c),
               ["link", "dnd-link", "3085a0e285430894940527032f8b26df", "640fb0e74195791501fd1ed57b41487f"]),
        Cursor("move", (16, 16), lambda c, f: _lines(
            "M16 4 L16 28 M4 16 L28 16 M12 8 L16 4 L20 8 M12 24 L16 28 L20 24 M8 12 L4 16 L8 20 M24 12 L28 16 L24 20", c),
               ["fleur", "all-scroll", "size_all", "dnd-move", "grabbing_move", "4498f0e0c1937ffe01fd06f973665830",
                "9081237383d90e509aa00f00170e968f"]),
        Cursor("grab", (16, 16), lambda c, f: _hand(c, False), ["openhand"]),
        Cursor("grabbing", (16, 16), lambda c, f: _hand(c, True), ["closedhand", "dnd-none-grab"]),
        Cursor("ew-resize", (16, 16), lambda c, f: _double_arrow(c, 0),
               ["e-resize", "w-resize", "sb_h_double_arrow", "h_double_arrow", "size_hor", "right_side", "left_side",
                "028006030e0e7ebffc7f7070c0600140"]),
        Cursor("ns-resize", (16, 16), lambda c, f: _double_arrow(c, 90),
               ["n-resize", "s-resize", "sb_v_double_arrow", "v_double_arrow", "size_ver", "top_side",
                "bottom_side", "00008160000006810000408080010102"]),
        Cursor("nwse-resize", (16, 16), lambda c, f: _double_arrow(c, 45),
               ["nw-resize", "se-resize", "size_fdiag", "bd_double_arrow", "top_left_corner", "bottom_right_corner",
                "c7088f0f3e6c8088236ef8e1e3e70000"]),
        Cursor("nesw-resize", (16, 16), lambda c, f: _double_arrow(c, -45),
               ["ne-resize", "sw-resize", "size_bdiag", "fd_double_arrow", "top_right_corner", "bottom_left_corner",
                "fcf1c3c7cd4491d801f1e1c78f100000"]),
        Cursor("col-resize", (16, 16), lambda c, f: _bars(c, 0), ["split_h", "sb_h_double_arrow_split"]),
        Cursor("row-resize", (16, 16), lambda c, f: _bars(c, 90), ["split_v"]),
        Cursor("cell", (16, 16), lambda c, f: _lines("M16 6 L16 26 M6 16 L26 16", c, width=3), ["plus"]),
        Cursor("zoom-in", (13, 13), lambda c, f: _magnifier(c, "+"), []),
        Cursor("zoom-out", (13, 13), lambda c, f: _magnifier(c, "-"), []),
        Cursor("pencil", (4, 28), lambda c, f: _shape("M4 28 L6 21 L21 6 L26 11 L11 26 Z", c) +
               _lines("M18 9 L23 14", c, color=c["secondary"], width=1.2), ["draft"]),
    ]


CURSORS = _set()


def colors_of(spec: dict) -> dict:
    col = spec["colors"]
    return {"body": col["bg"], "halo": col["bg"], "primary": col["primary"], "secondary": col["secondary"]}


def stamp(spec: dict, sizes: tuple[int, ...]) -> str:
    data = json.dumps({"v": GENERATOR_VERSION, "c": colors_of(spec), "s": sorted(sizes)}, sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()[:16]


# --------------------------------------------------------------------------- rendering
def _cells() -> list[tuple[Cursor, int]]:
    return [(cur, f) for cur in CURSORS for f in range(FRAMES if cur.animated else 1)]


def sprite_svg(c: dict, size: int) -> str:
    """Every frame of every cursor side by side, size px each."""
    cells = _cells()
    scale = size / CANVAS
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{size * len(cells)}" height="{size}">']
    for i, (cur, frame) in enumerate(cells):
        parts.append(f'<g transform="translate({i * size} 0) scale({scale:.5f})">{cur.draw(c, frame)}</g>')
    parts.append("</svg>")
    return "".join(parts)


def _render_png(svg: str) -> bytes:
    if shutil.which("rsvg-convert") is None:
        raise CursorError("rsvg-convert not found (package librsvg)")
    try:
        return subprocess.run(["rsvg-convert"], input=svg.encode(), capture_output=True, check=True,
                              timeout=60).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise CursorError(f"rsvg-convert failed: {getattr(exc, 'stderr', b'') or exc}") from None


def decode_png(data: bytes) -> tuple[int, int, bytearray]:
    """(width, height, RGBA bytes) of an 8-bit RGBA, non-interlaced PNG (what rsvg-convert writes)."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise CursorError("not a PNG")
    pos, idat, width = 8, [], 0
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            width, height, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", chunk)
            if (depth, ctype, interlace) != (8, 6, 0):
                raise CursorError(f"unsupported PNG (depth {depth}, color type {ctype}, interlace {interlace})")
        elif kind == b"IDAT":
            idat.append(chunk)
        elif kind == b"IEND":
            break
        pos += 12 + length
    raw = zlib.decompress(b"".join(idat))
    stride = width * 4
    out = bytearray(stride * height)
    prev = bytearray(stride)
    for y in range(height):
        ftype = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        if ftype == 1:
            for i in range(4, stride):
                line[i] = (line[i] + line[i - 4]) & 0xFF
        elif ftype == 2:
            line = bytearray((a + b) & 0xFF for a, b in zip(line, prev))
        elif ftype == 3:
            for i in range(stride):
                left = line[i - 4] if i >= 4 else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:
            for i in range(stride):
                a = line[i - 4] if i >= 4 else 0
                b = prev[i]
                cc = prev[i - 4] if i >= 4 else 0
                p = a + b - cc
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - cc)
                pred = a if pa <= pb and pa <= pc else (b if pb <= pc else cc)
                line[i] = (line[i] + pred) & 0xFF
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return width, height, out


def _argb(rgba: bytearray, sheet_w: int, x0: int, size: int) -> bytes:
    """A size x size cell of the sheet as premultiplied ARGB, little-endian (Xcursor's pixels)."""
    px = bytearray()
    for y in range(size):
        row = rgba[(y * sheet_w + x0) * 4:(y * sheet_w + x0 + size) * 4]
        for i in range(0, len(row), 4):
            r, g, b, a = row[i], row[i + 1], row[i + 2], row[i + 3]
            # cairo's PNGs are straight alpha; Xcursor wants premultiplied
            px += bytes(((b * a + 127) // 255, (g * a + 127) // 255, (r * a + 127) // 255, a))
    return bytes(px)


def xcursor(images: list[tuple[int, int, int, int, int, bytes]]) -> bytes:
    """An Xcursor file. images: (nominal size, width, xhot, yhot, delay ms, ARGB pixels), square."""
    header = struct.pack("<4sIII", b"Xcur", 16, 0x10000, len(images))
    toc, chunks = b"", b""
    offset = 16 + 12 * len(images)
    for nominal, width, xhot, yhot, delay, pixels in images:
        chunk = struct.pack("<IIIIIIIII", 36, 0xFFFD0002, nominal, 1, width, width, xhot, yhot, delay) + pixels
        toc += struct.pack("<III", 0xFFFD0002, nominal, offset + len(chunks))
        chunks += chunk
    return header + toc + chunks


def read_xcursor(data: bytes) -> list[dict]:
    """The images in an Xcursor file (for tests and `nullgrid doctor`)."""
    magic, hsize, _, ntoc = struct.unpack("<4sIII", data[:16])
    if magic != b"Xcur":
        raise CursorError("not an Xcursor file")
    out = []
    for i in range(ntoc):
        kind, sub, pos = struct.unpack("<III", data[hsize + 12 * i:hsize + 12 * (i + 1)])
        if kind != 0xFFFD0002:
            continue
        _, _, nominal, _, w, h, xh, yh, delay = struct.unpack("<IIIIIIIII", data[pos:pos + 36])
        out.append({"size": nominal, "width": w, "height": h, "xhot": xh, "yhot": yh, "delay": delay,
                    "pixels": data[pos + 36:pos + 36 + w * h * 4]})
    return out


def build(dest: Path, spec: dict, sizes: tuple[int, ...] = SIZES) -> int:
    """Write the cursors/ directory of a theme into dest. Returns the number of cursor names."""
    c = colors_of(spec)
    cells = _cells()
    images: dict[str, list] = {cur.name: [] for cur in CURSORS}
    for size in sorted(set(sizes)):
        w, h, rgba = decode_png(_render_png(sprite_svg(c, size)))
        if (w, h) != (size * len(cells), size):
            raise CursorError(f"unexpected sprite size {w}x{h}")
        for i, (cur, _) in enumerate(cells):
            xh = min(size - 1, round(cur.hotspot[0] * size / CANVAS))
            yh = min(size - 1, round(cur.hotspot[1] * size / CANVAS))
            delay = FRAME_MS if cur.animated else 0
            images[cur.name].append((size, size, xh, yh, delay, _argb(rgba, w, i * size, size)))

    staging = dest.with_name(f".{dest.name}.tmp")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    count = 0
    for cur in CURSORS:
        (staging / cur.name).write_bytes(xcursor(images[cur.name]))
        for alias in cur.aliases:
            (staging / alias).symlink_to(cur.name)
        count += 1 + len(cur.aliases)
    shutil.rmtree(dest, ignore_errors=True)
    os.replace(staging, dest)
    return count

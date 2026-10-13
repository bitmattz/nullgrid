"""Text graphics: segmented bars and column graphs.

Two glyph sets: the Linux console font only has a few block glyphs (█ ▒ ░ ■ ·), while a
desktop terminal can use eighth blocks for smoother graphs.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Glyphs:
    bar_on: str
    bar_off: str
    levels: str      # partial cells for graphs, lowest first; the last one is a full cell
    rule: str


CONSOLE = Glyphs(bar_on="■", bar_off="·", levels="░▒█", rule="─")
DESKTOP = Glyphs(bar_on="■", bar_off="·", levels="▁▂▃▄▅▆▇█", rule="─")


def bar(fraction: float, width: int, g: Glyphs) -> str:
    """A segmented bar: ■■■■······"""
    width = max(0, width)
    on = round(max(0.0, min(1.0, fraction)) * width)
    return g.bar_on * on + g.bar_off * (width - on)


def graph(values: list[float], width: int, height: int, top: float, g: Glyphs) -> list[str]:
    """Column graph of the newest `width` values (right-aligned), `height` rows, top row first."""
    if width <= 0 or height <= 0:
        return []
    vals = list(values)[-width:]
    vals = [0.0] * (width - len(vals)) + vals
    steps = len(g.levels)
    rows = [[" "] * width for _ in range(height)]
    for x, v in enumerate(vals):
        units = 0 if top <= 0 else round(max(0.0, min(1.0, v / top)) * height * steps)
        if v > 0 and units == 0:
            units = 1  # any traffic at all is visible
        for y in range(height):  # y = 0 is the bottom row
            filled = units - y * steps
            if filled >= steps:
                rows[height - 1 - y][x] = g.levels[-1]
            elif filled > 0:
                rows[height - 1 - y][x] = g.levels[filled - 1]
    return ["".join(r) for r in rows]


def nice_top(peak: float) -> float:
    """Round a byte rate up to 1, 2 or 5 x 10^n of its unit (K, M, ...), so the scale label
    printed by human_bytes stays round: 50K, not 48.8K."""
    if peak <= 0:
        return 1.0
    unit = 1024 ** min(4, max(0, int(math.log(peak, 1024))))
    value = peak / unit
    exp = 10 ** math.floor(math.log10(value))
    for m in (1, 2, 5, 10):
        if value <= m * exp:
            return m * exp * unit
    return 10 * exp * unit


def human_bytes(n: float, rate: bool = False) -> str:
    units = ["B", "K", "M", "G", "T"]
    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024
        i += 1
    number = f"{n:.0f}" if n >= 100 or i == 0 else f"{n:.1f}".removesuffix(".0")
    text = number + units[i]
    return text + ("/s" if rate else "")


def duration(seconds: float) -> str:
    s = int(seconds)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m = s // 60
    return f"{d}d {h:02d}:{m:02d}" if d else f"{h:02d}:{m:02d}"

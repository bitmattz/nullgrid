"""The NULLGRID logo, concept B "dead pixel lattice": a lattice of short line segments with one
cell missing, the hole glowing in the secondary accent (docs/LOGO.md).

One geometry, three renderings: ASCII for fastfetch (console-safe glyphs only), a standalone
SVG, and an SVG group the wallpaper embeds. assets/logo/generate.py writes the asset files.
"""
from __future__ import annotations

from dataclasses import dataclass

WORDMARK = "NULLGRID"


@dataclass(frozen=True)
class Lattice:
    cells: int = 4               # cells per side
    hole: tuple[int, int] = (2, 2)  # (row, column) of the dead pixel

    def edges(self) -> list[tuple[tuple[int, int], tuple[int, int]]]:
        """Cell edges as ((row, col), (row, col)) node pairs, minus the hole's four sides."""
        n, (hr, hc) = self.cells, self.hole
        hole = {((hr, hc), (hr, hc + 1)), ((hr + 1, hc), (hr + 1, hc + 1)),
                ((hr, hc), (hr + 1, hc)), ((hr, hc + 1), (hr + 1, hc + 1))}
        out = []
        for r in range(n + 1):
            out += [((r, c), (r, c + 1)) for c in range(n)]
        for c in range(n + 1):
            out += [((r, c), (r + 1, c)) for r in range(n)]
        return [e for e in out if e not in hole]


FULL = Lattice()
SMALL = Lattice(cells=2, hole=(1, 1))  # for 16-32 px: fewer, thicker cells


# --------------------------------------------------------------------------- ASCII
_JOINTS = {  # (top, bottom, left, right) edge flags -> junction glyph
    (1, 0, 1, 0): "┌", (1, 0, 0, 1): "┐", (0, 1, 1, 0): "└", (0, 1, 0, 1): "┘",
    (1, 0, 0, 0): "┬", (0, 1, 0, 0): "┴", (0, 0, 1, 0): "├", (0, 0, 0, 1): "┤",
}


def ascii_art(lattice: Lattice = FULL, cell_w: int = 5, cell_h: int = 2) -> list[str]:
    """Lines with fastfetch color markers: $1 primary (lattice), $2 secondary (hole, GRID)."""
    n, (hr, hc) = lattice.cells, lattice.hole
    rows, cols = n * (cell_h + 1) + 1, n * (cell_w + 1) + 1
    glyph = [[" "] * cols for _ in range(rows)]
    slot = [[1] * cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            on_h, on_v = r % (cell_h + 1) == 0, c % (cell_w + 1) == 0
            if on_h and on_v:
                edges = (r == 0, r == rows - 1, c == 0, c == cols - 1)
                glyph[r][c] = _JOINTS.get(tuple(map(int, edges)), "┼")
            elif on_h:
                glyph[r][c] = "─"
            elif on_v:
                glyph[r][c] = "│"

    # The dead pixel: its frame is gone (crossings stay so the lattice still reads), filled with glow.
    top, left = hr * (cell_h + 1), hc * (cell_w + 1)
    bottom, right = top + cell_h + 1, left + cell_w + 1
    for r in range(top, bottom + 1):
        for c in range(left, right + 1):
            if r in (top, bottom) and c in (left, right):
                continue
            glyph[r][c] = "░" if r in (top, bottom) or c in (left, right) else "▒"
            slot[r][c] = 2

    lines = []
    for r in range(rows):
        line, current = "", None
        for c in range(cols):
            if slot[r][c] != current:
                current = slot[r][c]
                line += f"${current}"
            line += glyph[r][c]
        lines.append(line)
    spaced = " ".join(WORDMARK[:4]) + "   " + " ".join(WORDMARK[4:])
    half = spaced.index("G")
    pad = " " * ((cols - len(spaced)) // 2)
    return lines + ["", f"$1{pad}{spaced[:half]}$2{spaced[half:]}"]


# --------------------------------------------------------------------------- SVG
def _f(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def svg_group(x: float, y: float, size: float, primary: str, secondary: str, *,
              lattice: Lattice = FULL, stroke: float | None = None, glow: float = 0.6,
              glow_filter: str | None = None) -> str:
    """The mark as a <g> inside a size x size box at (x, y). glow_filter: id of a blur filter
    defined by the caller, used for the hole's halo."""
    n = lattice.cells
    cell = size / n
    sw = stroke if stroke is not None else max(1.0, cell * (0.09 if n > 2 else 0.16))
    gap = cell * (0.16 if n > 2 else 0.12)   # segments stop short of the crossings
    parts = [f'<g transform="translate({_f(x)} {_f(y)})">']
    lines = []
    for (r1, c1), (r2, c2) in lattice.edges():
        x1, y1, x2, y2 = c1 * cell, r1 * cell, c2 * cell, r2 * cell
        if r1 == r2:
            x1, x2 = x1 + gap, x2 - gap
        else:
            y1, y2 = y1 + gap, y2 - gap
        lines.append(f'<line x1="{_f(x1)}" y1="{_f(y1)}" x2="{_f(x2)}" y2="{_f(y2)}"/>')
    parts.append(f'<g stroke="{primary}" stroke-width="{_f(sw)}" stroke-linecap="square">{"".join(lines)}</g>')
    # crossings: small squares at every node, so the lattice reads at a glance
    dot = sw * 1.6
    nodes = "".join(f'<rect x="{_f(c * cell - dot / 2)}" y="{_f(r * cell - dot / 2)}" '
                    f'width="{_f(dot)}" height="{_f(dot)}"/>'
                    for r in range(n + 1) for c in range(n + 1))
    parts.append(f'<g fill="{primary}">{nodes}</g>')
    hr, hc = lattice.hole
    inset = cell * 0.2
    hx, hy, hs = hc * cell + inset, hr * cell + inset, cell - 2 * inset
    if glow_filter and glow > 0:
        parts.append(f'<rect x="{_f(hx)}" y="{_f(hy)}" width="{_f(hs)}" height="{_f(hs)}" fill="{secondary}" '
                     f'opacity="{_f(min(1.0, glow + 0.2))}" filter="url(#{glow_filter})"/>')
    parts.append(f'<rect x="{_f(hx)}" y="{_f(hy)}" width="{_f(hs)}" height="{_f(hs)}" fill="{secondary}"/>')
    parts.append("</g>")
    return "".join(parts)


def svg(primary: str = "#5ef2f2", secondary: str = "#ff3b4e", *, lattice: Lattice = FULL,
        size: int = 256, background: str | None = None) -> str:
    """A standalone SVG of the mark, with a margin for the glow."""
    pad = size * 0.1
    inner = size - 2 * pad
    blur = inner / lattice.cells * 0.18
    bg = f'<rect width="{size}" height="{size}" fill="{background}"/>' if background else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
            f'<defs><filter id="glow" x="-1" y="-1" width="3" height="3">'
            f'<feGaussianBlur stdDeviation="{_f(blur)}"/></filter></defs>'
            f'{bg}{svg_group(pad, pad, inner, primary, secondary, lattice=lattice, glow_filter="glow")}</svg>\n')

#!/usr/bin/env python3
"""Draw the NULLGRID logo (concept B, "dead pixel lattice") as text for fastfetch.

A 4x4 lattice with one cell missing; the hole glows in the secondary accent.
Only glyphs the Linux console font (Terminus) has are used, so it renders on a TTY too.
$1 / $2 are fastfetch color slots (primary / secondary).

Usage: generate_ascii.py   (writes nullgrid.txt next to this script)
"""
from pathlib import Path

CELLS, CELL_W, CELL_H = 4, 5, 2   # cells per side, interior width/height in characters
HOLE = (2, 2)                     # (row, column) of the dead pixel
WORDMARK = "N U L L   G R I D"

JOINTS = {  # (top, bottom, left, right) edge flags -> junction glyph
    (1, 0, 1, 0): "┌", (1, 0, 0, 1): "┐", (0, 1, 1, 0): "└", (0, 1, 0, 1): "┘",
    (1, 0, 0, 0): "┬", (0, 1, 0, 0): "┴", (0, 0, 1, 0): "├", (0, 0, 0, 1): "┤",
}


def draw() -> list[str]:
    rows, cols = CELLS * (CELL_H + 1) + 1, CELLS * (CELL_W + 1) + 1
    glyph = [[" "] * cols for _ in range(rows)]
    slot = [[1] * cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            on_h, on_v = r % (CELL_H + 1) == 0, c % (CELL_W + 1) == 0
            if on_h and on_v:
                edges = (r == 0, r == rows - 1, c == 0, c == cols - 1)
                glyph[r][c] = JOINTS.get(tuple(map(int, edges)), "┼")
            elif on_h:
                glyph[r][c] = "─"
            elif on_v:
                glyph[r][c] = "│"

    # The dead pixel: its frame is gone (crossings stay so the lattice still reads), filled with glow.
    top, left = HOLE[0] * (CELL_H + 1), HOLE[1] * (CELL_W + 1)
    bottom, right = top + CELL_H + 1, left + CELL_W + 1
    for r in range(top, bottom + 1):
        for c in range(left, right + 1):
            if r in (top, bottom) and c in (left, right):
                continue
            edge = r in (top, bottom) or c in (left, right)
            glyph[r][c] = "░" if edge else "▒"
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
    half = WORDMARK.index("G")
    pad = " " * ((cols - len(WORDMARK)) // 2)
    lines += ["", f"$1{pad}{WORDMARK[:half]}$2{WORDMARK[half:]}"]
    return lines


if __name__ == "__main__":
    out = Path(__file__).with_name("nullgrid.txt")
    out.write_text("\n".join(draw()) + "\n")
    print(out.read_text().replace("$1", "").replace("$2", ""))

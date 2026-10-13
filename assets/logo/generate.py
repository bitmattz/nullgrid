#!/usr/bin/env python3
"""Write the NULLGRID logo files (concept B, "dead pixel lattice") from the geometry in
tools/nullgrid/nullgrid/logo.py:

  nullgrid.txt        ASCII for fastfetch ($1/$2 = primary/secondary color slots; console-safe glyphs)
  nullgrid.svg        the mark in the crimson-hud colors, transparent background
  nullgrid-small.svg  simplified 2x2 variant for 16-32 px (tray, favicon)

Usage: generate.py   (writes next to this script; the wallpaper draws the mark itself, per theme)
"""
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
sys.path.insert(0, str(here.parents[1] / "tools" / "nullgrid"))
from nullgrid import logo  # noqa: E402

if __name__ == "__main__":
    (here / "nullgrid.txt").write_text("\n".join(logo.ascii_art()) + "\n")
    (here / "nullgrid.svg").write_text(logo.svg())
    (here / "nullgrid-small.svg").write_text(logo.svg(lattice=logo.SMALL, size=32))
    print((here / "nullgrid.txt").read_text().replace("$1", "").replace("$2", ""))

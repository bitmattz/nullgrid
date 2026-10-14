#!/usr/bin/env python3
"""window_color.py APP_ID [COLOR ...]: the most common color inside a Sway window (from a grim
capture), as #rrggbb. With COLORs: exit 1 unless it is close to one of them. The shell smoke
test uses it to check that GTK and Qt windows took the theme's background, and follow a switch."""
import collections
import json
import subprocess
import sys
import tempfile


def find(node, app_id):
    if node.get("app_id") == app_id and node.get("pid"):
        return node
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        if (hit := find(child, app_id)) is not None:
            return hit
    return None


def dominant(app_id):
    tree = json.loads(subprocess.run(["swaymsg", "-t", "get_tree"], capture_output=True, text=True).stdout)
    win = find(tree, app_id)
    if win is None:
        sys.exit(f"no window with app_id {app_id}")
    r = win["rect"]
    with tempfile.NamedTemporaryFile(suffix=".ppm") as f:
        subprocess.run(["grim", "-t", "ppm", "-g", f"{r['x']},{r['y']} {r['width']}x{r['height']}", f.name], check=True)
        data = open(f.name, "rb").read()
    fields, pos = [], 2
    while len(fields) < 3:  # P6 header: width height maxval
        while data[pos:pos + 1].isspace():
            pos += 1
        start = pos
        while not data[pos:pos + 1].isspace():
            pos += 1
        fields.append(int(data[start:pos]))
    px = data[pos + 1:]
    counts = collections.Counter(px[i:i + 3] for i in range(0, len(px) - 2, 3))
    return counts.most_common(1)[0][0]


def rgb(hexv):
    h = hexv.lstrip("#")
    return bytes(int(h[i:i + 2], 16) for i in (0, 2, 4))


got = dominant(sys.argv[1])
print("#" + got.hex())
if len(sys.argv) > 2:
    near = min(sum(abs(a - b) for a, b in zip(got, rgb(c))) for c in sys.argv[2:])
    sys.exit(0 if near <= 30 else 1)

"""GTK/Qt apps, icons and cursors: what `nullgrid toolkit apply` does.

The `toolkit` manifest target writes ~/.config/nullgrid/generated/toolkit.json (theme names,
fonts, cursor size, colors); its reload hook runs `nullgrid toolkit apply --reload`, which:

  1. regenerates the icon theme ~/.local/share/icons/NULLGRID/ (icons.py) if the colors changed,
  2. renders the cursors (cursors.py, cached per palette) and links them into that theme,
  3. writes the desktop settings GTK reads (org.gnome.desktop.interface: theme, icons, cursor,
     fonts, dark style) with gsettings, when a session bus is there,
  4. makes running apps pick the new files up: GTK only re-reads a theme when its name changes,
     so the names flip to Adwaita and back; Hyprland/Sway get the cursor again.

The GTK theme files themselves are ordinary templates (gtk3.css.j2, gtk4.css.j2); Qt apps follow
qt6ct, which watches ~/.config/qt6ct/ by itself.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import cursors, icons
from .paths import Paths

SCHEMA = "org.gnome.desktop.interface"
# spec key -> gsettings key
SETTINGS = {
    "gtk_theme": "gtk-theme",
    "icon_theme": "icon-theme",
    "cursor_theme": "cursor-theme",
    "cursor_size": "cursor-size",
    "font": "font-name",
    "mono_font": "monospace-font-name",
    "color_scheme": "color-scheme",
}
# what the names flip to for a moment, so GTK reloads
FLIP = {"gtk-theme": "Adwaita", "icon-theme": "Adwaita", "cursor-theme": "Adwaita"}
KEEP_CURSOR_CACHES = 4


class ToolkitError(Exception):
    pass


@dataclass
class Result:
    icons: bool = False             # icon theme regenerated
    cursors: bool = False           # cursor theme changed
    settings: list[str] = field(default_factory=list)   # gsettings keys written
    reloaded: list[str] = field(default_factory=list)   # what was told to reload
    notes: list[str] = field(default_factory=list)


def load_spec(paths: Paths) -> dict:
    f = paths.config_dir / "generated" / "toolkit.json"
    try:
        return json.loads(f.read_text())
    except FileNotFoundError:
        raise ToolkitError(f"{f} is missing; run: nullgrid theme reload") from None
    except ValueError as exc:
        raise ToolkitError(f"{f}: not valid JSON: {exc}") from None


def theme_dir(paths: Paths) -> Path:
    return paths.data_home / "icons" / icons.THEME_NAME


# --------------------------------------------------------------------------- files
def build_icons(paths: Paths, spec: dict, force: bool = False) -> bool:
    """Regenerate the icon theme if its colors (or the generator) changed. True if it did."""
    d = theme_dir(paths)
    stamp_file = d / ".nullgrid-icons"
    want = icons.stamp(spec)
    if not force and (d / "scalable").is_dir() and _read(stamp_file) == want:
        return False
    icons.build(d, spec)
    stamp_file.write_text(want + "\n")
    return True


def cursor_sizes(spec: dict) -> tuple[int, ...]:
    return tuple(sorted({*cursors.SIZES, int(spec.get("cursor_size", 24))}))


def build_cursors(paths: Paths, spec: dict, force: bool = False) -> bool:
    """Make the theme's cursors/ point at the cursors for this palette, rendering them first if
    they aren't cached. True if the link changed."""
    sizes = cursor_sizes(spec)
    cache = paths.cache_dir / "cursors"
    target = cache / cursors.stamp(spec, sizes)
    if force or not (target / "default").is_file():
        cursors.build(target, spec, sizes)
    link = theme_dir(paths) / "cursors"
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink() and os.readlink(link) == str(target) and not force:
        return False
    if link.exists() and not link.is_symlink():
        shutil.rmtree(link)
    tmp = link.with_name(".cursors.tmp")
    tmp.unlink(missing_ok=True)
    tmp.symlink_to(target)
    os.replace(tmp, link)
    _prune(cache, keep=target)
    return True


def _prune(cache: Path, keep: Path) -> None:
    dirs = sorted((d for d in cache.iterdir() if d.is_dir() and d != keep and not d.name.startswith(".")),
                  key=lambda d: d.stat().st_mtime, reverse=True)
    for d in dirs[KEEP_CURSOR_CACHES - 1:]:
        shutil.rmtree(d, ignore_errors=True)


def _read(f: Path) -> str:
    try:
        return f.read_text().strip()
    except OSError:
        return ""


# --------------------------------------------------------------------------- settings
def bus_available() -> bool:
    if os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        return True
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    return bool(runtime) and Path(runtime, "bus").exists()


def _gsettings(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["gsettings", *args], capture_output=True, text=True, timeout=10)


def _gvariant(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'") + "'"


def settings_available() -> str | None:
    """None if gsettings can be used, else why not."""
    if shutil.which("gsettings") is None:
        return "gsettings not found (package glib2)"
    if not bus_available():
        return "no session bus"
    try:
        if _gsettings("list-keys", SCHEMA).returncode != 0:
            return f"schema {SCHEMA} not installed (package gsettings-desktop-schemas)"
    except (OSError, subprocess.SubprocessError) as exc:
        return f"gsettings failed: {exc}"
    return None


def current_settings() -> dict[str, str]:
    """gsettings key -> current value, as gsettings prints it."""
    out = {}
    for key in SETTINGS.values():
        r = _gsettings("get", SCHEMA, key)
        if r.returncode == 0:
            out[key] = r.stdout.strip()
    return out


def sync_settings(spec: dict) -> list[str]:
    """Write the keys whose value differs from the spec. Returns the keys written."""
    current = current_settings()
    written = []
    for name, key in SETTINGS.items():
        if name not in spec:
            continue
        want = _gvariant(spec[name])
        if current.get(key) == want:
            continue
        if _gsettings("set", SCHEMA, key, want).returncode == 0:
            written.append(key)
    return written


def flip(keys: list[str], spec: dict) -> None:
    """Switch the theme names away and back: GTK apps re-read a theme only when its name changes."""
    names = {SETTINGS[n]: spec[n] for n in ("gtk_theme", "icon_theme", "cursor_theme") if n in spec}
    keys = [k for k in keys if k in names]
    for key in keys:
        _gsettings("set", SCHEMA, key, _gvariant(FLIP[key]))
    if keys:
        time.sleep(0.25)
    for key in keys:
        _gsettings("set", SCHEMA, key, _gvariant(names[key]))


def compositor_cursor(spec: dict) -> str | None:
    """Tell the running compositor to load the cursor theme again. Returns which one."""
    theme, size = spec.get("cursor_theme", icons.THEME_NAME), str(spec.get("cursor_size", 24))
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") and shutil.which("hyprctl"):
        argv, name = ["hyprctl", "setcursor", theme, size], "hyprland"
    elif os.environ.get("SWAYSOCK") and shutil.which("swaymsg"):
        argv, name = ["swaymsg", f"seat * xcursor_theme {theme} {size}"], "sway"
    else:
        return None
    try:
        ok = subprocess.run(argv, capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        ok = False
    return name if ok else None


# --------------------------------------------------------------------------- apply
def apply(paths: Paths, *, reload: bool = False, force: bool = False) -> Result:
    """Generate icons and cursors, write the desktop settings and, with reload (the manifest
    hook: GTK theme files changed) or when anything changed, make running apps reload."""
    spec = load_spec(paths)
    res = Result()
    res.icons = build_icons(paths, spec, force)
    try:
        res.cursors = build_cursors(paths, spec, force)
    except cursors.CursorError as exc:
        res.notes.append(f"cursors not generated: {exc}")

    why_not = settings_available()
    if why_not:
        res.notes.append(f"desktop settings not written: {why_not}")
    else:
        res.settings = sync_settings(spec)
        flips = []
        if reload:
            flips.append("gtk-theme")
        if res.icons:
            flips.append("icon-theme")
        if res.cursors:
            flips.append("cursor-theme")
        # a key just written already told the apps; flip only the others
        flips = [k for k in flips if k not in res.settings]
        flip(flips, spec)
        res.reloaded += [k for k in flips]
    if res.cursors or reload or "cursor-size" in res.settings:
        if (name := compositor_cursor(spec)) is not None:
            res.reloaded.append(f"{name} cursor")
    return res

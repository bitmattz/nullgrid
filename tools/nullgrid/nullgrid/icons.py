"""The NULLGRID icon theme: original line icons, generated as SVG in the theme's colors.

Four frames carry the glyphs from glyphs.py: a circle (apps, categories), a chamfered folder
(places), a document sheet with a cut corner (file types) and a chamfered plate (devices).
Only the names below are drawn; everything else (toolbar and status icons, which GTK recolors
itself, and icons of apps we don't know) comes from the inherited themes, Adwaita and hicolor.

The theme is generated per user into ~/.local/share/icons/NULLGRID/ by `nullgrid toolkit
apply`, so a theme switch recolors it. The cursors (cursors.py) live in the same directory.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

from .glyphs import GLYPHS
from .logo import SMALL, svg_group

THEME_NAME = "NULLGRID"
GENERATOR_VERSION = 1  # bump when the drawing changes: generated themes are redone

# (frame, glyph) -> icon names drawn with it. Frames: app, folder, file, device. Glyph None:
# the frame alone; "logo": the lattice mark.
ICONS: dict[str, list[tuple[str, str | None, list[str]]]] = {
    "apps": [
        ("app", "logo", ["nullgrid", "start-here", "distributor-logo", "distributor-logo-nullgrid",
                         "archlinux-logo", "nullgrid-shell"]),
        ("app", "terminal", ["kitty", "utilities-terminal", "org.gnome.Console", "org.gnome.Terminal",
                             "terminal", "foot", "Alacritty"]),
        ("app", "globe", ["firefox", "org.mozilla.firefox", "web-browser", "internet-web-browser",
                          "chromium", "google-chrome"]),
        ("app", "files", ["org.xfce.thunar", "thunar", "Thunar", "system-file-manager", "org.gnome.Nautilus",
                          "file-manager", "yazi"]),
        ("app", "image", ["org.xfce.ristretto", "ristretto", "image-viewer", "org.gnome.eog", "org.gnome.Loupe",
                          "imv", "multimedia-photo-viewer"]),
        ("app", "pdf", ["org.pwmt.zathura", "zathura", "document-viewer", "org.gnome.Evince", "org.gnome.Papers"]),
        ("app", "editor", ["nvim", "accessories-text-editor", "text-editor", "org.gnome.TextEditor", "vim", "gvim"]),
        ("app", "monitor", ["btop", "htop", "utilities-system-monitor", "org.gnome.SystemMonitor"]),
        ("app", "dashboard", ["nullgrid-dash"]),
        ("app", "settings", ["preferences-system", "preferences-desktop", "org.gnome.Settings",
                             "systemsettings", "gnome-settings", "preferences-other"]),
        ("app", "palette", ["preferences-desktop-theme", "qt6ct", "qt5ct", "kvantum", "preferences-desktop-color"]),
        ("app", "media", ["multimedia-video-player", "mpv", "vlc", "totem", "org.gnome.Totem"]),
        ("app", "music", ["multimedia-audio-player", "audio-player", "cava"]),
        ("app", "volume", ["multimedia-volume-control", "pavucontrol", "org.pulseaudio.pavucontrol"]),
        ("app", "code", ["code", "vscodium", "com.visualstudio.code", "lazygit", "git"]),
        ("app", "mail", ["mail-client", "internet-mail", "thunderbird", "org.mozilla.Thunderbird"]),
        ("app", "calculator", ["accessories-calculator", "org.gnome.Calculator", "galculator"]),
        ("app", "archive", ["file-roller", "org.gnome.FileRoller", "xarchiver", "ark"]),
        ("app", "tool", ["applications-utilities", "accessories", "utilities"]),
        ("app", "bluetooth", ["bluetooth", "blueman", "blueberry"]),
        ("app", "wifi", ["nm-connection-editor", "network-manager", "preferences-system-network"]),
        ("app", "lock", ["system-lock-screen", "hyprlock"]),
        ("app", "power", ["system-shutdown", "system-log-out"]),
        ("app", "info", ["help-about", "help-browser", "dialog-information", "fastfetch"]),
        ("app", "keyboard", ["preferences-desktop-keyboard", "input-keyboard-settings"]),
        ("app", "font", ["preferences-desktop-font", "font-viewer", "org.gnome.font-viewer"]),
        ("app", "unknown", ["application-default-icon", "application-x-executable-app"]),
    ],
    "categories": [
        ("app", "code", ["applications-development"]),
        ("app", "image", ["applications-graphics"]),
        ("app", "globe", ["applications-internet"]),
        ("app", "media", ["applications-multimedia"]),
        ("app", "office", ["applications-office"]),
        ("app", "system", ["applications-system"]),
        ("app", "game", ["applications-games"]),
        ("app", "apps", ["applications-other", "applications-all"]),
        ("app", "settings", ["preferences-desktop-peripherals", "preferences-system-network-proxy"]),
    ],
    "places": [
        ("folder", None, ["folder", "inode-directory", "folder-open", "folder-saved-search"]),
        ("folder", "home", ["user-home", "folder-home"]),
        ("folder", "computer", ["user-desktop", "folder-desktop"]),
        ("folder", "document", ["folder-documents"]),
        ("folder", "download", ["folder-download", "folder-downloads"]),
        ("folder", "music", ["folder-music"]),
        ("folder", "image", ["folder-pictures", "folder-images"]),
        ("folder", "video", ["folder-videos", "folder-video"]),
        ("folder", "template", ["folder-templates"]),
        ("folder", "share", ["folder-publicshare", "folder-public"]),
        ("folder", "network", ["folder-remote", "network-workgroup", "network-server"]),
        ("folder", "code", ["folder-development", "folder-git", "folder-projects"]),
        ("folder", "star", ["user-bookmarks", "folder-favorites"]),
        ("device", "trash", ["user-trash"]),
        ("device", "trash_full", ["user-trash-full"]),
    ],
    "mimetypes": [
        ("file", None, ["unknown", "application-octet-stream", "empty", "application-x-zerosize"]),
        ("file", "text", ["text-x-generic", "text-plain", "text-x-readme", "text-markdown", "text-x-log",
                          "x-office-document", "application-rtf"]),
        ("file", "script", ["text-x-script", "application-x-shellscript", "text-x-python", "application-x-perl",
                            "text-x-csrc", "text-x-chdr", "text-x-c++src", "text-rust", "text-x-go",
                            "application-javascript", "text-x-lua", "application-json", "application-toml",
                            "application-xml", "text-css"]),
        ("file", "globe", ["text-html", "application-xhtml+xml"]),
        ("file", "image", ["image-x-generic", "image-png", "image-jpeg", "image-svg+xml", "image-gif",
                           "image-webp"]),
        ("file", "music", ["audio-x-generic", "audio-mpeg", "audio-x-wav", "audio-flac", "audio-ogg"]),
        ("file", "video", ["video-x-generic", "video-mp4", "video-webm", "video-x-matroska"]),
        ("file", "pdf", ["application-pdf", "x-office-presentation"]),
        ("file", "calculator", ["x-office-spreadsheet", "text-csv"]),
        ("file", "archive", ["package-x-generic", "application-x-archive", "application-zip",
                             "application-x-compressed-tar", "application-x-tar", "application-x-xz",
                             "application-zstd", "application-x-7z-compressed", "application-x-rar"]),
        ("file", "binary", ["application-x-executable", "application-x-sharedlib", "application-x-object"]),
        ("file", "optical", ["application-x-cd-image", "application-x-iso9660-image"]),
        ("file", "font", ["font-x-generic", "font-ttf", "font-otf"]),
    ],
    "devices": [
        ("device", "disk", ["drive-harddisk", "drive-harddisk-solidstate", "drive-harddisk-system", "drive-multidisk"]),
        ("device", "usb", ["drive-removable-media", "media-removable", "drive-removable-media-usb", "media-flash"]),
        ("device", "optical", ["drive-optical", "media-optical"]),
        ("device", "computer", ["computer", "video-display", "display"]),
        ("device", "network", ["network-wired", "network-vpn"]),
        ("device", "wifi", ["network-wireless"]),
        ("device", "keyboard", ["input-keyboard"]),
        ("device", "mouse", ["input-mouse", "input-touchpad"]),
        ("device", "speaker", ["audio-speakers", "audio-card", "audio-headphones"]),
        ("device", "bluetooth", ["bluetooth-active"]),
    ],
}

CONTEXTS = {"apps": "Applications", "categories": "Categories", "places": "Places", "mimetypes": "MimeTypes",
            "devices": "Devices"}


def _f(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _glyph(name: str, cx: float, cy: float, scale: float, color: str, width: float) -> str:
    """Glyph `name` (24x24) centered on (cx, cy)."""
    off = 12 * scale
    return (f'<path transform="translate({_f(cx - off)} {_f(cy - off)}) scale({_f(scale)})" d="{GLYPHS[name]}" '
            f'fill="none" stroke="{color}" stroke-width="{_f(width / scale)}" stroke-linecap="square" '
            f'stroke-linejoin="miter"/>')


def _content(glyph: str | None, cx: float, cy: float, scale: float, c: dict, width: float = 1.8) -> str:
    if glyph is None:
        return ""
    if glyph == "logo":
        size = 24 * scale
        return svg_group(cx - size / 2, cy - size / 2, size, c["primary"], c["secondary"], lattice=SMALL,
                         stroke=width * 1.1)
    return _glyph(glyph, cx, cy, scale, c["primary"], width)


def svg(frame: str, glyph: str | None, c: dict) -> str:
    """One icon on a 48x48 canvas. c: colors bg, surface, primary, secondary, dim (hex)."""
    if frame == "app":
        body = (f'<circle cx="24" cy="24" r="21.5" fill="{c["bg"]}" fill-opacity="0.92" stroke="{c["primary"]}" '
                f'stroke-width="2"/>'
                f'<circle cx="24" cy="24" r="18" fill="none" stroke="{c["dim"]}" stroke-width="0.8" '
                f'stroke-dasharray="2 3"/>'
                # a HUD tick on the ring, in the second accent
                f'<path d="M35.6 6.6 A21.5 21.5 0 0 1 43.3 15.3" fill="none" stroke="{c["secondary"]}" '
                f'stroke-width="3" stroke-linecap="butt"/>'
                + _content(glyph, 24, 24, 0.95, c))
    elif frame == "folder":
        body = (f'<path d="M4 10 L6 8 L18 8 L22 12 L42 12 L44 14 L44 38 L40 42 L4 42 Z" fill="{c["surface"]}" '
                f'stroke="{c["primary"]}" stroke-width="2" stroke-linejoin="miter"/>'
                f'<path d="M4 17 L44 17" stroke="{c["dim"]}" stroke-width="1"/>'
                f'<path d="M36 39 L40 35 M32 39 L40 31" stroke="{c["secondary"]}" stroke-width="1.6"/>'
                + _content(glyph, 23, 29.5, 0.62, c, 1.7))
    elif frame == "file":
        body = (f'<path d="M10 4 L32 4 L40 12 L40 44 L10 44 Z" fill="{c["surface"]}" stroke="{c["primary"]}" '
                f'stroke-width="2" stroke-linejoin="miter"/>'
                f'<path d="M32 4 L32 12 L40 12" fill="none" stroke="{c["primary"]}" stroke-width="1.4"/>'
                f'<path d="M14 40 L22 40" stroke="{c["secondary"]}" stroke-width="2"/>'
                + _content(glyph, 25, 25, 0.7, c, 1.6))
    elif frame == "device":
        body = (f'<path d="M9 4 L39 4 L44 9 L44 39 L39 44 L9 44 L4 39 L4 9 Z" fill="{c["bg"]}" fill-opacity="0.92" '
                f'stroke="{c["primary"]}" stroke-width="2" stroke-linejoin="miter"/>'
                f'<path d="M4 15 L4 9 L9 4 L15 4" fill="none" stroke="{c["secondary"]}" stroke-width="3"/>'
                + _content(glyph, 24, 24, 1.05, c))
    else:
        raise ValueError(f"unknown frame {frame!r}")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">'
            f'{body}</svg>\n')


def index_theme(inherits: str = "Adwaita,hicolor") -> str:
    lines = ["[Icon Theme]", f"Name={THEME_NAME}", "Comment=NULLGRID line icons and cursors (generated)",
             f"Inherits={inherits}", "Example=folder",
             "Directories=" + ",".join(f"scalable/{d}" for d in ICONS), ""]
    for d in ICONS:
        lines += [f"[scalable/{d}]", "Size=48", "MinSize=8", "MaxSize=512", "Type=Scalable",
                  f"Context={CONTEXTS[d]}", ""]
    return "\n".join(lines)


def colors_of(spec: dict) -> dict:
    return {k: spec["colors"][k] for k in ("bg", "surface", "primary", "secondary", "dim")}


def stamp(spec: dict) -> str:
    data = json.dumps({"v": GENERATOR_VERSION, "c": colors_of(spec)}, sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def build(dest: Path, spec: dict) -> int:
    """Write the icons into dest (the theme directory), replacing earlier ones. Returns the
    number of icon names. The cursors/ subdirectory is left alone."""
    c = colors_of(spec)
    staging = dest.with_name(f".{dest.name}.icons-tmp")
    shutil.rmtree(staging, ignore_errors=True)
    count = 0
    for context, entries in ICONS.items():
        d = staging / "scalable" / context
        d.mkdir(parents=True)
        for frame, glyph, names in entries:
            first, *aliases = names
            (d / f"{first}.svg").write_text(svg(frame, glyph, c))
            for alias in aliases:
                (d / f"{alias}.svg").symlink_to(f"{first}.svg")
            count += len(names)
    dest.mkdir(parents=True, exist_ok=True)
    old = dest / "scalable"
    if old.exists():
        trash = dest / ".scalable-old"
        shutil.rmtree(trash, ignore_errors=True)
        os.replace(old, trash)
        os.replace(staging / "scalable", old)
        shutil.rmtree(trash, ignore_errors=True)
    else:
        os.replace(staging / "scalable", old)
    shutil.rmtree(staging, ignore_errors=True)
    (dest / "index.theme").write_text(index_theme())
    (dest / "icon-theme.cache").unlink(missing_ok=True)  # a stale cache would hide new icons
    return count

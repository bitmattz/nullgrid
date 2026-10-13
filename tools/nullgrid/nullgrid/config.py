"""The nullgrid.toml schema, theme presets, and loading/saving the user config.

A theme preset (themes/<name>.toml) defines the look: palette, terminal colors, fonts, style.
The user config (~/.config/nullgrid/nullgrid.toml) picks a preset with `[theme] preset`, may
override any preset value under [theme.colors] / [theme.fonts] / [theme.style], and holds
everything that isn't the look: sound, widgets, decor, behavior, performance.
"""
from __future__ import annotations

import os
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomlkit

from .paths import Paths
from .schema import Bool, ColorField, Enum, Float, Int, Str, Table, Time

NAME = r"[a-z0-9][a-z0-9-]*"

# --------------------------------------------------------------------------- theme presets
TERMINAL = Table({
    "foreground": ColorField(),
    "background": ColorField(),
    "cursor": ColorField(),
    "selection": ColorField(),
    **{f"color{i}": ColorField() for i in range(16)},
}, doc="16-color terminal palette (also used by the Linux console, btop, nvim)")

COLORS = Table({
    "bg": ColorField(doc="background, gradient start"),
    "bg_alt": ColorField(doc="background, gradient end"),
    "surface": ColorField(doc="panels and frames"),
    "primary": ColorField(doc="main accent (neon)"),
    "secondary": ColorField(doc="second accent"),
    "glow": ColorField(doc="active window border and glow"),
    "text": ColorField(),
    "dim": ColorField(doc="secondary text, inactive borders"),
    "warning": ColorField(),
    "terminal": TERMINAL,
})

FONTS = Table({
    "ui": Str(default="Rajdhani", doc="condensed UI font"),
    "mono": Str(default="JetBrains Mono", doc="terminal and code"),
    "display": Str(default="Orbitron", doc="logo plate and big numbers"),
    "size": Int(6, 48, default=11, doc="UI font size in pt"),
    "mono_size": Int(6, 48, default=11, doc="terminal font size in pt"),
})

STYLE = Table({
    "border_width": Int(0, 8, default=2),
    "glow": Float(0, 1, default=0.6, doc="glow/shadow intensity"),
    "corners": Enum("sharp", "chamfer", "round", default="chamfer"),
    "surface_opacity": Float(0.3, 1, default=0.85),
    "terminal_opacity": Float(0.3, 1, default=0.92),
    "blur": Bool(default=True),
    "gaps": Int(0, 40, default=8, doc="space between windows in px"),
})

THEME = Table({
    "meta": Table({
        "name": Str(NAME, hint="a lowercase name like 'crimson-hud'"),
        "description": Str(default=""),
        "author": Str(default=""),
    }),
    "colors": COLORS,
    "fonts": FONTS,
    "style": STYLE,
})

# --------------------------------------------------------------------------- user config
WIDGET_POSITIONS = ("top", "bottom", "left", "right", "top-left", "top-right", "bottom-left", "bottom-right")


def _widget(visible: bool, position: str) -> Table:
    return Table({"visible": Bool(default=visible), "position": Enum(*WIDGET_POSITIONS, default=position)})


WIDGETS = Table({
    "dock": _widget(True, "left"),
    "bar": _widget(True, "bottom"),
    "ram_gauge": _widget(True, "bottom-right"),
    "net_graph": _widget(True, "bottom-right"),
    "cpu_bars": _widget(True, "bottom-right"),
    "workspace_strip": _widget(True, "bottom-right"),
    "activity_grid": _widget(True, "bottom-right"),
})

# Sound events and whether they are on by default (section 7 of the brief).
SOUND_EVENTS = {
    "boot": True, "login": True, "logout": True, "shutdown": True,
    "workspace_switch": True, "window_open": True, "window_close": True, "window_focus": False,
    "launcher_open": True, "launcher_close": True, "menu_hover": False, "button_click": True,
    "notification": True, "notification_critical": True,
    "volume_change": True, "brightness_change": True,
    "usb_connect": True, "usb_disconnect": True, "battery_low": True, "charger_plug": True,
    "screenshot": True, "error": True, "lock": True, "unlock": True,
    "terminal_bell": False, "command_done": False, "command_failed": False,
}

SOUND = Table({
    "enabled": Bool(default=True),
    "volume": Float(0, 1, default=0.6, doc="master volume"),
    "pack": Str(NAME, hint="a sound pack name", default="neural-link"),
    "quiet_hours": Table({
        "enabled": Bool(default=False),
        "start": Time(default="22:00"),
        "end": Time(default="07:00"),
        "volume": Float(0, 1, default=0.3, doc="volume multiplier during quiet hours"),
    }),
    "events": Table({
        name: Table({"enabled": Bool(default=on), "volume": Float(0, 1, default=1.0)})
        for name, on in SOUND_EVENTS.items()
    }),
})

DECOR = Table({
    "circuit_lines": Bool(default=True),
    "matrix_rain": Bool(default=True),
    "data_text": Bool(default=True),
    "scanlines": Bool(default=False),
})

BEHAVIOR = Table({
    "animation_speed": Float(0.25, 4, default=1.0, doc="multiplier; 2 = twice as fast"),
    "reduce_motion": Bool(default=False),
    "default_mode": Enum("desktop", "tty", default="desktop"),
    "keybinds": Str(default="default", doc="keybind set name or path to a file"),
    "greeting": Enum("fastfetch", "none", default="fastfetch", doc="shown when a terminal opens"),
})

PERFORMANCE = Table({
    "profile": Enum("full", "lite", default="full",
                    doc="lite: no blur/shadows/animations, slower widget refresh"),
})

CONFIG = Table({
    "theme": Table({
        "preset": Str(NAME, hint="a theme name like 'crimson-hud'", default="crimson-hud"),
        "colors": COLORS.as_partial(),
        "fonts": FONTS.as_partial(),
        "style": STYLE.as_partial(),
    }),
    "sound": SOUND,
    "widgets": WIDGETS,
    "decor": DECOR,
    "behavior": BEHAVIOR,
    "performance": PERFORMANCE,
})

OVERRIDABLE = ("colors", "fonts", "style")


# --------------------------------------------------------------------------- loading
class ConfigError(Exception):
    def __init__(self, source: Path | str, problems: list[str]):
        self.source = source
        self.problems = problems
        super().__init__(f"{source}: " + "; ".join(problems))

    def report(self) -> str:
        return f"{self.source}:\n" + "\n".join(f"  - {p}" for p in self.problems)


@dataclass
class Settings:
    """A validated user config plus the resolved theme."""
    config: dict          # validated user config, defaults filled in
    theme: dict           # validated preset with the user's overrides applied
    preset_path: Path
    config_path: Path | None  # None: no user config yet, defaults in use


def read_toml(path: Path) -> dict:
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(path, [f"not valid TOML: {exc}"]) from None


def find_theme(paths: Paths, name: str) -> Path | None:
    for d in paths.themes:
        p = d / f"{name}.toml"
        if p.is_file():
            return p
    return None


def list_themes(paths: Paths) -> dict[str, Path]:
    """Every preset name -> file, user themes shadowing system ones."""
    found: dict[str, Path] = {}
    for d in reversed(paths.themes):
        if d.is_dir():
            for p in sorted(d.glob("*.toml")):
                found[p.stem] = p
    return dict(sorted(found.items()))


def load_theme(path: Path) -> dict:
    errors: list[str] = []
    theme = THEME.validate(read_toml(path), "", errors)
    if not errors and theme["meta"]["name"] != path.stem:
        errors.append(f"meta.name: is {theme['meta']['name']!r} but the file is named {path.name!r}")
    if errors:
        raise ConfigError(path, errors)
    return theme


def validate_config(raw: dict, source: Path | str) -> dict:
    errors: list[str] = []
    cfg = CONFIG.validate(raw, "", errors)
    if errors:
        raise ConfigError(source, errors)
    return cfg


def load(paths: Paths, config_path: Path | None = None) -> Settings:
    """Load and validate the user config and its theme. Raises ConfigError."""
    path = config_path or paths.config_file
    if path.is_file():
        cfg = validate_config(read_toml(path), path)
        source: Path | None = path
    else:
        cfg = validate_config({}, "defaults")
        source = None
    name = cfg["theme"]["preset"]
    preset = find_theme(paths, name)
    if preset is None:
        known = ", ".join(list_themes(paths)) or "none found"
        raise ConfigError(source or "defaults", [f"theme.preset: no theme named {name!r} (available: {known})"])
    theme = apply_overrides(load_theme(preset), cfg["theme"])
    return Settings(config=cfg, theme=theme, preset_path=preset, config_path=source)


def apply_overrides(theme: dict, user_theme: dict) -> dict:
    out = {k: dict(v) if isinstance(v, dict) else v for k, v in theme.items()}
    out["colors"]["terminal"] = dict(theme["colors"]["terminal"])
    for section in OVERRIDABLE:
        for key, value in user_theme.get(section, {}).items():
            if isinstance(value, dict):  # colors.terminal
                out[section][key].update(value)
            else:
                out[section][key] = value
    return out


def overrides_in_use(cfg: dict) -> list[str]:
    """Dotted names of the preset values the user config overrides."""
    found = []
    for section in OVERRIDABLE:
        for key, value in cfg["theme"].get(section, {}).items():
            if isinstance(value, dict):
                found += [f"theme.{section}.{key}.{k}" for k in value]
            else:
                found.append(f"theme.{section}.{key}")
    return found


# --------------------------------------------------------------------------- editing
class ConfigDocument:
    """The user config as a comment-preserving tomlkit document, for CLI edits."""

    def __init__(self, paths: Paths):
        self.paths = paths
        self.path = paths.config_file
        if self.path.is_file():
            text = self.path.read_text()
        elif paths.default_config.is_file():
            text = paths.default_config.read_text()
        else:
            text = ""
        self.doc = tomlkit.parse(text)

    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.doc
        for key in dotted.split("."):
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node.unwrap() if hasattr(node, "unwrap") else node

    def set(self, dotted: str, value: Any) -> None:
        *parents, last = dotted.split(".")
        node: Any = self.doc
        for key in parents:
            if key not in node:
                node[key] = tomlkit.table()
            node = node[key]
        node[last] = value

    def remove(self, dotted: str) -> bool:
        *parents, last = dotted.split(".")
        node: Any = self.doc
        for key in parents:
            if key not in node:
                return False
            node = node[key]
        if last in node:
            del node[last]
            return True
        return False

    def validate(self) -> dict:
        return validate_config(self.doc.unwrap(), self.path)

    def save(self) -> None:
        """Validate, then write atomically. A config that wouldn't load is never written."""
        self.validate()
        atomic_write(self.path, tomlkit.dumps(self.doc))


def atomic_write(path: Path, text: str, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
        os.chmod(tmp, mode if mode is not None else 0o644)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise

"""Keybind sets: one TOML file drives the Hyprland and Sway bindings, `nullgrid keys` and the
keymap printed on the wallpaper, so they can't disagree.

A set lives in keybinds/<name>.toml (system dir or ~/.config/nullgrid/keybinds/, yours win) and
is chosen with `[behavior] keybinds = "<name>"`:

    [meta]
    name = "default"

    [keys]                       # action = combo, or a list of combos
    terminal = "SUPER+Return"
    focus_left = ["SUPER+Left", "SUPER+H"]
    workspace = "SUPER"          # modifiers only: + 1..9, 0 (workspaces 1-10)

    [exec]                       # extra binds: combo = shell command
    "SUPER+B" = "firefox"

Combos are modifiers (SUPER SHIFT CTRL ALT) and one xkb key name joined by "+".
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .paths import Paths
from .schema import Field, Invalid, Mapping, Str, Table

MODS = ("SUPER", "SHIFT", "CTRL", "ALT")
_MOD = "(?:SUPER|SHIFT|CTRL|ALT)"
COMBO = re.compile(rf"(?:{_MOD}\+)*[A-Za-z0-9_]+")
PREFIX = re.compile(rf"{_MOD}(?:\+{_MOD})*")

# Actions in display order: name -> (label, command). Commands run through a shell; actions
# without one are compositor actions that each compositor template implements.
ACTIONS: dict[str, tuple[str, str | None]] = {
    "terminal": ("terminal", "kitty"),
    "start_menu": ("start menu", "nullgrid-shell menu"),
    "launcher": ("app launcher", "fuzzel"),
    "files": ("file manager", "kitty --class nullgrid-files yazi"),
    "dashboard": ("system dashboard", "kitty --class nullgrid-dash nullgrid-dash"),
    "keys_help": ("show keybinds", "kitty --class nullgrid-keys nullgrid keys --pause"),
    "theme_next": ("next theme", "nullgrid theme next"),
    "lock": ("lock screen", "hyprlock"),
    "screenshot": ("screenshot (region)", "nullgrid-screenshot region"),
    "screenshot_screen": ("screenshot (screen)", "nullgrid-screenshot screen"),
    "close": ("close window", None),
    "fullscreen": ("fullscreen", None),
    "float": ("float / tile window", None),
    "focus_left": ("focus left", None),
    "focus_right": ("focus right", None),
    "focus_up": ("focus up", None),
    "focus_down": ("focus down", None),
    "move_left": ("move window left", None),
    "move_right": ("move window right", None),
    "move_up": ("move window up", None),
    "move_down": ("move window down", None),
    "exit": ("leave the desktop", None),
}
PREFIX_ACTIONS = {
    "workspace": "go to workspace 1-10",
    "move_to_workspace": "move window to workspace 1-10",
}
WORKSPACE_KEYS = [str(i % 10) for i in range(1, 11)]  # key "0" is workspace 10


class Combos(Field):
    """One combo or a list of them ([] leaves the action unbound)."""

    def check(self, value):
        items = [value] if isinstance(value, str) else value
        if not (isinstance(items, list) and all(isinstance(v, str) for v in items)):
            raise Invalid(f"expected a key combo like 'SUPER+Return' or a list of them, got {value!r}")
        for v in items:
            if not COMBO.fullmatch(v):
                raise Invalid(f"expected a combo like 'SUPER+SHIFT+Q' (modifiers: {' '.join(MODS)}), got {v!r}")
        return items


KEYBINDS = Table({
    "meta": Table({
        "name": Str(r"[a-z0-9][a-z0-9-]*", hint="a lowercase name like 'default'"),
        "description": Str(default=""),
    }),
    "keys": Table({
        **{name: Combos(default=[]) for name in ACTIONS},
        **{name: Str(PREFIX.pattern, hint="modifiers only, like 'SUPER+SHIFT'", default="")
           for name in PREFIX_ACTIONS},
    }),
    "exec": Mapping(default={}),
})


@dataclass
class Bind:
    combo: str            # "SUPER+SHIFT+Return"
    action: str           # an ACTIONS name, "workspace"/"move_to_workspace", or "exec"
    label: str
    command: str | None = None
    workspace: int | None = None

    @property
    def mods(self) -> list[str]:
        return self.combo.split("+")[:-1]

    @property
    def key(self) -> str:
        return self.combo.split("+")[-1]


def find(paths: Paths, name: str) -> Path | None:
    for d in paths.keybinds:
        p = d / f"{name}.toml"
        if p.is_file():
            return p
    return None


def available(paths: Paths) -> list[str]:
    return sorted({p.stem for d in paths.keybinds if d.is_dir() for p in d.glob("*.toml")})


def _normal(combo: str) -> tuple:
    *mods, key = combo.split("+")
    return tuple(sorted(m.upper() for m in mods)), key.lower()


def validate(raw: dict, path: Path | str) -> tuple[dict, list[str]]:
    errors: list[str] = []
    data = KEYBINDS.validate(raw, "", errors)
    if errors:
        return data, errors
    if isinstance(path, Path) and data["meta"]["name"] != path.stem:
        errors.append(f"meta.name: is {data['meta']['name']!r} but the file is named {path.name!r}")
    for combo, cmd in data["exec"].items():
        if not COMBO.fullmatch(combo):
            errors.append(f"exec.{combo}: not a key combo like 'SUPER+B'")
        elif not isinstance(cmd, str) or not cmd.strip():
            errors.append(f"exec.{combo}: expected a command string")
    if not errors:
        seen: dict[tuple, str] = {}
        for b in binds(data):
            where = f"exec.{b.combo}" if b.action == "exec" else f"keys.{b.action}"
            other = seen.setdefault(_normal(b.combo), where)
            if other != where:
                errors.append(f"{where}: {b.combo} is already bound by {other}")
    return data, errors


def binds(data: dict) -> list[Bind]:
    """Every binding of a validated set, in display order."""
    out = []
    for name, (label, command) in ACTIONS.items():
        out += [Bind(c, name, label, command) for c in data["keys"][name]]
    for name, label in PREFIX_ACTIONS.items():
        if prefix := data["keys"][name]:
            out += [Bind(f"{prefix}+{k}", name, label, workspace=i)
                    for i, k in enumerate(WORKSPACE_KEYS, start=1)]
    out += [Bind(combo, "exec", cmd, cmd) for combo, cmd in data["exec"].items()]
    return out


_PRETTY = {"Return": "ENTER", "grave": "`", "slash": "/", "space": "SPACE", "Escape": "ESC"}


def pretty(combo: str) -> str:
    """'SUPER+Return' -> 'SUPER+ENTER', for help texts."""
    *mods, key = combo.split("+")
    return "+".join([*mods, _PRETTY.get(key, key.upper())])


def summary(data: dict) -> list[tuple[str, str, str]]:
    """(combos, label, action) for help screens: one row per action, workspaces folded into one."""
    rows, done = [], set()
    all_binds = binds(data)
    for b in all_binds:
        if b.action == "exec":
            rows.append((pretty(b.combo), b.label, b.action))
        elif b.action in PREFIX_ACTIONS:
            if b.action not in done:
                rows.append((f"{data['keys'][b.action]}+1..0", b.label, b.action))
        elif b.action not in done:
            alts = [pretty(x.combo) for x in all_binds if x.action == b.action]
            rows.append((" / ".join(alts), b.label, b.action))
        done.add(b.action)
    return rows


# What the wallpaper's keymap block shows, in this order (actions the set leaves unbound are skipped).
ESSENTIALS = ("terminal", "start_menu", "launcher", "files", "dashboard", "keys_help", "theme_next", "close",
              "workspace", "lock", "exit")


def essentials(data: dict) -> list[tuple[str, str]]:
    """(first combo, label) of the most useful actions, for the wallpaper."""
    rows = {action: (combos.split(" / ")[0], label) for combos, label, action in summary(data)}
    return [rows[a] for a in ESSENTIALS if a in rows]

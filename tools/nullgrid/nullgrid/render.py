"""Render app configs from templates and hot-reload the apps that are running.

templates/manifest.toml lists one entry per generated file:

    [kitty]
    template = "kitty.conf.j2"                         # path under a templates dir
    target   = "{config_home}/kitty/nullgrid-theme.conf"
    # optional reload hook, run only when the file changed (or on `theme reload`):
    process  = "kitty"           # only if a process with this name runs (as this user)
    signal   = "USR1"            # ...send it this signal, or:
    reload   = ["makoctl", "reload"]                   # ...run this command
    env      = "HYPRLAND_INSTANCE_SIGNATURE"           # only if this env var is set ("VAR=value" also works)
    terminal = false             # let the reload command write to our terminal
    vars     = { tty = true }    # extra template variables (one template, several variants)
    enabled  = true

A manifest.toml in ~/.config/nullgrid/templates/ is merged over the system one (add entries,
change fields, or set enabled = false). Templates there shadow system templates by name.

All templates render into memory first; nothing is written unless every one succeeds.
Files whose content didn't change are left alone. A generated file that was edited by hand
since nullgrid last wrote it is backed up to <name>.bak before being replaced.
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import shutil
import signal as signals
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jinja2

from . import __version__
from . import keybinds as kbmod
from .color import Color
from .config import Settings, atomic_write, read_toml
from .paths import Paths
from .schema import Bool, Mapping, Str, StrList, Table

TARGET = Table({
    "template": Str(),
    "target": Str(),
    "process": Str(default=""),
    "signal": Str(r"[A-Z0-9]+", hint="a signal name like 'USR1'", default=""),
    "reload": StrList(default=[]),
    "env": Str(default=""),
    "terminal": Bool(default=False),
    "enabled": Bool(default=True),
    "mode": Str(r"0?[0-7]{3}", hint="a file mode like '644'", default="644"),
    "vars": Mapping(default={}),
})


class RenderError(Exception):
    pass


@dataclass
class Target:
    name: str
    template: str
    path: Path
    process: str = ""
    signal: str = ""
    reload: list[str] = field(default_factory=list)
    env: str = ""
    terminal: bool = False
    mode: int = 0o644
    vars: dict = field(default_factory=dict)


@dataclass
class Report:
    written: list[Target] = field(default_factory=list)
    unchanged: list[Target] = field(default_factory=list)
    backups: list[Path] = field(default_factory=list)
    reloaded: list[str] = field(default_factory=list)
    reload_failed: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- manifest
def load_manifest(paths: Paths) -> list[Target]:
    merged: dict[str, dict] = {}
    for d in reversed(paths.templates):  # system first, user overrides
        f = d / "manifest.toml"
        if f.is_file():
            for name, entry in read_toml(f).items():
                if not isinstance(entry, dict):
                    raise RenderError(f"{f}: [{name}] must be a table")
                merged.setdefault(name, {}).update(entry)

    targets = []
    for name, raw in merged.items():
        errors: list[str] = []
        entry = TARGET.validate(raw, name, errors)
        if errors:
            raise RenderError("templates/manifest.toml: " + "; ".join(errors))
        if not entry["enabled"]:
            continue
        targets.append(Target(
            name=name,
            template=entry["template"],
            path=Path(entry["target"].format(config_home=paths.config_home, config_dir=paths.config_dir,
                                             home=Path.home())).expanduser(),
            process=entry["process"], signal=entry["signal"], reload=entry["reload"],
            env=entry["env"], terminal=entry["terminal"], mode=int(entry["mode"], 8),
            vars=entry["vars"],
        ))
    return targets


# --------------------------------------------------------------------------- context
def context(settings: Settings) -> dict[str, Any]:
    """Everything a template can use. See docs/CUSTOMIZING.md for the list."""
    cfg, theme = settings.config, settings.theme
    lite = cfg["performance"]["profile"] == "lite"
    motion = not lite and not cfg["behavior"]["reduce_motion"]
    term = theme["colors"]["terminal"]
    slots = [term[f"color{i}"] for i in range(16)]

    def ansi(color: Color) -> int:
        """Index (0-15) of the terminal color closest to color. Configs that must also work on
        the Linux console use these, so they follow whatever palette the console has."""
        return min(range(16), key=lambda i: slots[i].distance(color))

    roles = ("primary", "secondary", "glow", "text", "dim", "warning")
    return {
        "theme": theme,
        "c": theme["colors"],
        "t": theme["colors"]["terminal"],
        "fonts": theme["fonts"],
        "style": theme["style"],
        "sound": cfg["sound"],
        "sound_on": [e for e, v in cfg["sound"]["events"].items() if cfg["sound"]["enabled"] and v["enabled"]],
        "widgets": cfg["widgets"],
        "decor": cfg["decor"],
        "behavior": cfg["behavior"],
        "performance": cfg["performance"],
        "effects": {
            "blur": theme["style"]["blur"] and not lite,
            "shadows": theme["style"]["glow"] > 0 and not lite,
            "animations": motion,
            "lite": lite,
        },
        "ansi": ansi,
        "ansi_roles": {r: ansi(theme["colors"][r]) for r in roles},
        "keybinds": settings.keybinds,
        "binds": kbmod.binds(settings.keybinds),
        "keymap": kbmod.essentials(settings.keybinds),
        "version": __version__,
    }


def _ms(base: float, ctx: dict) -> int:
    """An animation duration scaled by behavior.animation_speed (0 when motion is off)."""
    if not ctx["effects"]["animations"]:
        return 0
    return max(1, round(base / ctx["behavior"]["animation_speed"]))


def _plain(value: Any) -> Any:
    """Context -> JSON-able data (colors become '#rrggbb')."""
    if isinstance(value, Color):
        return value.hex
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


_BASE = ("black", "red", "green", "yellow", "blue", "magenta", "cyan", "white")
# How apps spell the 16 terminal colors. "basic" folds bright colors onto the 8 base names.
_ANSI_NAMES = {
    "plain": [*_BASE, *(f"bright_{n}" for n in _BASE)],                     # fastfetch, rich
    "starship": [*_BASE, *(f"bright-{n}" for n in _BASE)],
    "textual": [f"ansi_{n}" for n in _BASE] + [f"ansi_bright_{n}" for n in _BASE],
    "ratatui": [*_BASE[:7], "gray", "darkgray",                                # yazi
                *(f"light{n}" for n in _BASE[1:7]), "white"],
    "basic": [*_BASE, *_BASE],                                                  # lazygit, cava
}


def ansi_name(index: int, flavor: str = "plain") -> str:
    return _ANSI_NAMES[flavor][index]


def sgr(index: int | None = None, bold: bool = False) -> str:
    """Escape sequence for palette foreground color `index` (None: reset)."""
    if index is None:
        return "\033[0m"
    code = 30 + index if index < 8 else 82 + index
    return f"\033[{'1;' if bold else ''}{code}m"


def lua_string(value: str) -> str:
    """A Lua string literal."""
    out = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{out}"'


_SWAY_MODS = {"SUPER": "Mod4", "SHIFT": "Shift", "CTRL": "Control", "ALT": "Mod1"}


def hypr_combo(combo: str) -> str:
    """'SUPER+SHIFT+Return' -> 'SUPER + SHIFT + Return' (Hyprland's Lua bind syntax)."""
    return " + ".join(combo.split("+"))


def sway_combo(combo: str) -> str:
    """'SUPER+SHIFT+Q' -> 'Mod4+Shift+q'. Sway matches keysyms by case and "Q" is shift+q."""
    *mods, key = combo.split("+")
    return "+".join([*(_SWAY_MODS[m] for m in mods), key.lower() if len(key) == 1 else key])


def environment(paths: Paths) -> jinja2.Environment:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader([str(p) for p in paths.templates]),
        undefined=jinja2.StrictUndefined,  # a typo in a template is an error, not an empty string
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
    )
    env.filters["json"] = lambda v, indent=2: json.dumps(_plain(v), indent=indent, sort_keys=True)
    env.filters["tf"] = lambda v: "true" if v else "false"
    env.filters["lua"] = lua_string
    env.filters["hypr_combo"] = hypr_combo
    env.filters["sway_combo"] = sway_combo
    env.globals["Color"] = Color
    env.globals["ansi_name"] = ansi_name
    env.globals["sgr"] = sgr
    return env


def header(template: str, prefix: str, suffix: str = "") -> str:
    """The 'generated, don't edit' comment, in the target's comment syntax."""
    end = f" {suffix}" if suffix else ""
    return (f"{prefix} Generated by nullgrid from {template}. Do not edit: changes are overwritten.{end}\n"
            f"{prefix} Customize ~/.config/nullgrid/nullgrid.toml or override the template instead.{end}")


def render_all(settings: Settings, paths: Paths, targets: list[Target]) -> dict[str, str]:
    env = environment(paths)
    ctx = context(settings)
    out = {}
    for t in targets:
        try:
            tpl = env.get_template(t.template)
            out[t.name] = tpl.render(ctx, header=functools.partial(header, t.template),
                                     ms=lambda base: _ms(base, ctx), **t.vars)
        except jinja2.TemplateNotFound:
            raise RenderError(f"{t.name}: template {t.template!r} not found") from None
        except jinja2.TemplateError as exc:
            where = f"{exc.filename}:{exc.lineno}" if getattr(exc, "lineno", None) else t.template
            raise RenderError(f"{t.name}: {where}: {exc.message}") from None
    return out


# --------------------------------------------------------------------------- writing
def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def read_state(paths: Paths) -> dict[str, str]:
    try:
        return json.loads(paths.state_file.read_text())
    except (OSError, ValueError):
        return {}


def check_drift(t: Target, state: dict[str, str]) -> str:
    """'missing' | 'edited' (changed since nullgrid wrote it) | 'foreign' (not ours) | 'ok'."""
    if not t.path.is_file():
        return "missing"
    current = _digest(t.path.read_text(errors="replace"))
    recorded = state.get(str(t.path))
    if recorded is None:
        return "foreign"
    return "ok" if recorded == current else "edited"


def apply(settings: Settings, paths: Paths, *, reload: str = "changed", dry_run: bool = False) -> Report:
    """Render and write every target. reload: 'changed' | 'all' | 'none'."""
    targets = load_manifest(paths)
    rendered = render_all(settings, paths, targets)
    state = read_state(paths)
    report = Report()
    for t in targets:
        text = rendered[t.name]
        old = t.path.read_text(errors="replace") if t.path.is_file() else None
        if old == text:
            report.unchanged.append(t)
            state[str(t.path)] = _digest(text)
            continue
        report.written.append(t)
        if dry_run:
            continue
        if old is not None and state.get(str(t.path)) != _digest(old):
            backup = t.path.with_name(t.path.name + ".bak")
            shutil.copy2(t.path, backup)
            report.backups.append(backup)
        atomic_write(t.path, text, t.mode)
        state[str(t.path)] = _digest(text)
    if dry_run:
        return report
    atomic_write(paths.state_file, json.dumps(state, indent=1, sort_keys=True) + "\n")

    to_reload = {"all": targets, "changed": report.written, "none": []}[reload]
    done: set[tuple] = set()  # e.g. the Hyprland theme and keys files share one `hyprctl reload`
    for t in to_reload:
        hook = (t.process, t.signal, tuple(t.reload))
        if t.reload and hook in done:
            continue
        done.add(hook)
        ok = run_reload(t)
        if ok is True:
            report.reloaded.append(t.name)
        elif ok is False:
            report.reload_failed.append(t.name)
    return report


# --------------------------------------------------------------------------- reloading
def _processes(name: str) -> list[int]:
    """PIDs of this user's processes whose name (comm) is name."""
    uid = os.getuid()
    pids = []
    for entry in os.scandir("/proc"):
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid != uid:
                continue
            with open(f"/proc/{entry.name}/comm") as fh:
                if fh.read().strip() == name:
                    pids.append(int(entry.name))
        except OSError:
            continue
    return pids


def _catches(pid: int, sig: int) -> bool:
    """Whether the process has a handler for sig. A process still starting up (or one that
    never handles it) would be killed by signals like SIGUSR1 or SIGHUP, so it's skipped."""
    try:
        with open(f"/proc/{pid}/status") as fh:
            for line in fh:
                if line.startswith("SigCgt:"):
                    return bool(int(line.split()[1], 16) >> (sig - 1) & 1)
    except (OSError, ValueError):
        pass
    return False


def _env_matches(spec: str) -> bool:
    if not spec:
        return True
    var, eq, want = spec.partition("=")
    value = os.environ.get(var)
    return value == want if eq else bool(value)


def run_reload(t: Target) -> bool | None:
    """True: reloaded. False: tried and failed. None: nothing to do (no hook, app not running)."""
    if not (t.signal or t.reload) or not _env_matches(t.env):
        return None
    pids = _processes(t.process) if t.process else []
    if t.process and not pids:
        return None
    if t.signal:
        try:
            sig = getattr(signals, f"SIG{t.signal}")
        except AttributeError:
            return False
        targets = [pid for pid in pids if _catches(pid, sig)]
        if not targets:
            return None  # only processes that would die of it (e.g. a kitty still starting)
        sent = False
        for pid in targets:
            try:
                os.kill(pid, sig)
                sent = True
            except OSError:
                pass
        return sent
    argv = [a.format(target=t.path) for a in t.reload]
    if shutil.which(argv[0]) is None:
        return None
    out = None if t.terminal else subprocess.DEVNULL
    try:
        # generous: the wallpaper hook renders an image per screen
        return subprocess.run(argv, stdout=out, stderr=out, timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False

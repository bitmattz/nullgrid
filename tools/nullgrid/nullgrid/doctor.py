"""`nullgrid doctor`: check the config, theme, templates and generated files."""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass

from . import config as cfgmod
from . import render
from .paths import Paths

OK, INFO, WARN, FAIL = "ok", "info", "warn", "FAIL"
MIN_CONTRAST = 4.5  # WCAG AA for body text


@dataclass
class Check:
    level: str
    message: str


def run(paths: Paths) -> list[Check]:
    out: list[Check] = []
    add = lambda level, msg: out.append(Check(level, msg))  # noqa: E731

    # -- config + theme -------------------------------------------------
    if paths.config_file.is_file():
        add(OK, f"config file {paths.config_file}")
    else:
        add(INFO, f"no {paths.config_file} yet; using defaults (any nullgrid command that changes settings creates it)")
    try:
        settings = cfgmod.load(paths)
    except cfgmod.ConfigError as exc:
        for p in exc.problems:
            add(FAIL, f"{exc.source}: {p}")
        return out
    add(OK, f"config valid; theme {settings.theme['meta']['name']!r} from {settings.preset_path}")

    for name, path in cfgmod.list_themes(paths).items():
        try:
            cfgmod.load_theme(path)
        except cfgmod.ConfigError as exc:
            add(WARN, f"theme {name!r} is broken and can't be selected: {'; '.join(exc.problems)}")

    if overrides := cfgmod.overrides_in_use(settings.config):
        add(INFO, f"{len(overrides)} theme value(s) overridden in your config: {', '.join(overrides)}")

    c = settings.theme["colors"]
    for fg, bg in (("text", "bg"), ("text", "surface"), ("primary", "bg"), ("dim", "bg")):
        ratio = c[fg].contrast(c[bg])
        need = 3.0 if fg in ("primary", "dim") else MIN_CONTRAST
        if ratio < need:
            add(WARN, f"low contrast: colors.{fg} on colors.{bg} is {ratio:.1f}:1 (want at least {need}:1)")

    # -- templates + generated files ------------------------------------
    try:
        targets = render.load_manifest(paths)
        render.render_all(settings, paths, targets)
    except render.RenderError as exc:
        add(FAIL, f"templates: {exc}")
        return out
    add(OK, f"{len(targets)} templates render")

    state = render.read_state(paths)
    stale = []
    for t in targets:
        drift = render.check_drift(t, state)
        if drift == "missing":
            stale.append(t.name)
        elif drift == "edited":
            add(WARN, f"{t.path} was edited by hand; the next reload backs it up to {t.path.name}.bak and replaces it")
        elif drift == "foreign":
            add(WARN, f"{t.path} wasn't written by nullgrid; the next reload backs it up and replaces it")
    if stale:
        add(WARN, f"not generated yet: {', '.join(stale)}. Run: nullgrid theme reload")
    else:
        try:
            pending = render.apply(settings, paths, dry_run=True).written
        except render.RenderError as exc:  # pragma: no cover - render_all already passed
            add(FAIL, str(exc))
            return out
        if pending:
            add(WARN, f"out of date: {', '.join(t.name for t in pending)}. Run: nullgrid theme reload")
        else:
            add(OK, "generated files are up to date")

    # -- environment ----------------------------------------------------
    fonts = settings.theme["fonts"]
    if shutil.which("fc-list"):
        try:
            installed = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True,
                                       timeout=10).stdout.lower()
        except (OSError, subprocess.TimeoutExpired):
            installed = None
        if installed is not None:
            for role in ("ui", "mono", "display"):
                if fonts[role].lower() not in installed:
                    add(WARN, f"font {fonts[role]!r} (fonts.{role}) is not installed")
    else:
        add(INFO, "fontconfig not installed; skipping the font check")

    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        add(OK, "running inside Hyprland")
    elif os.environ.get("WAYLAND_DISPLAY"):
        add(INFO, "running in a Wayland session other than Hyprland")
    else:
        add(INFO, "no graphical session (TTY mode or SSH)")
    return out


def exit_code(checks: list[Check]) -> int:
    return 1 if any(c.level == FAIL for c in checks) else 0

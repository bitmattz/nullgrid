"""`nullgrid doctor`: check the config, theme, templates and generated files."""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass

from . import config as cfgmod
from . import icons, render, sound, toolkit
from .paths import Paths

OK, INFO, WARN, FAIL = "ok", "info", "warn", "FAIL"
MIN_CONTRAST = 4.5  # WCAG AA for body text
ADW_GTK3 = "/usr/share/themes/adw-gtk3-dark/gtk-3.0/gtk.css"
PLYMOUTH_THEME = "/usr/share/plymouth/themes/nullgrid"


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

    # -- desktop ------------------------------------------------------------
    # A compositor config that doesn't load the generated files silently ignores every theme change.
    for app, main, needs in (("Hyprland", "hypr/hyprland.lua", ("nullgrid-theme.lua", "nullgrid-keys.lua")),
                             ("sway", "sway/config", ("nullgrid-theme", "nullgrid-keys"))):
        if not shutil.which(app):
            continue
        f = paths.config_home / main
        if not f.is_file():
            add(WARN, f"{f} is missing: {app} won't use the NULLGRID look or keybinds. Run: nullgrid init")
            continue
        text = f.read_text(errors="replace")
        if missing := [n for n in needs if n not in text]:
            add(WARN, f"{f} doesn't load {' or '.join(missing)}: theme and keybind changes won't reach {app}"
                      f" (compare with {paths.skel / '.config' / main})")
    status = paths.state_dir / "session-status"
    if status.is_file():
        lines = status.read_text(errors="replace").splitlines()
        failed = [l for l in lines if "could not start" in l or "stopped with" in l or "fell back" in l]
        for line in failed:
            add(WARN, f"last desktop start: {line}")
        if lines and not failed:
            add(OK, f"last desktop start: {lines[-1]}")
    if shutil.which("Hyprland") or shutil.which("sway"):
        for tool, pkg in (("swaybg", "swaybg"), ("rsvg-convert", "librsvg")):
            if not shutil.which(tool):
                add(WARN, f"{tool} not found (package {pkg}): no wallpaper")

    # -- GTK / Qt / icons / cursors -----------------------------------------
    if shutil.which("Hyprland") or shutil.which("sway"):
        _toolkit_checks(paths, add)
    _boot_checks(add)

    # -- sound --------------------------------------------------------------
    snd = settings.config["sound"]
    where = sound.find_pack(paths, snd["pack"])
    if where is None:
        known = ", ".join(sound.list_packs(paths)) or "none installed"
        add(WARN, f"sound.pack: no sound pack named {snd['pack']!r} ({known}); no sounds")
    else:
        try:
            pack = sound.load_pack(where)
            add(OK, f"sound pack {pack.name!r}: {len(pack.sounds)} sounds" + ("" if snd["enabled"] else " (muted)"))
        except cfgmod.ConfigError as exc:
            for p in exc.problems:
                add(WARN, f"{exc.source}: {p}")
    if sound.player() is None:
        add(WARN, "no audio player (pw-play, paplay or aplay): no sounds. Install pipewire-audio")
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime and shutil.which("pipewire"):
        if os.path.exists(os.path.join(runtime, "pipewire-0")):
            add(OK, "PipeWire is running")
        else:
            add(WARN, "PipeWire is not running: no sound. Try: systemctl --user start pipewire wireplumber")
    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("nullgrid-sfx"):
        if sound.request("status", reply=True) is None:
            add(WARN, "the sound daemon is not running: desktop events make no sound. Start it: nullgrid-sfx daemon &")
        else:
            add(OK, "sound daemon running")

    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        add(OK, "running inside Hyprland")
    elif os.environ.get("WAYLAND_DISPLAY"):
        add(INFO, "running in a Wayland session other than Hyprland")
    else:
        add(INFO, "no graphical session (TTY mode or SSH)")
    return out


def _toolkit_checks(paths: Paths, add) -> None:
    if not os.path.isfile(ADW_GTK3):
        add(WARN, "GTK theme base missing (package adw-gtk-theme): GTK apps won't look like NULLGRID")
    try:
        spec = toolkit.load_spec(paths)
    except toolkit.ToolkitError:
        return  # reported above as "not generated yet"
    d = toolkit.theme_dir(paths)
    stamp = d / ".nullgrid-icons"
    if not stamp.is_file() or stamp.read_text().strip() != icons.stamp(spec):
        add(WARN, f"icon theme in {d} is missing or out of date. Run: nullgrid toolkit apply")
    elif not (d / "cursors" / "default").is_file():
        add(WARN, "cursors not generated (needs rsvg-convert, package librsvg). Run: nullgrid toolkit apply")
    else:
        add(OK, f"icon theme and cursors in {d}")
    if toolkit.settings_available() is None:
        current = toolkit.current_settings()
        differ = [key for name, key in toolkit.SETTINGS.items()
                  if name in spec and key in current and current[key] != toolkit._gvariant(spec[name])]
        if differ:
            add(WARN, f"GTK settings differ from nullgrid.toml: {', '.join(differ)}. Run: nullgrid toolkit apply")
        else:
            add(OK, "GTK settings (theme, icons, cursor, fonts) match")
    if os.environ.get("WAYLAND_DISPLAY"):
        if os.environ.get("QT_QPA_PLATFORMTHEME") != "qt6ct":
            add(WARN, "QT_QPA_PLATFORMTHEME is not qt6ct in this session: Qt apps won't follow the theme")
        elif not shutil.which("qt6ct"):
            add(WARN, "qt6ct is not installed: Qt apps won't follow the theme")


def _boot_checks(add) -> None:
    if not os.path.isdir(PLYMOUTH_THEME):
        return
    theme = ""
    for f in ("/etc/plymouth/plymouthd.conf", "/usr/share/plymouth/plymouthd.defaults"):
        try:
            for line in open(f):
                if line.strip().startswith("Theme="):
                    theme = line.strip().split("=", 1)[1]
        except OSError:
            continue
        if theme:
            break
    if theme != "nullgrid":
        add(INFO, f"boot splash is {theme or 'not set'!r}, not NULLGRID's. Set it: "
                  "sudo plymouth-set-default-theme -R nullgrid")


def exit_code(checks: list[Check]) -> int:
    return 1 if any(c.level == FAIL for c in checks) else 0

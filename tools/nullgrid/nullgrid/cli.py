"""The `nullgrid` command."""
from __future__ import annotations

import argparse
import difflib
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__, doctor, dotfiles
from . import config as cfgmod
from . import keybinds as kbmod
from . import paths as pathmod
from . import render
from . import wallpaper

# --------------------------------------------------------------------------- output
_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR") and os.environ.get("TERM") != "dumb"
_STYLE = {"ok": "36", "info": "2", "warn": "33", "FAIL": "1;31", "head": "1;36", "dim": "2"}


def paint(text: str, style: str) -> str:
    return f"\033[{_STYLE[style]}m{text}\033[0m" if _COLOR else text


def err(msg: str) -> None:
    print(paint("error:", "FAIL"), msg, file=sys.stderr)


class Fail(Exception):
    """A user-facing error: printed without a traceback, exit code 1."""


def print_report(report: render.Report, dry_run: bool = False) -> None:
    if not report.written:
        print("all generated files already up to date")
    else:
        verb = "would update" if dry_run else "updated"
        print(f"{verb} {len(report.written)} file(s): {', '.join(t.name for t in report.written)}")
    for b in report.backups:
        print(paint("note:", "warn"), f"{b.with_suffix('')} had hand edits; saved them to {b}")
    if report.reloaded:
        print(f"reloaded: {', '.join(report.reloaded)}")
    if report.reload_failed:
        print(paint("warn:", "warn"), f"reload failed for: {', '.join(report.reload_failed)}")


def apply(paths, reload: str = "changed", dry_run: bool = False) -> None:
    settings = cfgmod.load(paths)
    print_report(render.apply(settings, paths, reload=reload, dry_run=dry_run), dry_run)


# --------------------------------------------------------------------------- theme
def cmd_theme_list(args, paths) -> None:
    try:
        current = cfgmod.load(paths).theme["meta"]["name"]
    except cfgmod.ConfigError:
        current = None
    themes = cfgmod.list_themes(paths)
    if not themes:
        raise Fail("no themes found")
    width = max(map(len, themes))
    for name, path in themes.items():
        mark = paint("*", "head") if name == current else " "
        try:
            desc = cfgmod.load_theme(path)["meta"]["description"]
        except cfgmod.ConfigError:
            desc = paint("(broken: run nullgrid doctor)", "warn")
        user = paint(" [user]", "dim") if path.is_relative_to(paths.user_themes) else ""
        print(f"{mark} {name.ljust(width)}  {desc}{user}")


def set_theme(paths, name: str, *, reset_colors: bool = False, reload: bool = True) -> None:
    preset = cfgmod.find_theme(paths, name)
    if preset is None:
        names = list(cfgmod.list_themes(paths))
        hint = difflib.get_close_matches(name, names, n=1)
        raise Fail(f"no theme named {name!r}" + (f" (did you mean {hint[0]!r}?)" if hint else "")
                   + f". Available: {', '.join(names)}")
    cfgmod.load_theme(preset)  # refuse a broken preset before touching the config
    doc = cfgmod.ConfigDocument(paths)
    doc.set("theme.preset", name)
    if reset_colors:
        doc.remove("theme.colors")
    doc.save()
    print(f"theme: {name}")
    settings = cfgmod.load(paths)
    kept = [o for o in cfgmod.overrides_in_use(settings.config) if o.startswith("theme.colors.")]
    if kept:
        print(paint("note:", "warn"), f"your config still overrides {', '.join(kept)} "
              "(use --reset-colors to drop them)")
    print_report(render.apply(settings, paths, reload="changed" if reload else "none"))


def cmd_theme_set(args, paths) -> None:
    set_theme(paths, args.name, reset_colors=args.reset_colors, reload=not args.no_reload)


def cmd_theme_step(args, paths) -> None:
    """theme next / prev: cycle through the presets in `theme list` order."""
    names = [n for n, p in cfgmod.list_themes(paths).items() if _loads(p)]
    if not names:
        raise Fail("no themes found")
    current = cfgmod.load(paths).theme["meta"]["name"]
    step = 1 if args.action == "next" else -1
    i = names.index(current) + step if current in names else 0
    set_theme(paths, names[i % len(names)])


def _loads(theme_path) -> bool:
    try:
        cfgmod.load_theme(theme_path)
        return True
    except cfgmod.ConfigError:
        return False


def _editor() -> list[str]:
    for var in ("VISUAL", "EDITOR"):
        if value := os.environ.get(var):
            return shlex.split(value)
    for name in ("nvim", "nano", "vi"):
        if shutil.which(name):
            return [name]
    raise Fail("no editor found; set $EDITOR")


def cmd_theme_edit(args, paths) -> None:
    path = paths.config_file
    if not path.is_file():
        cfgmod.ConfigDocument(paths).save()
        print(f"created {path}")
    before = path.read_text()
    while True:
        subprocess.run([*_editor(), str(path)])
        try:
            cfgmod.load(paths)
            break
        except cfgmod.ConfigError as exc:
            print(exc.report(), file=sys.stderr)
            if not sys.stdin.isatty():
                cfgmod.atomic_write(path, before)
                raise Fail("the config has errors; your edit was reverted") from None
            answer = input("[e]dit again or [r]evert your changes? [E/r] ").strip().lower()
            if answer.startswith("r"):
                cfgmod.atomic_write(path, before)
                print("reverted")
                return
    if path.read_text() == before:
        print("no changes")
        return
    apply(paths)


def cmd_theme_reload(args, paths) -> None:
    apply(paths, reload="none" if args.dry_run else "all", dry_run=args.dry_run)


# --------------------------------------------------------------------------- keys / wallpaper
def cmd_keys(args, paths) -> None:
    settings = cfgmod.load(paths)
    kb = settings.keybinds
    rows = kbmod.summary(kb)
    width = max(len(r[0]) for r in rows)
    head = paint(f"keybinds: {kb['meta']['name']}", "head")
    if kb["meta"]["description"]:
        head += paint(f"  ({kb['meta']['description']})", "dim")
    print(head)
    for combo, label, _ in rows:
        print(f"  {paint(combo.ljust(width), 'ok')}  {label}")
    print(paint(f"\nchange them: copy {kbmod.find(paths, kb['meta']['name'])} to {paths.keybinds[0]}/<name>.toml,"
                " then set [behavior] keybinds = \"<name>\"", "dim"))
    if args.pause and sys.stdin.isatty():
        try:
            input(paint("\npress Enter to close ", "dim"))
        except (EOFError, KeyboardInterrupt):
            pass


def _size(text: str) -> tuple[int, int]:
    try:
        w, h = (int(v) for v in text.lower().split("x"))
        if 16 <= w <= 16384 and 16 <= h <= 16384:
            return w, h
    except ValueError:
        pass
    raise argparse.ArgumentTypeError(f"expected a size like 1920x1080, got {text!r}")


def _wallpaper_spec(paths) -> dict:
    try:
        return wallpaper.load_spec(paths)
    except wallpaper.WallpaperError:
        render.apply(cfgmod.load(paths), paths, reload="none")  # first run: generate it
        return wallpaper.load_spec(paths)


def cmd_wallpaper_render(args, paths) -> None:
    spec = _wallpaper_spec(paths)
    w, h = args.size
    svg = wallpaper.render(spec, w, h)
    if args.output is None:
        sys.stdout.write(svg)
    elif args.output.suffix == ".png":
        wallpaper.to_png(svg, args.output)
    else:
        cfgmod.atomic_write(args.output, svg)


def cmd_wallpaper_apply(args, paths) -> None:
    _wallpaper_spec(paths)
    for out, png in wallpaper.apply(paths):
        if not args.quiet:
            print(f"{out.name} {out.width}x{out.height}: {png}")


# --------------------------------------------------------------------------- widgets / mode
def cmd_widget_list(args, paths) -> None:
    widgets = cfgmod.load(paths).config["widgets"]
    width = max(map(len, widgets))
    for name, w in widgets.items():
        state = paint("on ", "ok") if w["visible"] else paint("off", "dim")
        print(f"{state}  {name.ljust(width)}  {w['position']}")


def cmd_widget_toggle(args, paths) -> None:
    names = list(cfgmod.WIDGETS.fields)
    if args.name not in names:
        hint = difflib.get_close_matches(args.name, names, n=1)
        raise Fail(f"no widget named {args.name!r}" + (f" (did you mean {hint[0]!r}?)" if hint else "")
                   + f". Widgets: {', '.join(names)}")
    visible = not cfgmod.load(paths).config["widgets"][args.name]["visible"]
    doc = cfgmod.ConfigDocument(paths)
    doc.set(f"widgets.{args.name}.visible", visible)
    doc.save()
    print(f"{args.name}: {'on' if visible else 'off'}")
    apply(paths)


def cmd_mode(args, paths) -> None:
    if args.mode is None:
        print(cfgmod.load(paths).config["behavior"]["default_mode"])
        return
    doc = cfgmod.ConfigDocument(paths)
    doc.set("behavior.default_mode", args.mode)
    doc.save()
    print(f"default mode: {args.mode} (takes effect at the next login)")
    apply(paths)


def cmd_doctor(args, paths) -> int:
    checks = doctor.run(paths)
    for c in checks:
        if c.level == doctor.INFO and not args.verbose:
            continue
        print(f"[{paint(c.level.center(4), c.level)}] {c.message}")
    code = doctor.exit_code(checks)
    problems = sum(c.level in (doctor.WARN, doctor.FAIL) for c in checks)
    print(paint("all good" if not problems else f"{problems} problem(s) found", "FAIL" if code else "head"))
    return code


# --------------------------------------------------------------------------- init
def cmd_init(args, paths) -> None:
    report = dotfiles.install(paths, overwrite=args.reset)
    if not paths.config_file.is_file():
        cfgmod.ConfigDocument(paths).save()
        report.copied.append(paths.config_file)
    settings = cfgmod.load(paths)
    result = render.apply(settings, paths)
    paths.init_marker.parent.mkdir(parents=True, exist_ok=True)
    paths.init_marker.touch()
    if args.quiet:
        return
    home = str(Path.home())
    for f in report.copied:
        print(f"  + {str(f).replace(home, '~', 1)}")
    if report.kept:
        print(paint(f"  kept {len(report.kept)} existing file(s) (--reset replaces them, saving .bak copies)", "dim"))
    print_report(result)


# --------------------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="nullgrid", description="Configure the NULLGRID desktop and terminal.")
    p.add_argument("--version", action="version", version=f"nullgrid {__version__}")
    sub = p.add_subparsers(dest="command", required=True, metavar="COMMAND")

    theme = sub.add_parser("theme", help="list, switch, edit and reload themes")
    tsub = theme.add_subparsers(dest="action", required=True, metavar="ACTION")
    tsub.add_parser("list", help="show available themes (* = active)").set_defaults(func=cmd_theme_list)
    s = tsub.add_parser("set", help="switch theme and restyle everything live")
    s.add_argument("name")
    s.add_argument("--reset-colors", action="store_true", help="drop your [theme.colors] overrides")
    s.add_argument("--no-reload", action="store_true", help="write the files but don't signal running apps")
    s.set_defaults(func=cmd_theme_set)
    tsub.add_parser("next", help="switch to the next theme in the list").set_defaults(func=cmd_theme_step)
    tsub.add_parser("prev", help="switch to the previous theme").set_defaults(func=cmd_theme_step)
    tsub.add_parser("edit", help="edit nullgrid.toml, validate it, apply it").set_defaults(func=cmd_theme_edit)
    r = tsub.add_parser("reload", help="regenerate every config and reload running apps")
    r.add_argument("--dry-run", action="store_true", help="only show which files would change")
    r.set_defaults(func=cmd_theme_reload)

    k = sub.add_parser("keys", help="list the desktop keybinds")
    k.add_argument("--pause", action="store_true", help="wait for Enter before exiting (for a popup window)")
    k.set_defaults(func=cmd_keys)

    wp = sub.add_parser("wallpaper", help="render the HUD wallpaper, or show it on every screen")
    wpsub = wp.add_subparsers(dest="action", required=True, metavar="ACTION")
    wr = wpsub.add_parser("render", help="write the wallpaper as SVG (or PNG) for one screen size")
    wr.add_argument("--size", type=_size, default=(1920, 1080), metavar="WxH", help="default 1920x1080")
    wr.add_argument("-o", "--output", type=Path, help="file to write (.svg or .png); default: SVG to stdout")
    wr.set_defaults(func=cmd_wallpaper_render)
    wa = wpsub.add_parser("apply", help="render for each screen of this session and show it (swaybg)")
    wa.add_argument("-q", "--quiet", action="store_true")
    wa.set_defaults(func=cmd_wallpaper_apply)

    widget = sub.add_parser("widget", help="show or hide desktop widgets")
    wsub = widget.add_subparsers(dest="action", required=True, metavar="ACTION")
    wsub.add_parser("list", help="show widgets and whether they're visible").set_defaults(func=cmd_widget_list)
    w = wsub.add_parser("toggle", help="show/hide a widget")
    w.add_argument("name")
    w.set_defaults(func=cmd_widget_toggle)

    m = sub.add_parser("mode", help="print or set the default session: desktop or tty")
    m.add_argument("mode", nargs="?", choices=("desktop", "tty"))
    m.set_defaults(func=cmd_mode)

    i = sub.add_parser("init", help="set up this home: default dotfiles, nullgrid.toml, generated configs")
    i.add_argument("--reset", action="store_true", help="also replace dotfiles you already have (.bak copies are kept)")
    i.add_argument("-q", "--quiet", action="store_true")
    i.set_defaults(func=cmd_init)

    d = sub.add_parser("doctor", help="check the system and config for problems")
    d.add_argument("-v", "--verbose", action="store_true", help="also show informational notes")
    d.set_defaults(func=cmd_doctor)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = pathmod.resolve()
    try:
        return args.func(args, paths) or 0
    except cfgmod.ConfigError as exc:
        print(exc.report(), file=sys.stderr)
        err("fix the problems above, or run: nullgrid doctor")
    except render.RenderError as exc:
        err(f"rendering failed, no files were changed: {exc}")
    except (Fail, wallpaper.WallpaperError) as exc:
        err(str(exc))
    except KeyboardInterrupt:
        return 130
    return 1

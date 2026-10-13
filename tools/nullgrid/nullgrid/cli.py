"""The `nullgrid` command."""
from __future__ import annotations

import argparse
import difflib
import os
import shlex
import shutil
import subprocess
import sys

from . import __version__, doctor
from . import config as cfgmod
from . import paths as pathmod
from . import render

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


def cmd_theme_set(args, paths) -> None:
    preset = cfgmod.find_theme(paths, args.name)
    if preset is None:
        names = list(cfgmod.list_themes(paths))
        hint = difflib.get_close_matches(args.name, names, n=1)
        raise Fail(f"no theme named {args.name!r}" + (f" (did you mean {hint[0]!r}?)" if hint else "")
                   + f". Available: {', '.join(names)}")
    cfgmod.load_theme(preset)  # refuse a broken preset before touching the config
    doc = cfgmod.ConfigDocument(paths)
    doc.set("theme.preset", args.name)
    if args.reset_colors:
        doc.remove("theme.colors")
    doc.save()
    print(f"theme: {args.name}")
    settings = cfgmod.load(paths)
    kept = [o for o in cfgmod.overrides_in_use(settings.config) if o.startswith("theme.colors.")]
    if kept:
        print(paint("note:", "warn"), f"your config still overrides {', '.join(kept)} "
              "(use --reset-colors to drop them)")
    print_report(render.apply(settings, paths, reload="none" if args.no_reload else "changed"))


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
    tsub.add_parser("edit", help="edit nullgrid.toml, validate it, apply it").set_defaults(func=cmd_theme_edit)
    r = tsub.add_parser("reload", help="regenerate every config and reload running apps")
    r.add_argument("--dry-run", action="store_true", help="only show which files would change")
    r.set_defaults(func=cmd_theme_reload)

    widget = sub.add_parser("widget", help="show or hide desktop widgets")
    wsub = widget.add_subparsers(dest="action", required=True, metavar="ACTION")
    wsub.add_parser("list", help="show widgets and whether they're visible").set_defaults(func=cmd_widget_list)
    w = wsub.add_parser("toggle", help="show/hide a widget")
    w.add_argument("name")
    w.set_defaults(func=cmd_widget_toggle)

    m = sub.add_parser("mode", help="print or set the default session: desktop or tty")
    m.add_argument("mode", nargs="?", choices=("desktop", "tty"))
    m.set_defaults(func=cmd_mode)

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
    except Fail as exc:
        err(str(exc))
    except KeyboardInterrupt:
        return 130
    return 1

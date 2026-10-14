"""`nullgrid-welcome`: the first-run wizard of an installed NULLGRID. Theme, sound pack, mode.

The first login on a console (the greeter's, or tty1) runs it once, before the session starts
(see /usr/share/nullgrid/zsh/nullgrid.zsh). Picking a theme applies it right away, so the
console or terminal around the wizard restyles as a preview; a highlighted sound pack plays a
sample. Run it again any time; or script it: nullgrid-welcome --theme NAME --sound PACK --mode tty
"""
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import ContentSwitcher, OptionList, Static
from textual.widgets.option_list import Option

from . import __version__

try:
    from nullgrid_dash.app import console_palette, load_theme, textual_theme, theme_path
except ImportError:  # pragma: no cover
    console_palette = load_theme = textual_theme = theme_path = None

NOTES = Path("/etc/nullgrid/install-notes")
MUTED = "(muted)"
MODES = [("desktop", "DESKTOP", "Hyprland with the HUD shell, dock, bar and widgets"),
         ("tty", "TERMINAL", "the console dashboard and terminal apps, no graphics")]
PAGES = [("theme", "THEME"), ("sound", "SOUND"), ("mode", "MODE"), ("done", "ONLINE")]


def state_file() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "nullgrid" / "welcomed"


def mark_done() -> None:
    f = state_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(f"nullgrid-welcome {__version__}\n")


def nullgrid(*args: str, quiet: bool = True) -> int:
    try:
        return subprocess.run(["nullgrid", *args], timeout=120,
                               stdout=subprocess.DEVNULL if quiet else None,
                               stderr=subprocess.DEVNULL if quiet else None).returncode
    except (OSError, subprocess.TimeoutExpired):
        return 1


# --------------------------------------------------------------------------- data
def themes() -> list[tuple[str, str, dict[str, str]]]:
    """(name, description, colors as #hex) of every theme, and which one is active."""
    from nullgrid import config as cfgmod, paths as ngpaths
    p = ngpaths.resolve()
    found = []
    for name, path in cfgmod.list_themes(p).items():
        try:
            theme = cfgmod.load_theme(path)
        except cfgmod.ConfigError:
            continue
        colors = {k: v.hex for k, v in theme["colors"].items() if k != "terminal"}
        found.append((name, theme["meta"]["description"], colors))
    return found


def current(key: str, default: str) -> str:
    from nullgrid import config as cfgmod, paths as ngpaths
    try:
        cfg = cfgmod.load(ngpaths.resolve()).config
    except cfgmod.ConfigError:
        return default
    section, _, name = key.partition(".")
    return str(cfg.get(section, {}).get(name, default))


def packs() -> list[tuple[str, str]]:
    from nullgrid import config as cfgmod, paths as ngpaths, sound
    found = []
    for name, where in sound.list_packs(ngpaths.resolve()).items():
        try:
            found.append((name, sound.load_pack(where).description))
        except cfgmod.ConfigError:
            continue
    return found


def apply(theme: str | None, pack: str | None, mode: str | None) -> list[str]:
    """Apply the choices with the nullgrid CLI; what failed."""
    failed = []
    if theme and nullgrid("theme", "set", theme):
        failed.append(f"theme {theme}")
    if pack == MUTED:
        if nullgrid("sound", "mute", "on"):
            failed.append("mute")
    elif pack:
        if nullgrid("sound", "set", pack) or nullgrid("sound", "mute", "off"):
            failed.append(f"sound pack {pack}")
    if mode and nullgrid("mode", mode):
        failed.append(f"mode {mode}")
    return failed


# --------------------------------------------------------------------------- the wizard
class WelcomeApp(App):
    CSS = """
    Screen { background: ansi_default; align: center middle; }
    #frame { width: 92; max-width: 100%; height: 26; max-height: 100%;
             border: solid $primary; border-title-color: $secondary; border-title-style: bold; padding: 0 2; }
    #top { height: 2; }
    .page { height: 1fr; }
    OptionList, OptionList:focus { border: solid $primary 40%; height: auto; max-height: 12; background: ansi_default; }
    OptionList:focus { border: solid $primary; }
    .side { width: 1fr; padding: 0 0 0 2; }
    .list { width: 34; }
    #help { height: 1; dock: bottom; }
    """
    BINDINGS = [
        Binding("escape,ctrl+q", "skip", "skip", priority=True),
        Binding("left", "back", "back", show=False),
    ]
    ENABLE_COMMAND_PALETTE = False

    def __init__(self, theme_list=None, pack_list=None, apply_fn=None, preview=True):
        super().__init__()
        self.theme_list = themes() if theme_list is None else theme_list
        self.pack_list = packs() if pack_list is None else pack_list
        self.apply_fn = apply_fn or apply
        self.preview = preview           # apply themes / play sounds while browsing
        self.choice = {"theme": current("theme.preset", "crimson-hud"),
                       "sound": current("sound.pack", "neural-link"), "mode": current("behavior.default_mode", "desktop")}
        if current("sound.enabled", "True") == "False":
            self.choice["sound"] = MUTED
        self.applied_theme = self.choice["theme"]
        self.page = 0
        self.ui = load_theme(theme_path()) if load_theme else None
        self._theme_mtime = self._mtime()
        self.failed: list[str] = []

    def style(self, role: str, bold: bool = False) -> str:
        return self.ui.style(role, bold) if self.ui else ("bold" if bold else "")

    def compose(self) -> ComposeResult:
        with Vertical(id="frame"):
            yield Static("", id="top")
            with ContentSwitcher(initial="theme", id="pages"):
                with Horizontal(id="theme", classes="page"):
                    yield OptionList(*[Option(n.upper(), id=n) for n, _, _ in self.theme_list],
                                     id="theme-list", classes="list")
                    yield Static("", id="theme-side", classes="side")
                with Horizontal(id="sound", classes="page"):
                    yield OptionList(*[Option(n.upper(), id=n) for n, _ in self.pack_list],
                                     Option("MUTED", id=MUTED), id="sound-list", classes="list")
                    yield Static("", id="sound-side", classes="side")
                with Horizontal(id="mode", classes="page"):
                    yield OptionList(*[Option(label, id=key) for key, label, _ in MODES],
                                     id="mode-list", classes="list")
                    yield Static("", id="mode-side", classes="side")
                with Vertical(id="done", classes="page"):
                    yield Static("", id="done-text")
            yield Static("", id="help")

    def on_mount(self) -> None:
        self._restyle()
        self.query_one("#frame").border_title = "NULLGRID // FIRST BOOT"
        for key, list_id in (("theme", "#theme-list"), ("sound", "#sound-list"), ("mode", "#mode-list")):
            lst = self.query_one(list_id, OptionList)
            ids = [lst.get_option_at_index(i).id for i in range(lst.option_count)]
            lst.highlighted = ids.index(self.choice[key]) if self.choice[key] in ids else 0
        self.show(0)
        self.set_interval(1, self._watch_theme)

    # -- look --------------------------------------------------------------------
    def _mtime(self) -> float:
        try:
            return theme_path().stat().st_mtime if theme_path else 0.0
        except OSError:
            return 0.0

    def _restyle(self) -> None:
        if self.ui is None:
            return
        self._gen = getattr(self, "_gen", 0) + 1
        name = f"nullgrid-{self._gen}"   # a new name forces Textual to restyle
        self.register_theme(textual_theme(self.ui, name))
        self.theme = name
        self.refresh_css()   # (otherwise rules computed before the switch keep the old colors)
        if os.environ.get("TERM") == "linux" and (seq := console_palette(self.ui)):
            try:
                with open("/dev/tty", "w") as tty:
                    tty.write(seq)
            except OSError:
                pass

    def _watch_theme(self) -> None:
        if (m := self._mtime()) != self._theme_mtime:
            self._theme_mtime = m
            self.ui = load_theme(theme_path())
            self._restyle()
            self.show(self.page)

    # -- pages -------------------------------------------------------------------
    def show(self, index: int) -> None:
        self.page = index
        key, title = PAGES[index]
        self.query_one("#pages", ContentSwitcher).current = key
        top = Text(no_wrap=True)
        for i, (_, name) in enumerate(PAGES):
            top.append(f" {i + 1:02d} {name} ", self.style("primary", True) if i == index else self.style("dim"))
            if i < len(PAGES) - 1:
                top.append("›", self.style("dim"))
        self.query_one("#top", Static).update(top)
        help_text = ("↑↓ choose   ENTER next   ← back   ESC skip" if key != "done" else "ENTER start   ← back")
        self.query_one("#help", Static).update(Text(help_text, self.style("dim")))
        if key == "done":
            self.query_one("#done-text", Static).update(self.done_text())
            self.query_one("#done-text").focus()
        else:
            lst = self.query_one(f"#{key}-list", OptionList)
            lst.focus()
            self.describe(key, lst)

    def describe(self, key: str, lst: OptionList) -> None:
        if lst.highlighted is None:
            return
        chosen = lst.get_option_at_index(lst.highlighted).id
        t = Text()
        if key == "theme":
            name, desc, colors = next(x for x in self.theme_list if x[0] == chosen)
            t.append(f"{name.upper()}\n", self.style("primary", True))
            t.append(f"{desc}\n\n", self.style("text"))
            for role in ("bg", "surface", "primary", "secondary", "glow", "text", "dim", "warning"):
                if role in colors:
                    t.append("████ ", colors[role])
                    t.append(f"{role}\n", self.style("dim"))
            t.append("\nENTER applies it everywhere right away.", self.style("dim"))
        elif key == "sound":
            desc = next((d for n, d in self.pack_list if n == chosen), "no sound effects at all")
            t.append(f"{chosen.upper()}\n", self.style("primary", True))
            t.append(f"{desc}\n\n", self.style("text"))
            if chosen != MUTED:
                t.append("A sample plays as you move through the list.", self.style("dim"))
        else:
            label, desc = next((lb, d) for k, lb, d in MODES if k == chosen)
            t.append(f"{label}\n", self.style("primary", True))
            t.append(f"{desc}\n\n", self.style("text"))
            t.append("Switch any time: nullgrid mode desktop|tty", self.style("dim"))
        self.query_one(f"#{key}-side", Static).update(t)

    def done_text(self) -> Text:
        t = Text()
        t.append("OPERATOR ONLINE\n\n", self.style("primary", True))
        for key, label in (("theme", "THEME"), ("sound", "SOUND"), ("mode", "MODE")):
            t.append(f"  {label:<8}", self.style("dim"))
            t.append(f"{self.choice[key]}\n", self.style("text"))
        try:
            notes = NOTES.read_text().strip()
        except OSError:
            notes = ""
        if notes:
            t.append("\nFROM THE INSTALLER\n", self.style("warning", True))
            t.append(notes + "\n", self.style("text"))
        t.append("\nChange these later: nullgrid theme | sound | mode   (help: nullgrid --help)\n",
                 self.style("dim"))
        return t

    @on(OptionList.OptionHighlighted)
    def highlighted(self, event: OptionList.OptionHighlighted) -> None:
        key = PAGES[self.page][0]
        if event.option_list.id != f"{key}-list":
            return
        self.describe(key, event.option_list)
        if key == "sound" and self.preview and event.option.id != MUTED:
            self.play(event.option.id)

    @on(OptionList.OptionSelected)
    def selected(self, event: OptionList.OptionSelected) -> None:
        key = PAGES[self.page][0]
        self.choice[key] = event.option.id
        if key == "theme" and self.preview and event.option.id != self.applied_theme:
            self.applied_theme = event.option.id
            self.apply_theme(event.option.id)
        self.show(self.page + 1)

    @work(thread=True, exclusive=True, group="theme")
    def apply_theme(self, name: str) -> None:
        nullgrid("theme", "set", name)

    @work(thread=True, exclusive=True, group="sound")
    def play(self, pack: str) -> None:
        nullgrid("sound", "test", "notification", "--pack", pack)

    def on_key(self, event) -> None:
        if event.key == "enter" and PAGES[self.page][0] == "done":
            self.finish()

    def action_back(self) -> None:
        if self.page > 0:
            self.show(self.page - 1)

    def action_skip(self) -> None:
        mark_done()
        self.exit()

    def finish(self) -> None:
        theme = self.choice["theme"] if self.choice["theme"] != self.applied_theme or not self.preview else None
        self.failed = self.apply_fn(theme, self.choice["sound"], self.choice["mode"])
        mark_done()
        self.exit()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="nullgrid-welcome", description=__doc__.splitlines()[0])
    p.add_argument("--version", action="version", version=f"nullgrid-welcome {__version__}")
    p.add_argument("--theme", help="apply this theme without asking")
    p.add_argument("--sound", help=f"this sound pack ({MUTED!r} or 'muted' for none)")
    p.add_argument("--mode", choices=("desktop", "tty"))
    p.add_argument("--status", action="store_true", help="say whether the wizard has run for this user")
    args = p.parse_args(argv)
    if args.status:
        print("done" if state_file().exists() else "pending")
        return 0
    if args.theme or args.sound or args.mode:
        failed = apply(args.theme, MUTED if args.sound == "muted" else args.sound, args.mode)
        mark_done()
        for f in failed:
            print(f"nullgrid-welcome: could not set {f} (see: nullgrid doctor)")
        return 1 if failed else 0
    app = WelcomeApp()
    app.run()
    for f in app.failed:
        print(f"nullgrid-welcome: could not set {f} (see: nullgrid doctor)")
    return 0

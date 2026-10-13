"""The `nullgrid-dash` TUI: CPU, memory, network, system panels and an app launcher.

Colors are terminal palette slots taken from the theme engine's theme.json ("ansi" roles), so
the dashboard matches the theme in kitty and on the Linux console alike, and restyles live when
`nullgrid theme set` rewrites that file.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.theme import Theme
from textual.widgets import Static

from . import __version__, gfx
from .stats import Sampler, Snapshot

DEFAULT_ROLES = {"primary": 6, "secondary": 1, "glow": 9, "text": 15, "dim": 8, "warning": 3}
_BASE = ("black", "red", "green", "yellow", "blue", "magenta", "cyan", "white")
TEXTUAL_ANSI = [f"ansi_{n}" for n in _BASE] + [f"ansi_bright_{n}" for n in _BASE]


def theme_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "nullgrid" / "generated" / "theme.json"


@dataclass
class UiTheme:
    name: str = "default"
    roles: dict | None = None
    refresh_ms: int = 1000
    terminal: dict | None = None    # color0..color15 as '#rrggbb', for the console palette

    def slot(self, role: str) -> int:
        return (self.roles or DEFAULT_ROLES).get(role, DEFAULT_ROLES[role])

    def style(self, role: str, bold: bool = False) -> str:
        return ("bold " if bold else "") + f"color({self.slot(role)})"


def load_theme(path: Path) -> UiTheme:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return UiTheme(roles=dict(DEFAULT_ROLES))
    roles = {**DEFAULT_ROLES, **{k: int(v) for k, v in data.get("ansi", {}).items()}}
    return UiTheme(name=data.get("name", "custom"), roles=roles,
                   refresh_ms=int(data.get("refresh_ms", 1000)),
                   terminal=data.get("colors", {}).get("terminal"))


def textual_theme(ui: UiTheme, name: str) -> Theme:
    n = lambda role: TEXTUAL_ANSI[ui.slot(role)]  # noqa: E731
    return Theme(
        name=name, ansi=True, dark=True,
        primary=n("primary"), secondary=n("secondary"), accent=n("glow"),
        warning=n("warning"), error=n("secondary"), success="ansi_green",
        foreground="ansi_default", background="ansi_default", surface="ansi_default",
        panel="ansi_default", boost="ansi_default",
        # The same extra variables as Textual's own "ansi-dark" theme (its widgets need them).
        variables={
            "ansi-background": "ansi_default",
            "ansi-foreground": n("text"),
            "border-blurred": n("dim"),
            "block-cursor-foreground": "ansi_black",
            "block-cursor-background": n("primary"),
            "input-cursor-background": n("primary"),
            "input-cursor-foreground": "ansi_black",
            "input-cursor-text-style": "none",
            "input-selection-background": n("primary"),
            "input-selection-foreground": "ansi_black",
            "screen-selection-background": n("primary"),
            "screen-selection-foreground": "ansi_black",
            "footer-key-foreground": n("primary"),
        },
    )


def console_palette(ui: UiTheme) -> str:
    """Escape sequences that set the Linux console's 16 colors."""
    if not ui.terminal:
        return ""
    return "".join(f"\033]P{i:X}{ui.terminal[f'color{i}'].lstrip('#')}" for i in range(16)
                   if f"color{i}" in ui.terminal)


# --------------------------------------------------------------------------- launcher
@dataclass
class Entry:
    key: str
    label: str
    hint: str
    argv: list[str]
    pause: bool = False   # wait for Enter afterwards (for commands that print and exit)


def launcher_entries() -> list[Entry]:
    tty = os.environ.get("TERM") == "linux"
    cfg = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    candidates = [
        ("btop", "monitor", ["btop"], False),
        ("yazi", "files", ["yazi"], False),
        ("nvim", "editor", ["nvim"], False),
        ("lazygit", "git", ["lazygit"], False),
        ("cava", "audio viz", ["cava", "-p", f"{cfg}/cava/config-tty"] if tty else ["cava"], False),
        ("tmux", "sessions", ["tmux", "new-session", "-A", "-s", "main"], False),
        ("nmtui", "network", ["nmtui"], False),
        ("fastfetch", "sysinfo", ["fastfetch"], True),
    ]
    found = [c for c in candidates if shutil.which(c[2][0])]
    return [Entry(str(i), label, hint, argv, pause) for i, (label, hint, argv, pause) in enumerate(found, 1)]


# --------------------------------------------------------------------------- panels
def crop(text: Text, width: int) -> Text:
    """Cut every line to width (Textual would otherwise wrap long lines)."""
    lines = text.split("\n", allow_blank=True)
    for line in lines:
        line.truncate(width, overflow="crop")
    return Text("\n").join(lines)


class Panel(Static):
    """A bordered panel whose body is redrawn from the app's latest snapshot."""

    TITLE = ""

    def on_mount(self) -> None:
        self.border_title = self.TITLE

    def render(self) -> Text:
        app: Dashboard = self.app  # type: ignore[assignment]
        size = self.content_size
        if app.snap is None or size.width <= 0:
            return Text("")
        return crop(self.body(app.snap, app.ui, size.width, size.height, app.glyphs), size.width)

    def body(self, s: Snapshot, ui: UiTheme, w: int, h: int, g: gfx.Glyphs) -> Text:
        raise NotImplementedError


def _level(ui: UiTheme, fraction: float) -> str:
    return ui.style("secondary", bold=True) if fraction >= 0.85 else ui.style("primary")


def _meter(t: Text, ui: UiTheme, g: gfx.Glyphs, label: str, fraction: float, width: int, tail: str) -> None:
    t.append(f"{label:<6}", ui.style("dim"))
    t.append(gfx.bar(fraction, width, g), _level(ui, fraction))
    t.append(f" {tail}\n", ui.style("text"))


def _history(t: Text, ui: UiTheme, g: gfx.Glyphs, values, w: int, rows: int, interval_ms: int) -> None:
    """A labelled percent-history graph filling `rows` lines (needs at least 3)."""
    span = min(len(values), w) * interval_ms // 1000
    t.append("\nHISTORY ", ui.style("dim"))
    t.append(f"{span}s\n", ui.style("text"))
    for line in gfx.graph(list(values), w, rows - 2, 100, g):
        t.append(line + "\n", ui.style("primary"))


class CpuPanel(Panel):
    TITLE = "CPU"

    def body(self, s, ui, w, h, g):
        t = Text(no_wrap=True, overflow="crop")
        _meter(t, ui, g, "TOTAL", s.cpu / 100, max(4, w - 13), f"{s.cpu:5.1f}%")
        t.append("LOAD  ", ui.style("dim"))
        t.append(" ".join(f"{x:.2f}" for x in s.load), ui.style("text"))
        t.append("  CORES ", ui.style("dim"))
        t.append(str(len(s.cores)), ui.style("text"))
        if s.temp is not None:
            t.append("  TEMP ", ui.style("dim"))
            t.append(f"{s.temp:.0f}C", _level(ui, s.temp / 100))
        t.append("\n")
        rows = h - 3
        if rows <= 0:
            return t
        t.append("\n")
        cols = math.ceil(len(s.cores) / rows)
        rows = math.ceil(len(s.cores) / cols)  # rows actually needed
        cell = w // max(1, cols)
        label = len(str(len(s.cores) - 1)) + 1
        bar_w = max(3, cell - label - 7)
        for r in range(min(rows, len(s.cores))):
            for c in range(cols):
                i = c * rows + r
                if i >= len(s.cores):
                    break
                pct = s.cores[i]
                t.append(f"C{i:<{label}}", ui.style("dim"))
                t.append(gfx.bar(pct / 100, bar_w, g), _level(ui, pct / 100))
                t.append(f" {pct:3.0f}% ".ljust(cell - label - bar_w), ui.style("text"))
            t.append("\n")
        if (spare := h - 3 - rows) >= 4:
            app: Dashboard = self.app  # type: ignore[assignment]
            _history(t, ui, g, app.sampler.cpu_hist, w, spare, ui.refresh_ms)
        return t


class MemPanel(Panel):
    TITLE = "MEMORY"

    def body(self, s, ui, w, h, g):
        t = Text(no_wrap=True, overflow="crop")
        bar_w = max(4, w - 11)
        ram = s.mem_used / s.mem_total if s.mem_total else 0
        _meter(t, ui, g, "RAM", ram, bar_w, f"{ram * 100:3.0f}%")
        t.append(f"      {gfx.human_bytes(s.mem_used)} / {gfx.human_bytes(s.mem_total)}\n\n", ui.style("text"))
        if s.swap_total:
            sw = s.swap_used / s.swap_total
            _meter(t, ui, g, "SWAP", sw, bar_w, f"{sw * 100:3.0f}%")
        else:
            t.append("SWAP  ", ui.style("dim"))
            t.append("none\n", ui.style("text"))
        disk = s.disk_used / s.disk_total if s.disk_total else 0
        _meter(t, ui, g, "DISK", disk, bar_w, f"{disk * 100:3.0f}%")
        t.append(f"      {gfx.human_bytes(s.disk_used)} / {gfx.human_bytes(s.disk_total)}\n", ui.style("text"))
        if (spare := h - 6) >= 4:
            app: Dashboard = self.app  # type: ignore[assignment]
            _history(t, ui, g, app.sampler.mem_hist, w, spare, ui.refresh_ms)
        return t


class NetPanel(Panel):
    TITLE = "NETWORK"

    def body(self, s, ui, w, h, g):
        app: Dashboard = self.app  # type: ignore[assignment]
        t = Text(no_wrap=True, overflow="crop")
        down, up = list(app.sampler.down_hist), list(app.sampler.up_hist)
        t.append("▼ DOWN ", ui.style("primary", bold=True))
        t.append(f"{gfx.human_bytes(s.down, rate=True):<10}", ui.style("text"))
        t.append("▲ UP ", ui.style("secondary", bold=True))
        t.append(f"{gfx.human_bytes(s.up, rate=True):<10}", ui.style("text"))
        top = gfx.nice_top(max(down[-w:] + up[-w:] + [1024]))
        t.append(f"SCALE {gfx.human_bytes(top, rate=True)}\n", ui.style("dim"))
        rows = h - 1
        if rows < 2:
            return t
        hd = (rows + 1) // 2
        for line in gfx.graph(down, w, hd, top, g):
            t.append(line + "\n", ui.style("primary"))
        for line in reversed(gfx.graph(up, w, rows - hd, top, g)):  # mirrored below the axis
            t.append(line + "\n", ui.style("secondary"))
        return t


class SysPanel(Panel):
    TITLE = "SYSTEM"

    def body(self, s, ui, w, h, g):
        t = Text(no_wrap=True, overflow="crop")

        def row(key: str, value: str, style: str | None = None) -> None:
            t.append(f"{key:<8}", ui.style("dim"))
            t.append(value + "\n", style or ui.style("text"))

        row("NODE", s.host.upper(), ui.style("primary", bold=True))
        row("KERNEL", s.kernel)
        row("UPTIME", gfx.duration(s.uptime))
        if s.battery:
            pct, plugged = s.battery
            row("POWER", f"{pct:.0f}% {'AC' if plugged else 'BATTERY'}",
                ui.style("secondary", bold=True) if pct < 15 and not plugged else None)
        else:
            row("POWER", "AC")
        row("THEME", ui.name)
        return t


class Header(Static):
    def render(self) -> Text:
        app: Dashboard = self.app  # type: ignore[assignment]
        ui, w = app.ui, self.size.width
        left = " NULLGRID // OPERATOR CONSOLE "
        right = f" {time.strftime('%Y-%m-%d %H:%M:%S')} "
        t = Text(no_wrap=True, overflow="crop")
        t.append(left, ui.style("primary", bold=True))
        t.append(app.glyphs.rule * max(0, w - len(left) - len(right)), ui.style("dim"))
        t.append(right, ui.style("text"))
        return t


class Launcher(Static):
    def on_mount(self) -> None:
        self.border_title = "LAUNCH"

    def render(self) -> Text:
        app: Dashboard = self.app  # type: ignore[assignment]
        ui, w = app.ui, max(1, self.content_size.width)
        items = [(e.key, e.label.upper(), e.hint) for e in app.entries]
        items += [("t", "THEME", "next"), ("p", "POWER", "menu"), ("q", "SHELL", "exit")]
        t = Text(no_wrap=True, overflow="crop")
        used = 0
        for key, label, hint in items:
            chunk = len(key) + len(label) + len(hint) + 6
            if used and used + chunk > w:
                t.append("\n")
                used = 0
            t.append(f"[{key}] ", ui.style("secondary", bold=True))
            t.append(label, ui.style("primary", bold=True))
            t.append(f" {hint}   ", ui.style("dim"))
            used += chunk
        return t


class PowerScreen(ModalScreen):
    BINDINGS = [
        Binding("o", "power('poweroff')", "power off"),
        Binding("r", "power('reboot')", "reboot"),
        Binding("escape,n,q,p", "app.pop_screen", "cancel"),
    ]
    DEFAULT_CSS = """
    PowerScreen { align: center middle; }
    #power { width: 46; height: auto; border: solid $secondary; padding: 1 2; }
    """

    def compose(self) -> ComposeResult:
        ui: UiTheme = self.app.ui  # type: ignore[attr-defined]
        t = Text()
        t.append("POWER\n\n", ui.style("secondary", bold=True))
        for key, label in (("o", "power off"), ("r", "reboot"), ("esc", "cancel")):
            t.append(f"[{key}] ", ui.style("secondary", bold=True))
            t.append(f"{label}\n", ui.style("text"))
        yield Static(t, id="power")

    def action_power(self, what: str) -> None:
        self.app.power_action = what  # type: ignore[attr-defined]
        self.app.exit()


# --------------------------------------------------------------------------- app
class Dashboard(App):
    CSS = """
    Screen { background: ansi_default; layout: vertical; }
    Header { height: 1; }
    .row { height: 1fr; }
    Panel, Launcher {
        border: solid $primary;
        border-title-color: $secondary;
        border-title-style: bold;
        padding: 0 1;
        height: 100%;
        scrollbar-size: 0 0;
    }
    #cpu, #net { width: 2fr; }
    #mem, #sys { width: 1fr; }
    Launcher { height: auto; }
    """
    BINDINGS = [
        Binding("q,s,escape", "quit", "shell"),
        Binding("p", "power", "power"),
        Binding("t", "next_theme", "theme"),
        *(Binding(str(i), f"launch('{i}')", show=False) for i in range(1, 10)),
    ]
    ENABLE_COMMAND_PALETTE = False

    def __init__(self, theme_file: Path | None = None):
        super().__init__()
        self.theme_file = theme_file or theme_path()
        self.ui = load_theme(self.theme_file)
        self._theme_mtime = self._mtime()
        self._theme_gen = 0
        self.glyphs = gfx.CONSOLE if os.environ.get("TERM") == "linux" else gfx.DESKTOP
        self.sampler = Sampler()
        self.snap: Snapshot | None = None
        self.entries = launcher_entries()
        self.power_action: str | None = None
        self._timer = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(classes="row"):
            yield CpuPanel(id="cpu")
            yield MemPanel(id="mem")
        with Horizontal(classes="row"):
            yield NetPanel(id="net")
            yield SysPanel(id="sys")
        yield Launcher(id="launch")

    def on_mount(self) -> None:
        self._apply_theme()
        self.tick()
        self._timer = self.set_interval(self.ui.refresh_ms / 1000, self.tick)
        self.set_interval(1, self._clock)

    def _mtime(self) -> float:
        try:
            return self.theme_file.stat().st_mtime
        except OSError:
            return 0.0

    def _apply_theme(self) -> None:
        self._theme_gen += 1
        name = f"nullgrid-{self._theme_gen}"  # a new name forces Textual to restyle
        self.register_theme(textual_theme(self.ui, name))
        self.theme = name
        if os.environ.get("TERM") == "linux" and (seq := console_palette(self.ui)):
            try:
                with open("/dev/tty", "w") as tty:
                    tty.write(seq)
            except OSError:
                pass

    def _clock(self) -> None:
        self.query_one(Header).refresh()
        if (m := self._mtime()) != self._theme_mtime:
            self._theme_mtime = m
            old_refresh = self.ui.refresh_ms
            self.ui = load_theme(self.theme_file)
            self._apply_theme()
            if self.ui.refresh_ms != old_refresh and self._timer:
                self._timer.stop()
                self._timer = self.set_interval(self.ui.refresh_ms / 1000, self.tick)
            self.refresh(layout=True)
            for w in self.query(Static):
                w.refresh()

    def tick(self) -> None:
        self.snap = self.sampler.sample()
        for panel in self.query(Panel):
            panel.refresh()

    def action_launch(self, key: str) -> None:
        entry = next((e for e in self.entries if e.key == key), None)
        if entry is None:
            return
        with self.suspend():
            print("\033[2J\033[H", end="", flush=True)
            try:
                subprocess.run(entry.argv)
            except OSError as exc:
                print(f"could not start {entry.label}: {exc}")
                entry.pause = True
            if entry.pause:
                input("\n  press Enter to return to the dashboard ")
        self.refresh(layout=True)

    def action_next_theme(self) -> None:
        try:
            out = subprocess.run(["nullgrid", "theme", "list"], capture_output=True, text=True,
                                 timeout=20, env={**os.environ, "NO_COLOR": "1"}).stdout
        except (OSError, subprocess.TimeoutExpired):
            return
        names, current = [], None
        for line in out.splitlines():
            if not line.strip():
                continue
            active, name = line.startswith("*"), line[1:].split()[0]
            names.append(name)
            current = name if active else current
        if not names:
            return
        nxt = names[(names.index(current) + 1) % len(names)] if current in names else names[0]
        subprocess.run(["nullgrid", "theme", "set", nxt], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=60)
        self._clock()

    def action_power(self) -> None:
        self.push_screen(PowerScreen())


def check() -> int:
    """Sample twice and print a summary: a headless smoke test of the data side."""
    sampler = Sampler()
    sampler.sample()
    time.sleep(0.5)
    s = sampler.sample()
    ui = load_theme(theme_path())
    print(f"theme={ui.name} cores={len(s.cores)} cpu={s.cpu:.0f}% "
          f"mem={gfx.human_bytes(s.mem_used)}/{gfx.human_bytes(s.mem_total)} "
          f"disk={s.disk_used * 100 // max(1, s.disk_total)}% down={gfx.human_bytes(s.down, True)} "
          f"apps={','.join(e.label for e in launcher_entries())}")
    print("DASH_OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="nullgrid-dash", description=__doc__.splitlines()[0])
    p.add_argument("--version", action="version", version=f"nullgrid-dash {__version__}")
    p.add_argument("--check", action="store_true", help="print one sample and exit (no UI)")
    args = p.parse_args(argv)
    if args.check:
        return check()
    app = Dashboard()
    app.run()
    if app.power_action:
        os.execvp("systemctl", ["systemctl", app.power_action])
    return 0

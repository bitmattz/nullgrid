"""The installer TUI (Textual): welcome, disk, account, region, drivers, confirm, install.

Colors are terminal palette slots (like nullgrid-dash), and every glyph is one the Terminus
console font has, so it looks the same in kitty and on a bare Linux console.
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Checkbox, ContentSwitcher, Input, OptionList, RichLog, Select, Static
from textual.widgets.option_list import Option

from . import __version__, hw, options
from . import config as cfgmod
from .cli import LOG, build_installer, make_logger
from .install import InstallError, System

try:
    from nullgrid_dash.app import UiTheme, load_theme, textual_theme, theme_path
except ImportError:  # pragma: no cover - nullgrid-dash is a dependency of the package
    UiTheme = load_theme = textual_theme = theme_path = None

PAGES = [("welcome", "START"), ("disk", "DISK"), ("account", "ACCOUNT"), ("region", "REGION"),
         ("drivers", "DRIVERS"), ("confirm", "CONFIRM"), ("install", "INSTALL")]
SEGMENTS = 40


class NgCheckbox(Checkbox):
    BUTTON_LEFT = "["
    BUTTON_RIGHT = "]"
    BUTTON_INNER = "■"


def seg_bar(fraction: float, width: int) -> str:
    full = round(max(0.0, min(1.0, fraction)) * width)
    return "■" * full + "·" * (width - full)


def read_kv(path: Path, key: str, default: str) -> str:
    try:
        for line in path.read_text().splitlines():
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip().strip('"') or default
    except OSError:
        pass
    return default


class Steps(Static):
    """The step list on the left; the current one highlighted."""

    def render(self) -> Text:
        app: InstallerApp = self.app  # type: ignore[assignment]
        t = Text(no_wrap=True)
        for i, (key, title) in enumerate(PAGES):
            mark = "►" if i == app.page else ("■" if i < app.page else "·")
            style = app.style("primary", True) if i == app.page else app.style("text" if i < app.page else "dim")
            t.append(f" {mark} {i + 1:02d} {title}\n", style)
        return t


class InstallerApp(App):
    CSS = """
    Screen { background: ansi_default; }
    #top { height: 1; }
    #body { height: 1fr; }
    #steps { width: 18; border: solid $primary; border-title-color: $secondary; padding: 1 0; }
    #main { border: solid $primary; border-title-color: $secondary; border-title-style: bold; padding: 0 2; }
    .page { height: auto; }
    .label { color: $secondary; text-style: bold; margin-top: 1; }
    .hint { color: $foreground 60%; }
    Input, Input:focus, SelectCurrent, Select:focus > SelectCurrent { border: solid $primary 40%; }
    Input:focus, Select:focus > SelectCurrent { border: solid $primary; }
    SelectOverlay, SelectOverlay:focus { border: solid $primary; }
    OptionList, OptionList:focus { border: solid $primary 40%; height: auto; max-height: 12; }
    OptionList:focus { border: solid $primary; }
    NgCheckbox, NgCheckbox:focus { border: none; padding: 0; margin-top: 1; background: ansi_default; }
    #nav { height: 3; dock: bottom; }
    #error { width: 1fr; color: $secondary; text-style: bold; padding: 1 2 0 2; }
    Button, Button:focus, Button:hover { border: solid $primary 40%; min-width: 12; height: 3; background: ansi_default; }
    Button:focus { border: solid $primary; text-style: bold; }
    #progress { height: 3; padding-top: 1; }
    #log { height: 1fr; min-height: 8; border: solid $primary 40%; background: ansi_default; }
    """
    BINDINGS = [Binding("ctrl+q", "quit_installer", "quit", priority=True)]
    ENABLE_COMMAND_PALETTE = False

    def __init__(self, disks=None, gpus=None, firmware=None, installer_factory=None):
        super().__init__()
        self.ui = load_theme(theme_path()) if load_theme else None
        self.disks = hw.list_disks() if disks is None else disks
        self.gpus = hw.list_gpus() if gpus is None else gpus
        self.firmware = firmware or hw.firmware()
        self.factory = installer_factory or build_installer
        self.cfg = cfgmod.InstallConfig(
            locale=read_kv(Path("/etc/locale.conf"), "LANG", "en_US.UTF-8"),
            keyboard=read_kv(Path("/etc/vconsole.conf"), "KEYMAP", "us"),
            timezone=options.current_timezone())
        if options.keyboard(self.cfg.keyboard) is None:
            self.cfg.keyboard = "us"
        self.locales = options.locales()
        if self.cfg.locale not in self.locales:   # the live ISO runs C.UTF-8
            self.cfg.locale = "en_US.UTF-8" if "en_US.UTF-8" in self.locales else self.locales[0]
        self.page = 0
        self.installing = False
        self.result: str | None = None   # "reboot" when the user asked for it at the end
        self.notes: list[str] = []

    # -- look ------------------------------------------------------------------
    def style(self, role: str, bold: bool = False) -> str:
        if self.ui is None:
            return "bold" if bold else ""
        return self.ui.style(role, bold)

    def on_mount(self) -> None:
        if self.ui is not None:
            self.register_theme(textual_theme(self.ui, "nullgrid"))
            self.theme = "nullgrid"
        self.query_one("#steps").border_title = "STEPS"
        self.show_page(0)

    # -- layout ----------------------------------------------------------------
    def compose(self) -> ComposeResult:
        yield Static(self.top_line(), id="top")
        with Horizontal(id="body"):
            yield Steps(id="steps")
            with Vertical(id="main"):
                with ContentSwitcher(initial="welcome", id="pages"):
                    yield from self.pages()
                with Horizontal(id="nav"):
                    yield Static("", id="error")
                    yield Button("< BACK", id="back")
                    yield Button("NEXT >", id="next")

    def top_line(self) -> Text:
        t = Text(no_wrap=True)
        t.append(" NULLGRID // SYSTEM INSTALL ", self.style("primary", True))
        t.append(f"v{__version__}  ", self.style("dim"))
        t.append(f"FIRMWARE {self.firmware.upper()}", self.style("text"))
        return t

    def pages(self) -> ComposeResult:
        cfg = self.cfg
        with VerticalScroll(id="welcome", classes="page"):
            yield Static(self.welcome_text(), id="welcome-text")
        with VerticalScroll(id="disk", classes="page"):
            yield Static("TARGET DISK", classes="label")
            yield Static("NULLGRID takes the whole disk: everything on it is erased.", classes="hint")
            yield OptionList(*[Option(Text(d.label + (f"  [{d.busy}]" if d.busy else "")), id=d.path,
                                      disabled=bool(d.busy)) for d in self.disks] or
                             [Option("no disk found", disabled=True)], id="disk-list")
            yield NgCheckbox("ENCRYPT THE DISK (LUKS2: the passphrase is asked at every boot)", cfg.encrypt, id="encrypt")
            yield Input(placeholder="passphrase", password=True, id="passphrase", disabled=not cfg.encrypt)
            yield Input(placeholder="passphrase again", password=True, id="passphrase2", disabled=not cfg.encrypt)
        with VerticalScroll(id="account", classes="page"):
            yield Static("OPERATOR", classes="label")
            yield Input(cfg.fullname, placeholder="full name (optional)", id="fullname")
            yield Input(cfg.username, placeholder="user name (e.g. ada)", id="username")
            yield Input(placeholder="password", password=True, id="password")
            yield Input(placeholder="password again", password=True, id="password2")
            yield Static("NODE", classes="label")
            yield Input(cfg.hostname, placeholder="hostname", id="hostname")
            yield Static("The user may run admin commands with sudo; root has no password.", classes="hint")
        with VerticalScroll(id="region", classes="page"):
            yield Static("KEYBOARD", classes="label")
            yield Select([(k.label, k.keymap) for k in options.KEYBOARDS], value=cfg.keyboard,
                         allow_blank=False, id="keyboard")
            yield Static("LANGUAGE (LOCALE)", classes="label")
            yield Select([(x, x) for x in self.locales], value=cfg.locale,
                         allow_blank=False, id="locale")
            yield Static("TIME ZONE", classes="label")
            zones = options.timezones()
            yield Select([(z, z) for z in zones], value=cfg.timezone if cfg.timezone in zones else "UTC",
                         allow_blank=False, id="timezone")
            yield Static("Type to jump in a list.", classes="hint")
        with VerticalScroll(id="drivers", classes="page"):
            yield Static(self.gpu_text(), id="gpu-text")
            yield Static("DRIVERS", classes="label")
            yield OptionList(*[Option(Text(self.driver_label(c)), id=c) for c in cfgmod.GPU_CHOICES], id="gpu-choice")
        with VerticalScroll(id="confirm", classes="page"):
            yield Static("", id="summary")
            yield Static("Type ERASE to install:", classes="label")
            yield Input(placeholder="ERASE", id="erase")
        with Vertical(id="install", classes="page"):
            yield Static("", id="progress")
            yield RichLog(id="log", wrap=True, markup=False, max_lines=400)

    # -- texts -----------------------------------------------------------------
    def welcome_text(self) -> Text:
        t = Text()
        t.append("\nINSTALL NULLGRID ON THIS MACHINE\n\n", self.style("primary", True))
        t.append("This copies the live system you are running to a disk: the same desktop, terminal,\n"
                 "themes and sounds. No network is needed (except for extra GPU drivers).\n\n", self.style("text"))
        rows = [("FIRMWARE", self.firmware.upper()),
                ("MEMORY", hw.human_size(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))),
                ("DISKS", str(sum(1 for d in self.disks if not d.busy)) + " usable")]
        rows += [("GPU", g.label) for g in self.gpus] or [("GPU", "none found")]
        for k, v in rows:
            t.append(f"  {k:<10}", self.style("dim"))
            t.append(f"{v}\n", self.style("text"))
        t.append("\nTAB / SHIFT+TAB move between fields, ENTER confirms, CTRL+Q quits.\n", self.style("dim"))
        return t

    def gpu_text(self) -> Text:
        t = Text()
        t.append("GRAPHICS\n", self.style("secondary", True))
        for g in self.gpus or []:
            t.append("  ■ ", self.style("primary"))
            t.append(f"{g.label}{'  (drives the screen)' if g.boot_vga and len(self.gpus) > 1 else ''}\n",
                     self.style("text"))
        if not self.gpus:
            t.append("  no GPU found: the desktop will draw in software\n", self.style("dim"))
        return t

    def driver_label(self, choice: str) -> str:
        plan = hw.driver_plan(self.gpus, choice)
        what = " ".join(plan.packages) if plan.packages else "nothing to download (Mesa)"
        title = {"auto": "RECOMMENDED", "open": "OPEN ONLY", "nvidia": "NVIDIA (proprietary)"}[choice]
        return f"{title:<22}{what}"

    def summary_text(self) -> Text:
        t = Text()
        t.append("READY TO INSTALL\n\n", self.style("primary", True))
        for k, v in self.cfg.summary():
            t.append(f"  {k:<13}", self.style("dim"))
            t.append(f"{v}\n", self.style("text"))
        plan = hw.driver_plan(self.gpus, self.cfg.gpu)
        if plan.packages:
            t.append(f"  {'':<13}{' '.join(plan.packages)} (downloaded if online)\n", self.style("dim"))
        t.append(f"\n▲ EVERYTHING ON {self.cfg.disk} WILL BE ERASED.\n", self.style("secondary", True))
        return t

    # -- navigation ------------------------------------------------------------
    def show_page(self, index: int) -> None:
        self.page = index
        key, title = PAGES[index]
        self.query_one("#pages", ContentSwitcher).current = key
        self.query_one("#main").border_title = f"{index + 1:02d} // {title}"
        self.query_one(Steps).refresh()
        self.query_one("#error", Static).update("")
        back, nxt = self.query_one("#back", Button), self.query_one("#next", Button)
        back.display = 0 < index < len(PAGES) - 1
        nxt.display = index < len(PAGES) - 1
        nxt.label = "INSTALL" if key == "confirm" else "NEXT >"
        if key == "disk":
            lst = self.query_one("#disk-list", OptionList)
            if lst.highlighted is None:
                first = next((i for i, d in enumerate(self.disks) if not d.busy), None)
                lst.highlighted = first
            lst.focus()
        elif key == "drivers":
            lst = self.query_one("#gpu-choice", OptionList)
            lst.highlighted = cfgmod.GPU_CHOICES.index(self.cfg.gpu)
            lst.focus()
        elif key == "confirm":
            self.query_one("#summary", Static).update(self.summary_text())
            self.query_one("#erase", Input).value = ""
            self.query_one("#erase", Input).focus()
        elif key == "account":
            self.query_one("#fullname", Input).focus()
        elif key == "region":
            self.query_one("#keyboard", Select).focus()
        else:
            nxt.focus()

    def collect(self, key: str) -> list[str]:
        """Read the page's fields into the config; the problems, if any."""
        cfg = self.cfg
        if key == "disk":
            lst = self.query_one("#disk-list", OptionList)
            opt = lst.get_option_at_index(lst.highlighted) if lst.highlighted is not None else None
            cfg.disk = opt.id if opt is not None and not opt.disabled and opt.id else ""
            cfg.encrypt = self.query_one("#encrypt", NgCheckbox).value
            cfg.passphrase = self.query_one("#passphrase", Input).value if cfg.encrypt else ""
            errors = cfgmod.check_disk(cfg)
            if cfg.encrypt and cfg.passphrase != self.query_one("#passphrase2", Input).value:
                errors.append("the passphrases differ")
            return errors
        if key == "account":
            cfg.fullname = self.query_one("#fullname", Input).value.strip()
            cfg.username = self.query_one("#username", Input).value.strip()
            cfg.password = self.query_one("#password", Input).value
            cfg.hostname = self.query_one("#hostname", Input).value.strip()
            errors = cfgmod.check_user(cfg)
            if cfg.password != self.query_one("#password2", Input).value:
                errors.append("the passwords differ")
            return errors
        if key == "region":
            cfg.keyboard = str(self.query_one("#keyboard", Select).value)
            cfg.locale = str(self.query_one("#locale", Select).value)
            cfg.timezone = str(self.query_one("#timezone", Select).value)
            return cfgmod.check_region(cfg)
        if key == "drivers":
            lst = self.query_one("#gpu-choice", OptionList)
            cfg.gpu = cfgmod.GPU_CHOICES[lst.highlighted or 0]
            return []
        if key == "confirm":
            if self.query_one("#erase", Input).value.strip() != "ERASE":
                return ["type ERASE (in capitals) to confirm"]
            return cfgmod.validate(cfg)
        return []

    @on(Input.Submitted)
    def input_submitted(self, event: Input.Submitted) -> None:
        """ENTER in a field: on to the next field of the page, or the next page after the last."""
        page = self.query_one(f"#{PAGES[self.page][0]}")
        fields = [w for w in page.query(Input) if not w.disabled]
        if event.input in fields and event.input is not fields[-1]:
            fields[fields.index(event.input) + 1].focus()
        else:
            self.next_page()

    @on(Button.Pressed, "#next")
    def next_page(self) -> None:
        if self.installing or self.page >= len(PAGES) - 1:
            return
        key = PAGES[self.page][0]
        errors = self.collect(key)
        if errors:
            self.query_one("#error", Static).update(" / ".join(errors))
            return
        self.show_page(self.page + 1)
        if PAGES[self.page][0] == "install":
            self.start_install()

    @on(OptionList.OptionSelected)
    def option_chosen(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "disk-list":
            self.query_one("#encrypt", NgCheckbox).focus()   # the rest of the page first
        else:
            self.next_page()

    @on(Button.Pressed, "#back")
    def prev_page(self) -> None:
        if not self.installing and self.page > 0:
            self.show_page(self.page - 1)

    @on(Checkbox.Changed, "#encrypt")
    def encrypt_toggled(self, event: Checkbox.Changed) -> None:
        for wid in ("#passphrase", "#passphrase2"):
            self.query_one(wid, Input).disabled = not event.value
        if event.value:
            self.query_one("#passphrase", Input).focus()

    def action_quit_installer(self) -> None:
        if not self.installing:
            self.exit()

    # -- installing ------------------------------------------------------------
    def set_progress(self, fraction: float, title: str) -> None:
        t = Text(no_wrap=True)
        avail = self.query_one("#progress").size.width
        width = SEGMENTS if avail == 0 else max(10, min(SEGMENTS, avail - 6))
        t.append(seg_bar(fraction, width), self.style("primary"))
        t.append(f" {fraction * 100:3.0f}%\n", self.style("text", True))
        t.append(title.upper(), self.style("secondary", True))
        self.query_one("#progress", Static).update(t)

    def log_line(self, line: str) -> None:
        self.query_one("#log", RichLog).write(Text(line, self.style("dim" if line.startswith(("$", " ")) else "text")))

    def start_install(self) -> None:
        self.installing = True
        self.set_progress(0, "starting")
        self.install_worker()

    @work(thread=True, exclusive=True)
    def install_worker(self) -> None:
        file_log = make_logger(LOG, False)

        def log(line: str) -> None:
            file_log(line)
            self.call_from_thread(self.log_line, line)

        def progress(fraction: float, title: str) -> None:
            self.call_from_thread(self.set_progress, fraction, title)

        system = System(log)
        log(f"nullgrid-install {__version__} {time.strftime('%Y-%m-%d %H:%M:%S')}: {self.cfg.public()}")
        try:
            inst = self.factory(self.cfg, system, progress, LOG)
            inst.run()
        except (InstallError, OSError) as exc:
            self.call_from_thread(self.finished, str(exc), [])
            return
        self.call_from_thread(self.finished, None, inst.notes)

    def finished(self, error: str | None, notes: list[str]) -> None:
        self.installing = False
        self.notes = notes
        nav = self.query_one("#nav")
        err = self.query_one("#error", Static)
        if error:
            err.update(f"FAILED: {error}  (log: {LOG})")
            nav.mount(Button("QUIT", id="quit"))
        else:
            self.set_progress(1, "installed")
            for n in notes:
                self.log_line(f"note: {n}")
            err.update(Text("INSTALLED. Remove the install medium, then reboot.", self.style("primary", True)))
            nav.mount(Button("QUIT", id="quit"))
            nav.mount(Button("REBOOT", id="reboot"))
            self.call_after_refresh(lambda: self.query_one("#reboot", Button).focus())

    @on(Button.Pressed, "#reboot")
    def reboot(self) -> None:
        self.result = "reboot"
        self.exit()

    @on(Button.Pressed, "#quit")
    def quit_pressed(self) -> None:
        self.exit()


def run_tui() -> int:
    app = InstallerApp()
    app.run()
    if app.result == "reboot":
        subprocess.run(["systemctl", "reboot"])
    return 0

"""The installer TUI and the first-run wizard, driven through Textual's pilot."""
import asyncio
import html
import re

from insttest import FakeSystem  # noqa: F401  (puts the tools on sys.path)
from nullgrid_install import hw, tui, welcome
from nullgrid_install.install import InstallError

DISKS = [hw.Disk("/dev/sdb", 32 * 1024**3, "USB", "usb", True, busy="the live medium"),
         hw.Disk("/dev/vda", 40 * 1024**3, "virtio disk")]
GPUS = [hw.Gpu("0000:00:02.0", "intel", 0x46A6, True, "Intel Iris Xe")]
CONSOLE_GLYPHS = set("─│┌┐└┘├┤┬┴┼█░▒■▲▼►◄◆·•›»↑↓ ")


class FakeInstaller:
    def __init__(self, cfg, fail=None):
        self.cfg, self.fail, self.notes = cfg, fail, ["a note"]

    def run(self):
        if self.fail:
            raise InstallError(self.fail)


async def nxt(app, pilot):
    # Button.press(): a real click within 0.2 s of the last one is ignored (its "active" effect)
    app.query_one("#next").press()
    await pilot.pause()


def make_app(fail=None):
    made = []

    def factory(cfg, system, progress, log_file):
        progress(0.5, "copying the system")
        made.append(FakeInstaller(cfg, fail))
        return made[-1]
    app = tui.InstallerApp(disks=DISKS, gpus=GPUS, firmware="uefi", installer_factory=factory)
    return app, made


async def fill(app, pilot):
    from textual.widgets import Input
    await pilot.pause()
    await nxt(app, pilot)                       # welcome
    await pilot.pause()
    assert app.page == 1 and app.query_one("#disk-list").highlighted == 1   # the live medium is skipped
    assert "[the live medium]" in str(app.query_one("#disk-list").get_option_at_index(0).prompt)
    await nxt(app, pilot)
    await pilot.pause()
    assert app.page == 2
    await nxt(app, pilot)                       # empty account: refused
    await pilot.pause()
    assert app.page == 2 and "user name" in str(app.query_one("#error").render())
    for wid, value in (("#username", "ada"), ("#password", "pw"), ("#password2", "pw"), ("#hostname", "deck")):
        app.query_one(wid, Input).value = value
    await nxt(app, pilot)
    await pilot.pause()
    assert app.page == 3
    await nxt(app, pilot)                       # region: defaults
    await pilot.pause()
    assert app.page == 4
    await nxt(app, pilot)                       # drivers: recommended
    await pilot.pause()
    assert app.page == 5


def test_installer_flow(monkeypatch, tmp_path):
    monkeypatch.setattr(tui, "LOG", tmp_path / "install.log")
    app, made = make_app()

    async def scenario():
        from textual.widgets import Input
        async with app.run_test(size=(110, 34)) as pilot:
            await fill(app, pilot)
            summary = str(app.query_one("#summary").render())
            assert "/dev/vda" in summary and "vulkan-intel" in summary
            app.query_one("#erase", Input).value = "erase"   # must be capitals
            await nxt(app, pilot)
            await pilot.pause()
            assert app.page == 5
            app.query_one("#erase", Input).value = "ERASE"
            await nxt(app, pilot)
            for _ in range(50):
                await pilot.pause(0.05)
                if not app.installing and app.query("#reboot"):
                    break
            assert app.page == 6 and app.query("#reboot")
            app.query_one("#reboot").press()
            await pilot.pause()
        assert app.result == "reboot"
    asyncio.run(scenario())
    cfg = made[0].cfg
    assert (cfg.disk, cfg.username, cfg.hostname, cfg.gpu, cfg.encrypt) == ("/dev/vda", "ada", "deck", "auto", False)
    assert cfg.locale == "en_US.UTF-8"  # not the live system's C.UTF-8


def test_installer_failure_and_encryption(monkeypatch, tmp_path):
    monkeypatch.setattr(tui, "LOG", tmp_path / "install.log")
    app, made = make_app(fail="sfdisk failed")

    async def scenario():
        from textual.widgets import Input
        async with app.run_test(size=(110, 34)) as pilot:
            await pilot.pause()
            await nxt(app, pilot)
            await pilot.pause()
            app.query_one("#encrypt").value = True
            await pilot.pause()
            app.query_one("#passphrase", Input).value = "a"
            app.query_one("#passphrase2", Input).value = "b"
            await nxt(app, pilot)
            await pilot.pause()
            assert app.page == 1 and "differ" in str(app.query_one("#error").render())
            app.query_one("#passphrase2", Input).value = "a"
            await nxt(app, pilot)
            await pilot.pause()
            assert app.page == 2 and app.cfg.encrypt and app.cfg.passphrase == "a"
            app.page = 1
            app.show_page(1)
            app.query_one("#encrypt").value = False
            await nxt(app, pilot)
            await pilot.pause()
            assert app.cfg.passphrase == ""
            for wid, value in (("#username", "ada"), ("#password", "pw"), ("#password2", "pw")):
                app.query_one(wid, Input).value = value
            for _ in range(3):
                await nxt(app, pilot)
                await pilot.pause()
            app.query_one("#erase", Input).value = "ERASE"
            await nxt(app, pilot)
            for _ in range(50):
                await pilot.pause(0.05)
                if app.query("#quit"):
                    break
            assert "FAILED: sfdisk failed" in str(app.query_one("#error").render())
            assert not app.query("#reboot")
    asyncio.run(scenario())


def drawn(app) -> set[str]:
    """Every character on the screen (from Textual's SVG screenshot)."""
    svg = app.export_screenshot()
    return set("".join(html.unescape(m) for m in re.findall(r"<text[^>]*>([^<]*)</text>", svg)))


def test_installer_console_glyphs(monkeypatch, tmp_path):
    """What the TUI draws must exist in the console font (it runs on a TTY too)."""
    monkeypatch.setattr(tui, "LOG", tmp_path / "install.log")
    app, _ = make_app()

    async def scenario():
        async with app.run_test(size=(110, 34)) as pilot:
            seen = set()
            for page in range(7):
                app.show_page(page)
                await pilot.pause()
                seen |= drawn(app)
            app.query_one("#encrypt").value = True
            app.set_progress(0.4, "copying")
            await pilot.pause()
            seen |= drawn(app)
            assert "■" in seen and "┌" in seen
            odd = {c for c in seen if not c.isascii() and c not in CONSOLE_GLYPHS | {"\xa0"}}
            assert odd == set(), odd
    asyncio.run(scenario())


def test_welcome_flow(isolated):
    applied = []
    app = welcome.WelcomeApp(
        theme_list=[("crimson-hud", "red", {"bg": "#1a0b0f", "primary": "#5ef2f2"}),
                    ("ice-protocol", "blue", {"bg": "#000000", "primary": "#aaddff"})],
        pack_list=[("neural-link", "glitchy"), ("minimal-ops", "subtle")],
        apply_fn=lambda *a: applied.append(a) or [], preview=False)

    async def scenario():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.page == 0
            await pilot.press("down", "enter")            # ice-protocol
            await pilot.pause()
            assert app.page == 1 and app.choice["theme"] == "ice-protocol"
            await pilot.press("down", "down", "enter")    # muted
            await pilot.pause()
            await pilot.press("left")                      # back to the sound page
            await pilot.pause()
            assert app.page == 1
            await pilot.press("enter")
            await pilot.press("down", "enter")             # tty
            await pilot.pause()
            assert app.page == 3 and "ice-protocol" in str(app.query_one("#done-text").render())
            await pilot.press("enter")
            await pilot.pause()
    asyncio.run(scenario())
    assert applied == [("ice-protocol", welcome.MUTED, "tty")]
    assert welcome.state_file().exists()


def test_welcome_uses_the_theme_palette(isolated):
    gen = isolated / ".config/nullgrid/generated"
    gen.mkdir(parents=True)
    (gen / "theme.json").write_text('{"name": "toxic-grid", "ansi": {"primary": 2}}')
    app = welcome.WelcomeApp(theme_list=[("toxic-grid", "", {})], pack_list=[], apply_fn=None, preview=False)

    async def scenario():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.query_one("#frame").styles.border_top[1].ansi == 2
    asyncio.run(scenario())


def test_welcome_skip_and_cli(isolated, monkeypatch):
    app = welcome.WelcomeApp(theme_list=[("crimson-hud", "red", {})], pack_list=[], apply_fn=None, preview=False)

    async def scenario():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
    asyncio.run(scenario())
    assert welcome.state_file().exists()
    welcome.state_file().unlink()

    calls = []
    monkeypatch.setattr(welcome, "nullgrid", lambda *a, **k: calls.append(a) or 0)
    assert welcome.main(["--theme", "toxic-grid", "--sound", "muted", "--mode", "tty"]) == 0
    assert calls == [("theme", "set", "toxic-grid"), ("sound", "mute", "on"), ("mode", "tty")]
    assert welcome.state_file().exists()

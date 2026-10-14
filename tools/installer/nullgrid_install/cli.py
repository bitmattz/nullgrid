"""`nullgrid-install`: install NULLGRID from the live ISO to a disk.

Without options it starts the installer TUI. With --config it installs unattended from a TOML
file (see nullgrid_install.config); --dry-run prints what would be done without touching disks.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from . import __version__, hw
from . import config as cfgmod
from .install import InstallError, Installer, System

LOG = Path("/var/log/nullgrid-install.log")


class DryRunSystem(System):
    """Prints the commands and files instead of running/writing them."""

    def __init__(self, log):
        super().__init__(log)
        self.copied = False   # the target looks like the live image once it was "copied"

    def run(self, *argv, input=None, capture=False, check=True):
        self.log("$ " + " ".join(argv) + ("  <<< (stdin)" if input is not None else ""))
        if argv[0] == "lsblk":
            return f"{argv[-1]} disk\n{argv[-1]}1 part\n{argv[-1]}2 part\n"
        if argv[0] == "blkid":
            return "0000-DRY-RUN\n"
        if argv[0] == "du":
            return "1\t-\n"
        return ""

    def write(self, path, text, mode=0o644):
        self.log(f"--- {path} (mode {mode:o})\n{text.rstrip()}")

    @staticmethod
    def _live(path):
        """A path on the target, as it is in the live image."""
        try:
            return hw.LIVE_ROOT / Path(path).relative_to("/mnt")
        except ValueError:
            return Path(path)

    def read(self, path):
        try:
            return self._live(path).read_text()
        except OSError:
            return ""

    def exists(self, path):
        if Path(path).is_relative_to("/mnt"):
            return self.copied and super().exists(self._live(path))
        return super().exists(Path(path))

    def remove(self, path):
        self.log(f"remove {path}")

    def symlink(self, target, path):
        self.log(f"link {path} -> {target}")

    def glob(self, base, pattern):
        found = super().glob(base, pattern)
        return found or [base / pattern.replace("*", "KVER")]

    def copy_tree(self, src, dst, total, progress):
        self.log(f"$ cp -a {src}/. {dst}")
        self.copied = True


def make_logger(path: Path | None, echo: bool):
    handle = None
    if path:
        try:
            handle = path.open("a")
        except OSError:
            handle = None

    def log(line: str) -> None:
        if handle:
            handle.write(line + "\n")
            handle.flush()
        if echo:
            print(line, flush=True)
    return log


def build_installer(cfg, system, progress=None, log_file=None) -> Installer:
    return Installer(cfg, system, firmware=hw.firmware(), gpus=hw.list_gpus(),
                     cmdline=Path("/proc/cmdline").read_text() if Path("/proc/cmdline").exists() else "",
                     progress=progress, log_file=log_file)


def unattended(args) -> int:
    try:
        cfg = cfgmod.load(args.config)
    except cfgmod.ConfigError as exc:
        print(f"nullgrid-install: {exc}", file=sys.stderr)
        return 2
    errors = cfgmod.validate(cfg)
    disk = next((d for d in hw.list_disks() if d.path == cfg.disk), None)
    if not args.dry_run:
        if disk is None:
            errors.append(f"disk: {cfg.disk} not found (nullgrid-install --list-disks)")
        elif disk.busy:
            errors.append(f"disk: {cfg.disk} can't be used: {disk.busy}")
    if errors:
        print("nullgrid-install: the config has problems:\n  " + "\n  ".join(errors), file=sys.stderr)
        return 2
    for key, value in cfg.summary():
        print(f"{key:<12} {value}")
    if not args.yes and not args.dry_run:
        if input(f"\nEverything on {cfg.disk} will be erased. Type ERASE to install: ").strip() != "ERASE":
            print("cancelled")
            return 1

    if args.dry_run:
        system = DryRunSystem(make_logger(None, True))
        log_file = None
    else:
        log_file = LOG
        system = System(make_logger(log_file, args.verbose))
    last = [-1, ""]

    def progress(fraction: float, title: str) -> None:
        pct = int(fraction * 100)
        if (pct, title) != tuple(last) and (pct >= last[0] + 5 or title != last[1]):
            last[:] = [pct, title]
            print(f"[{pct:3d}%] {title}", flush=True)

    system.log(f"nullgrid-install {__version__} {time.strftime('%Y-%m-%d %H:%M:%S')}: {cfg.public()}")
    inst = build_installer(cfg, system, progress, log_file)
    try:
        inst.run()
    except (InstallError, OSError) as exc:
        print(f"nullgrid-install: FAILED: {exc}" + (f" (log: {LOG})" if log_file else ""), file=sys.stderr)
        return 1
    for note in inst.notes:
        print(f"note: {note}")
    print("INSTALL_OK: remove the install medium and reboot")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="nullgrid-install", description=__doc__.splitlines()[0])
    p.add_argument("--version", action="version", version=f"nullgrid-install {__version__}")
    p.add_argument("--config", type=Path, help="install unattended with the answers in this TOML file")
    p.add_argument("--yes", action="store_true", help="with --config: don't ask before erasing the disk")
    p.add_argument("--dry-run", action="store_true", help="with --config: print the plan, change nothing")
    p.add_argument("-v", "--verbose", action="store_true", help="with --config: print every command")
    p.add_argument("--list-disks", action="store_true", help="show the disks it could install to")
    p.add_argument("--detect", action="store_true", help="show firmware, GPUs and the drivers it would add")
    args = p.parse_args(argv)

    if args.list_disks:
        for d in hw.list_disks():
            print(d.label + (f"  [{d.busy}]" if d.busy else ""))
        return 0
    if args.detect:
        gpus = hw.list_gpus()
        print(f"firmware  {hw.firmware()}")
        for g in gpus:
            print(f"gpu       {g.slot} {g.label}{' (boot)' if g.boot_vga else ''}")
        plan = hw.driver_plan(gpus)
        print(f"drivers   {' '.join(plan.packages) or '(Mesa only, nothing to download)'}")
        for n in plan.notes:
            print(f"note      {n}")
        return 0
    if not args.dry_run and os.geteuid() != 0:
        print("nullgrid-install: run it as root: sudo nullgrid-install", file=sys.stderr)
        return 1
    if args.config:
        return unattended(args)
    if args.dry_run:
        print("nullgrid-install: --dry-run needs --config", file=sys.stderr)
        return 2
    from .tui import run_tui
    return run_tui()

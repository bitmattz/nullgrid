"""The install itself: partition, copy the live system, make it a normal installed system.

The installed system is a copy of the live image (the squashfs, not the running overlay), so it
works without a network and is exactly what was tested live. Live-only parts are then removed
(autologin, the live user, the RAM journal, the archiso initramfs), and what the live ISO does
with its own boot loader is set up on the disk: the boot splash, the greeter, the console font
and palette.

Layout (GPT): 1 GiB FAT32 /boot (EFI system partition, also BIOS-bootable) + the rest ext4 /,
optionally inside LUKS2. Both boot loaders go on the disk, systemd-boot for UEFI and syslinux
for BIOS, so the disk boots on either kind of firmware.

All side effects go through a `System`, so tests can run the whole plan against a fake one.
"""
from __future__ import annotations

import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import __version__, hw, options
from .config import InstallConfig

TARGET = Path("/mnt")
CRYPT_NAME = "nullgrid-root"
CONSOLE_FONT = "ter-v16b"
GROUPS = "wheel,video,audio,input"

# Files of the live ISO's airootfs (iso/airootfs) that must not reach the installed system.
# tests/nullgrid_install checks every file there is either here or in KEEP.
LIVE_ONLY = [
    "etc/sysusers.d/nullgrid-live.conf",
    "etc/sudoers.d/10-nullgrid-live",
    "etc/systemd/system/getty@tty1.service.d",
    "etc/systemd/system/serial-getty@ttyS0.service.d",
    "etc/systemd/system/nullgrid-live-password.service",
    "etc/systemd/system/multi-user.target.wants/nullgrid-live-password.service",
    "etc/systemd/system/choose-mirror.service",
    "etc/systemd/system/multi-user.target.wants/choose-mirror.service",
    "usr/local/bin/choose-mirror",
    "etc/systemd/system/pacman-init.service",
    "etc/systemd/system/multi-user.target.wants/pacman-init.service",
    "etc/systemd/system/etc-pacman.d-gnupg.mount",   # the keyring in RAM
    "etc/systemd/journald.conf.d/volatile-storage.conf",
    "etc/systemd/logind.conf.d/do-not-suspend.conf",
    "etc/mkinitcpio.conf.d/archiso.conf",
    "etc/nullgrid/live-hints",
    "etc/nullgrid/lock-hint",
    "usr/local/share/applications/nullgrid-install.desktop",
]
# Live files the installed system keeps (or that the installer rewrites).
KEEP = [
    "etc/hostname", "etc/locale.conf", "etc/localtime", "etc/vconsole.conf",  # rewritten
    "etc/passwd", "etc/shadow",                                               # users rewritten
    "home/nullgrid",                                                          # removed with the live user
    "etc/issue", "etc/plymouth/plymouthd.conf", "etc/pacman.d/hooks",
    "etc/systemd/system/dbus-org.freedesktop.NetworkManager.service",
    "etc/systemd/system/dbus-org.freedesktop.nm-dispatcher.service",
    "etc/systemd/system/dbus-org.freedesktop.timesync1.service",
    "etc/systemd/system/multi-user.target.wants/NetworkManager.service",
    "etc/systemd/system/multi-user.target.wants/nullgrid-console-palette.service",
    "etc/systemd/system/bluetooth.target.wants",                 # bluetoothd when an adapter shows up
    "etc/systemd/system/dbus-org.bluez.service",
    "etc/systemd/system/network-online.target.wants",
    "etc/systemd/system/sysinit.target.wants",
    "etc/systemd/system/systemd-loop@.service",          # masked: as on the live system
    "etc/systemd/system-generators/systemd-gpt-auto-generator",  # masked: /etc/fstab says it all
]

PRESET = """\
# mkinitcpio preset for the 'linux' package (written by nullgrid-install)
ALL_kver="/boot/vmlinuz-linux"
PRESETS=('default' 'fallback')
default_image="/boot/initramfs-linux.img"
fallback_image="/boot/initramfs-linux-fallback.img"
fallback_options="-S autodetect"
"""

SYSLINUX_MODULES = ["menu.c32", "libutil.c32", "libcom32.c32", "ldlinux.c32"]


class InstallError(Exception):
    pass


# --------------------------------------------------------------------------- side effects
class System:
    """The real machine. Every command and file write is logged (secrets never are)."""

    def __init__(self, log: Callable[[str], None]):
        self.log = log

    def run(self, *argv: str, input: str | None = None, capture: bool = False, check: bool = True) -> str:
        self.log("$ " + shlex.join(argv))
        proc = subprocess.run(argv, input=input, text=True, stdin=None if input is not None else subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT if not capture else subprocess.PIPE)
        out = proc.stdout or ""
        if not capture:
            for line in out.splitlines():
                self.log("  " + line)
        if check and proc.returncode != 0:
            err = (proc.stderr or out).strip().splitlines()[-3:] if (proc.stderr or out) else []
            raise InstallError(f"{argv[0]} failed (exit {proc.returncode})" + (": " + " / ".join(err) if err else ""))
        return out

    def write(self, path: Path, text: str, mode: int = 0o644) -> None:
        self.log(f"write {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        os.chmod(path, mode)

    def read(self, path: Path) -> str:
        return path.read_text()

    def exists(self, path: Path) -> bool:
        return path.exists() or path.is_symlink()

    def remove(self, path: Path) -> None:
        if path.is_symlink() or path.is_file():
            self.log(f"remove {path}")
            path.unlink()
        elif path.is_dir():
            self.log(f"remove {path}/")
            subprocess.run(["rm", "-rf", "--one-file-system", str(path)], check=True)

    def symlink(self, target: str, path: Path) -> None:
        self.log(f"link {path} -> {target}")
        if path.is_symlink() or path.exists():
            path.unlink()
        path.symlink_to(target)

    def glob(self, base: Path, pattern: str) -> list[Path]:
        return sorted(base.glob(pattern))

    def copy_tree(self, src: Path, dst: Path, total: int, progress: Callable[[float], None]) -> None:
        """cp -a src/. dst, reporting progress by how much the target filesystem filled up."""
        self.log(f"$ cp -a {src}/. {dst}")
        start = self._used(dst)
        proc = subprocess.Popen(["cp", "-a", f"{src}/.", str(dst)], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True)
        while proc.poll() is None:
            time.sleep(0.5)
            progress(min(1.0, (self._used(dst) - start) / max(1, total)))
        out = proc.stdout.read() if proc.stdout else ""
        for line in out.splitlines()[-20:]:
            self.log("  " + line)
        if proc.returncode != 0:
            raise InstallError(f"copying the system failed (cp exit {proc.returncode})")
        progress(1.0)

    @staticmethod
    def _used(path: Path) -> int:
        st = os.statvfs(path)
        return (st.f_blocks - st.f_bfree) * st.f_frsize


@dataclass
class Step:
    title: str
    weight: float
    run: Callable[[], None]


# --------------------------------------------------------------------------- the install
class Installer:
    def __init__(self, cfg: InstallConfig, system: System, *, firmware: str, gpus: list[hw.Gpu],
                 source: Path = hw.LIVE_ROOT, target: Path = TARGET, cmdline: str = "",
                 progress: Callable[[float, str], None] | None = None, log_file: Path | None = None):
        self.cfg = cfg
        self.sys = system
        self.firmware = firmware
        self.drivers = hw.driver_plan(gpus, cfg.gpu)
        self.source = source
        self.target = target
        self.cmdline = cmdline.split()
        self.progress = progress or (lambda f, t: None)
        self._sub: Callable[[float], None] = lambda f: None   # progress within the current step
        self.log_file = log_file
        self.notes: list[str] = list(self.drivers.notes)
        # filled in as the install goes
        self.boot_part = self.root_part = self.root_dev = ""
        self.luks_uuid = self.root_uuid = self.boot_uuid = ""
        self.mounted = self.opened = False

    def t(self, rel: str) -> Path:
        """A path on the installed system."""
        return self.target / rel.lstrip("/")

    def chroot(self, *argv: str, **kw) -> str:
        return self.sys.run("arch-chroot", str(self.target), *argv, **kw)

    @property
    def serial(self) -> bool:
        if self.cfg.serial_console == "auto":
            return any(a.startswith("console=ttyS") for a in self.cmdline)
        return self.cfg.serial_console == "yes"

    def steps(self) -> list[Step]:
        return [
            Step("checking the live system", 1, self.check),
            Step(f"partitioning {self.cfg.disk}", 2, self.partition),
            Step("creating file systems", 4 if self.cfg.encrypt else 2, self.format),
            Step("mounting", 1, self.mount),
            Step("copying the system", 55, self.copy),
            Step("configuring the system", 10, self.configure),
            Step("installing GPU drivers", 12 if self.drivers.packages else 0.5, self.install_drivers),
            Step("building the boot image", 12, self.initramfs),
            Step("installing the boot loaders", 3, self.bootloader),
            Step("finishing", 2, self.finish),
        ]

    def run(self) -> None:
        steps = self.steps()
        total = sum(s.weight for s in steps)
        done = 0.0
        try:
            for step in steps:
                self.sys.log(f"== {step.title}")
                base = done

                def sub(fraction: float, step=step, base=base) -> None:
                    self.progress((base + step.weight * fraction) / total, step.title)

                self._sub = sub
                sub(0.0)
                step.run()
                done += step.weight
            self.progress(1.0, "done")
        except Exception:
            self.cleanup()
            raise

    # -- steps ------------------------------------------------------------------
    def check(self) -> None:
        if not self.sys.exists(self.source / "usr/lib/modules"):
            raise InstallError(f"no live system image at {self.source} (run this from the NULLGRID live ISO)")
        kernels = self.sys.glob(self.source, "usr/lib/modules/*/vmlinuz")
        if len(kernels) != 1:
            raise InstallError(f"expected one kernel in the live image, found {len(kernels)}")
        self.kernel = kernels[0].relative_to(self.source)
        if self.sys.exists(self.target / "etc"):
            raise InstallError(f"{self.target} is not empty: something is mounted there")

    def partition(self) -> None:
        disk = self.cfg.disk
        self.sys.run("wipefs", "--all", "--force", disk)
        self.sys.run("sfdisk", "--wipe", "always", "--wipe-partitions", "always", disk, input=(
            "label: gpt\n"
            'size=1GiB, type=uefi, name="NULLGRID boot", attrs="LegacyBIOSBootable"\n'
            'type=linux, name="NULLGRID root"\n'))
        self.sys.run("udevadm", "settle")
        parts = [line.split()[0] for line in self.sys.run("lsblk", "-lnpo", "PATH,TYPE", disk, capture=True).splitlines()
                 if line.split()[1:] == ["part"]]
        if len(parts) != 2:
            raise InstallError(f"expected 2 partitions on {disk}, found {len(parts)}")
        self.boot_part, self.root_part = parts

    def format(self) -> None:
        self.sys.run("mkfs.fat", "-F", "32", "-n", "NULLGRID", self.boot_part)
        self.root_dev = self.root_part
        if self.cfg.encrypt:
            self.sys.run("cryptsetup", "luksFormat", "--type", "luks2", "--batch-mode", "--label", "NULLGRID_CRYPT",
                         "--key-file", "-", self.root_part, input=self.cfg.passphrase)
            self._sub(0.6)
            self.sys.run("cryptsetup", "open", "--key-file", "-", self.root_part, CRYPT_NAME, input=self.cfg.passphrase)
            self.opened = True
            self.root_dev = f"/dev/mapper/{CRYPT_NAME}"
            self.luks_uuid = self.uuid(self.root_part)
        self.sys.run("mkfs.ext4", "-F", "-q", "-L", "nullgrid", self.root_dev)
        self.root_uuid = self.uuid(self.root_dev)
        self.boot_uuid = self.uuid(self.boot_part)

    def uuid(self, dev: str) -> str:
        value = self.sys.run("blkid", "-s", "UUID", "-o", "value", dev, capture=True).strip()
        if not value:
            raise InstallError(f"no UUID on {dev}")
        return value

    def mount(self) -> None:
        self.sys.run("mount", self.root_dev, str(self.target))
        self.mounted = True

    def copy(self) -> None:
        out = self.sys.run("du", "-sb", str(self.source), capture=True)
        total = int(out.split()[0]) if out.split() else 1
        self.sys.copy_tree(self.source, self.target, total, self._sub)
        # /boot only now: cp -a can't give a FAT mount point the image's owner and mode.
        # Only root may read the ESP (bootctl warns about a world-readable random seed otherwise).
        self.sys.run("mkdir", "-p", str(self.t("boot")))
        self.sys.run("mount", "-o", "fmask=0077,dmask=0077", self.boot_part, str(self.t("boot")))
        # the kernel: the live ISO keeps it outside its image, the package has it here
        self.sys.run("cp", str(self.t(str(self.kernel))), str(self.t("boot/vmlinuz-linux")))

    def configure(self) -> None:
        cfg = self.cfg
        for rel in LIVE_ONLY:
            if self.sys.exists(self.t(rel)):
                self.sys.remove(self.t(rel))
        if "\nnullgrid:" in "\n" + self.sys.read(self.t("etc/passwd")):
            self.chroot("userdel", "--remove", "nullgrid", check=False)
        self._sub(0.1)

        # host, locale, time, keyboard
        self.sys.write(self.t("etc/hostname"), cfg.hostname + "\n")
        self.sys.write(self.t("etc/hosts"), "127.0.0.1 localhost\n::1 localhost\n"
                       f"127.0.1.1 {cfg.hostname}.localdomain {cfg.hostname}\n")
        wanted = {cfg.locale, "en_US.UTF-8"}
        lines = []
        for line in self.sys.read(self.t("etc/locale.gen")).splitlines():
            name = line.lstrip("#").strip().split(" ")[0]
            lines.append(line.lstrip("#").strip() if line.startswith("#") and name in wanted
                         and line.lstrip("#").strip().endswith(" UTF-8") else line)
        self.sys.write(self.t("etc/locale.gen"), "\n".join(lines) + "\n")
        self.chroot("locale-gen")
        self.sys.write(self.t("etc/locale.conf"), f"LANG={cfg.locale}\n")
        self.sys.symlink(f"../usr/share/zoneinfo/{cfg.timezone}", self.t("etc/localtime"))
        self.chroot("hwclock", "--systohc", check=False)
        kb = options.keyboard(cfg.keyboard) or options.KEYBOARDS[0]
        self.sys.write(self.t("etc/vconsole.conf"), f"KEYMAP={kb.keymap}\nFONT={CONSOLE_FONT}\n")
        self.sys.write(self.t("etc/X11/xorg.conf.d/00-keyboard.conf"), xorg_keyboard(kb))
        self._sub(0.3)

        # file systems
        self.sys.write(self.t("etc/fstab"), fstab(self.root_uuid, self.boot_uuid))

        # the user; root gets no password (sudo for wheel instead)
        argv = ["useradd", "--create-home", "--groups", GROUPS, "--shell", "/usr/bin/zsh"]
        if cfg.fullname:
            argv += ["--comment", cfg.fullname]
        self.chroot(*argv, cfg.username)
        self.chroot("chpasswd", input=f"{cfg.username}:{cfg.password}\n")
        self.sys.write(self.t("etc/sudoers.d/10-nullgrid-wheel"),
                       "# members of wheel may run anything as root (with their password)\n"
                       "%wheel ALL=(ALL:ALL) ALL\n", 0o440)
        self.chroot("passwd", "--lock", "root")
        self._sub(0.5)

        # pacman: the live system keeps its keyring in RAM; the installed one gets its own
        self.chroot("pacman-key", "--init")
        self.chroot("pacman-key", "--populate", "archlinux")
        self._sub(0.8)

        # boot and login: splash, greeter (instead of autologin), console palette
        self.sys.write(self.t("etc/mkinitcpio.d/linux.preset"), PRESET)
        self.sys.write(self.t("etc/mkinitcpio.conf.d/nullgrid.conf"), mkinitcpio_conf(cfg.encrypt, self.drivers.initramfs_modules))
        self.chroot("plymouth-set-default-theme", "nullgrid")
        self.chroot("systemctl", "enable", "greetd.service", "nullgrid-console-palette.service")
        self.sys.write(self.t("etc/nullgrid/installed"),
                       f"# written by nullgrid-install {__version__}\n"
                       f"date={time.strftime('%Y-%m-%d %H:%M:%S')}\nfirmware={self.firmware}\n")

    def install_drivers(self) -> None:
        pkgs = self.drivers.packages
        if not pkgs:
            return
        try:
            self.chroot("pacman", "-Sy", "--noconfirm", "--needed", *pkgs)
        except InstallError as exc:
            self.sys.log(f"! {exc}")
            self.notes.append("GPU drivers were not installed (no network?). Once online, run: "
                              f"sudo pacman -Sy --needed {' '.join(pkgs)}")

    def initramfs(self) -> None:
        self.chroot("mkinitcpio", "-P")

    def kernel_options(self, fallback: bool = False) -> str:
        opts = [f"root=UUID={self.root_uuid}", "rw"]
        if self.cfg.encrypt:
            opts.append(f"cryptdevice=UUID={self.luks_uuid}:{CRYPT_NAME}")
        opts += ["plymouth.enable=0"] if fallback else ["quiet", "splash"]
        opts.append("fbcon=nodefer")
        opts += self.drivers.kernel_params
        if self.serial:
            # the last console= is /dev/console (where the boot messages and the splash go)
            opts += ["console=ttyS0,115200", "console=tty0", "plymouth.ignore-serial-consoles"]
        return " ".join(opts)

    def bootloader(self) -> None:
        # UEFI: systemd-boot (also as EFI/BOOT/BOOTX64.EFI, for firmware that forgets its entries)
        argv = ["bootctl", "install", "--esp-path=/boot"]
        if self.firmware != "uefi":
            argv.append("--no-variables")
        try:
            self.chroot(*argv)
        except InstallError:
            if self.firmware != "uefi":
                raise
            self.sys.log("! could not add a UEFI boot entry; installing to the fallback path only")
            self.chroot(*argv, "--no-variables")
        self.sys.write(self.t("boot/loader/loader.conf"), "default nullgrid.conf\ntimeout 3\nconsole-mode keep\neditor no\n")
        self.sys.write(self.t("boot/loader/entries/nullgrid.conf"), sd_entry(
            "NULLGRID", "01", "initramfs-linux.img", self.kernel_options()))
        self.sys.write(self.t("boot/loader/entries/nullgrid-fallback.conf"), sd_entry(
            "NULLGRID (fallback, boot messages)", "02", "initramfs-linux-fallback.img", self.kernel_options(True)))
        self._sub(0.5)

        # BIOS: syslinux on the same partition (marked legacy-BIOS-bootable), GPT MBR code
        bios = self.t("usr/lib/syslinux/bios")
        self.sys.run("mkdir", "-p", str(self.t("boot/syslinux")))
        self.sys.run("cp", *[str(bios / m) for m in SYSLINUX_MODULES], str(self.t("boot/syslinux")))
        self.sys.write(self.t("boot/syslinux/syslinux.cfg"), syslinux_cfg(
            self.kernel_options(), self.kernel_options(True), self.serial))
        self.sys.run("extlinux", "--install", str(self.t("boot/syslinux")))
        self.sys.run("dd", "bs=440", "count=1", "conv=notrunc", f"if={bios / 'gptmbr.bin'}", f"of={self.cfg.disk}")

    def finish(self) -> None:
        if self.notes:
            self.sys.write(self.t("etc/nullgrid/install-notes"), "".join(f"- {n}\n" for n in self.notes))
        if self.log_file:
            self.sys.run("cp", str(self.log_file), str(self.t("var/log/nullgrid-install.log")))
        self.sys.run("sync")
        self.cleanup()

    def cleanup(self) -> None:
        """Unmount and close what the install opened (also after a failure)."""
        if self.mounted:
            self.sys.run("umount", "--recursive", str(self.target), check=False)
            self.mounted = False
        if self.opened:
            self.sys.run("cryptsetup", "close", CRYPT_NAME, check=False)
            self.opened = False


# --------------------------------------------------------------------------- generated files
def fstab(root_uuid: str, boot_uuid: str) -> str:
    return ("# /etc/fstab (written by nullgrid-install)\n"
            "# <device>  <mount point>  <type>  <options>  <dump>  <fsck>\n"
            f"UUID={root_uuid}  /      ext4  rw,relatime  0 1\n"
            f"UUID={boot_uuid}  /boot  vfat  rw,relatime,fmask=0077,dmask=0077,codepage=437,"
            "iocharset=ascii,shortname=mixed,utf8,errors=remount-ro  0 2\n")


def mkinitcpio_conf(encrypt: bool, modules: list[str]) -> str:
    # As on the live ISO: kms for the splash, consolefont + fbcon=nodefer so the console font is
    # set before Plymouth hands the console over. encrypt asks for the passphrase in the splash.
    hooks = ["base", "udev", "autodetect", "microcode", "modconf", "kms", "keyboard", "keymap",
             "consolefont", "plymouth", "block", *(["encrypt"] if encrypt else []), "filesystems", "fsck"]
    return ("# NULLGRID boot image (written by nullgrid-install; overrides /etc/mkinitcpio.conf)\n"
            f"MODULES=({' '.join(modules)})\nHOOKS=({' '.join(hooks)})\n")


def xorg_keyboard(kb: options.Keyboard) -> str:
    lines = ["# Written by nullgrid-install; `localectl set-x11-keymap` changes it. Hyprland and Sway",
             "# read it too (nullgrid-session passes it on as XKB_DEFAULT_*).",
             'Section "InputClass"',
             '        Identifier "system-keyboard"',
             '        MatchIsKeyboard "on"',
             f'        Option "XkbLayout" "{kb.layout}"']
    if kb.variant:
        lines.append(f'        Option "XkbVariant" "{kb.variant}"')
    if kb.options:
        lines.append(f'        Option "XkbOptions" "{kb.options}"')
    return "\n".join(lines + ["EndSection", ""])


def sd_entry(title: str, key: str, initrd: str, opts: str) -> str:
    return (f"title    {title}\nsort-key {key}\nlinux    /vmlinuz-linux\n"
            f"initrd   /{initrd}\noptions  {opts}\n")


def syslinux_cfg(opts: str, fallback_opts: str, serial: bool) -> str:
    return (("SERIAL 0 115200\n" if serial else "") +
            "UI menu.c32\nPROMPT 0\nTIMEOUT 30\nDEFAULT nullgrid\n"
            "MENU TITLE NULLGRID\n"
            "MENU COLOR border 30;40 #40ffffff #00000000 std\n"
            "MENU COLOR title  1;36;40 #ff5ef2f2 #00000000 std\n"
            "MENU COLOR sel    7;37;41 #ffe6f7f7 #ff8a1a2e all\n"
            "MENU COLOR unsel  37;40 #50ffffff #00000000 std\n\n"
            "LABEL nullgrid\n    MENU LABEL NULLGRID\n    LINUX /vmlinuz-linux\n"
            f"    INITRD /initramfs-linux.img\n    APPEND {opts}\n\n"
            "LABEL fallback\n    MENU LABEL NULLGRID (fallback, boot messages)\n    LINUX /vmlinuz-linux\n"
            f"    INITRD /initramfs-linux-fallback.img\n    APPEND {fallback_opts}\n")

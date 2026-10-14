"""What to install where: the answers of the installer, from the TUI or a TOML file.

An unattended install reads the same answers from a file (`nullgrid-install --config FILE`):

    [disk]
    device = "/dev/vda"
    encrypt = false          # LUKS2 for the root partition
    passphrase = ""

    [user]
    username = "operator"
    fullname = ""
    password = "..."
    hostname = "nullgrid"

    [region]
    locale = "en_US.UTF-8"
    keyboard = "us"          # a console keymap from options.KEYBOARDS
    timezone = "UTC"

    [drivers]
    gpu = "auto"             # auto | open | nvidia

    [boot]
    serial_console = "auto"  # auto (when the live system has one) | yes | no
"""
from __future__ import annotations

import re
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

from . import options

USERNAME = re.compile(r"[a-z_][a-z0-9_-]{0,31}")
HOSTNAME = re.compile(r"[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?")
# names the system already uses (plus a few that would only confuse)
RESERVED = {"root", "bin", "daemon", "mail", "ftp", "http", "nobody", "dbus", "alpm", "avahi", "git",
            "greeter", "polkitd", "tss", "uuidd", "pcscd", "rtkit", "colord", "admin", "sudo", "wheel",
            "video", "audio", "input", "users"}
GPU_CHOICES = ("auto", "open", "nvidia")


@dataclass
class InstallConfig:
    disk: str = ""
    encrypt: bool = False
    passphrase: str = ""
    username: str = ""
    fullname: str = ""
    password: str = ""
    hostname: str = "nullgrid"
    locale: str = "en_US.UTF-8"
    keyboard: str = "us"
    timezone: str = "UTC"
    gpu: str = "auto"
    serial_console: str = "auto"

    def summary(self) -> list[tuple[str, str]]:
        """What will happen, for the confirmation screen and the log (no secrets)."""
        kb = options.keyboard(self.keyboard)
        return [
            ("DISK", f"{self.disk}  (erased)"),
            ("ENCRYPTION", "LUKS2" if self.encrypt else "none"),
            ("USER", f"{self.username}" + (f" ({self.fullname})" if self.fullname else "")),
            ("HOSTNAME", self.hostname),
            ("LOCALE", self.locale),
            ("KEYBOARD", kb.label if kb else self.keyboard),
            ("TIMEZONE", self.timezone),
            ("GPU DRIVERS", self.gpu),
        ]

    def public(self) -> dict:
        d = asdict(self)
        for secret in ("password", "passphrase"):
            d[secret] = "***" if d[secret] else ""
        return d


class ConfigError(Exception):
    pass


def load(path: Path) -> InstallConfig:
    try:
        data = tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    known = {
        "disk": {"device": "disk", "encrypt": "encrypt", "passphrase": "passphrase"},
        "user": {"username": "username", "fullname": "fullname", "password": "password", "hostname": "hostname"},
        "region": {"locale": "locale", "keyboard": "keyboard", "timezone": "timezone"},
        "drivers": {"gpu": "gpu"},
        "boot": {"serial_console": "serial_console"},
    }
    cfg = InstallConfig()
    for section, values in data.items():
        if section not in known or not isinstance(values, dict):
            raise ConfigError(f"{path}: unknown section [{section}]")
        for key, value in values.items():
            if key not in known[section]:
                raise ConfigError(f"{path}: unknown key {section}.{key}")
            attr = known[section][key]
            want = type(getattr(cfg, attr))
            if not isinstance(value, want):
                raise ConfigError(f"{path}: {section}.{key} must be a {want.__name__}")
            setattr(cfg, attr, value)
    return cfg


def check_user(cfg: InstallConfig) -> list[str]:
    errors = []
    if not USERNAME.fullmatch(cfg.username):
        errors.append("user name: lowercase letters, digits, - and _, starting with a letter (max 32)")
    elif cfg.username in RESERVED:
        errors.append(f"user name: {cfg.username!r} is used by the system")
    if not cfg.password:
        errors.append("password: must not be empty")
    elif "\n" in cfg.password or "\r" in cfg.password:
        errors.append("password: no line breaks")
    if ":" in cfg.fullname or "\n" in cfg.fullname:
        errors.append("full name: no ':' or line breaks")
    if not HOSTNAME.fullmatch(cfg.hostname):
        errors.append("hostname: letters, digits and -, not at the start or end (max 63)")
    return errors


def check_disk(cfg: InstallConfig) -> list[str]:
    errors = []
    if not cfg.disk.startswith("/dev/"):
        errors.append("disk: pick the disk to install to")
    if cfg.encrypt and not cfg.passphrase:
        errors.append("encryption: the passphrase must not be empty")
    return errors


def check_region(cfg: InstallConfig, locales=None, timezones=None) -> list[str]:
    errors = []
    if cfg.locale not in (locales if locales is not None else options.locales()):
        errors.append(f"locale: unknown {cfg.locale!r} (e.g. en_US.UTF-8)")
    if options.keyboard(cfg.keyboard) is None:
        errors.append(f"keyboard: unknown {cfg.keyboard!r} ({', '.join(k.keymap for k in options.KEYBOARDS)})")
    if cfg.timezone not in (timezones if timezones is not None else options.timezones()):
        errors.append(f"timezone: unknown {cfg.timezone!r} (e.g. Europe/Berlin)")
    return errors


def validate(cfg: InstallConfig, locales=None, timezones=None) -> list[str]:
    errors = check_disk(cfg) + check_user(cfg) + check_region(cfg, locales, timezones)
    if cfg.gpu not in GPU_CHOICES:
        errors.append(f"drivers.gpu: one of {', '.join(GPU_CHOICES)}")
    if cfg.serial_console not in ("auto", "yes", "no"):
        errors.append("boot.serial_console: auto, yes or no")
    return errors

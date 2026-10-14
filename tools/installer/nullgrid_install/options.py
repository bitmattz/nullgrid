"""Choices for the region step: keyboards, locales, time zones."""
from __future__ import annotations

import zoneinfo
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Keyboard:
    label: str
    keymap: str          # the console's (kbd) keymap
    layout: str          # XKB layout for Hyprland/Sway
    variant: str = ""
    options: str = ""    # XKB options (how to switch between two layouts)


# One entry per common layout: the console keymap and the XKB layout that match it.
# (tests check every name exists in kbd and xkeyboard-config)
KEYBOARDS = [
    Keyboard("English (US)", "us", "us"),
    Keyboard("English (US, international)", "us-acentos", "us", "intl"),
    Keyboard("English (UK)", "uk", "gb"),
    Keyboard("English (US, Dvorak)", "dvorak", "us", "dvorak"),
    Keyboard("English (US, Colemak)", "colemak", "us", "colemak"),
    Keyboard("Portuguese (Brazil, ABNT2)", "br-abnt2", "br"),
    Keyboard("Portuguese (Portugal)", "pt-latin1", "pt"),
    Keyboard("Spanish (Spain)", "es", "es"),
    Keyboard("Spanish (Latin America)", "la-latin1", "latam"),
    Keyboard("French (AZERTY)", "fr-latin1", "fr"),
    Keyboard("French (Switzerland)", "fr_CH-latin1", "ch", "fr"),
    Keyboard("German", "de-latin1", "de"),
    Keyboard("German (Switzerland)", "de_CH-latin1", "ch"),
    Keyboard("Italian", "it", "it"),
    Keyboard("Dutch", "nl", "nl"),
    Keyboard("Belgian", "be-latin1", "be"),
    Keyboard("Danish", "dk-latin1", "dk"),
    Keyboard("Norwegian", "no-latin1", "no"),
    Keyboard("Swedish", "sv-latin1", "se"),
    Keyboard("Finnish", "fi", "fi"),
    Keyboard("Polish", "pl2", "pl"),
    Keyboard("Czech", "cz-qwertz", "cz"),
    Keyboard("Hungarian", "hu", "hu"),
    Keyboard("Turkish (Q)", "trq", "tr"),
    Keyboard("Greek", "gr", "gr"),
    Keyboard("Russian", "ru", "us,ru", "", "grp:alt_shift_toggle"),
    Keyboard("Ukrainian", "ua", "us,ua", "", "grp:alt_shift_toggle"),
    Keyboard("Japanese (106 keys)", "jp106", "jp"),
]


def keyboard(keymap: str) -> Keyboard | None:
    return next((k for k in KEYBOARDS if k.keymap == keymap), None)


def locales(supported: Path = Path("/usr/share/i18n/SUPPORTED")) -> list[str]:
    """UTF-8 locales glibc can generate, e.g. 'pt_BR.UTF-8'."""
    try:
        lines = supported.read_text().splitlines()
    except OSError:
        return ["en_US.UTF-8"]
    found = [ln.split()[0] for ln in lines if ln.endswith(" UTF-8") and ln.split()[0].endswith(".UTF-8")]
    return sorted(set(found)) or ["en_US.UTF-8"]


def timezones() -> list[str]:
    zones = {z for z in zoneinfo.available_timezones()
             if "/" in z and not z.startswith(("Etc/", "SystemV/", "posix/", "right/", "US/"))}
    return ["UTC", *sorted(zones)]


def current_timezone(localtime: Path = Path("/etc/localtime")) -> str:
    try:
        target = str(localtime.resolve())
    except OSError:
        return "UTC"
    marker = "/zoneinfo/"
    return target.split(marker, 1)[1] if marker in target else "UTC"

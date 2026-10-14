"""One release version: VERSION at the repo root matches every package, tool and os-release."""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VERSION = (REPO / "VERSION").read_text().strip()
# nullgrid-fonts versions the bundled upstream fonts, nullgrid-keyring its key set (by date)
OWN_VERSION = ["nullgrid-base", "nullgrid-core", "nullgrid-sfx", "nullgrid-dash", "nullgrid-terminal",
               "nullgrid-desktop", "nullgrid-boot", "nullgrid-installer"]


def test_version_format():
    assert re.fullmatch(r"\d+\.\d+\.\d+", VERSION)


def test_packages_match():
    found = {name: re.search(r"^pkgver=(\S+)", (REPO / "pkg" / name / "PKGBUILD").read_text(), re.M).group(1)
             for name in OWN_VERSION}
    assert found == {name: VERSION for name in OWN_VERSION}
    assert set(OWN_VERSION) | {"nullgrid-fonts", "nullgrid-keyring"} == {p.name for p in (REPO / "pkg").iterdir() if p.is_dir()}


def test_tools_match():
    for init in ("tools/nullgrid/nullgrid", "tools/nullgrid-sfx/nullgrid_sfx",
                 "tools/nullgrid-dash/nullgrid_dash", "tools/installer/nullgrid_install"):
        text = (REPO / init / "__init__.py").read_text()
        assert f'__version__ = "{VERSION}"' in text, init


def test_os_release_matches():
    text = (REPO / "pkg/nullgrid-base/os-release").read_text()
    assert f"VERSION_ID={VERSION}\n" in text and f'VERSION="{VERSION}"' in text

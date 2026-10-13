"""Where nullgrid reads and writes files.

System data (presets, templates, the default config) comes from, in order:
  1. $NULLGRID_DATA_DIR             installed layout, used by tests and packaging
  2. the git checkout this file is in (themes/, config/templates/, config/keybinds/,
     config/nullgrid.toml, config/skel/)
  3. /usr/share/nullgrid            installed layout
User files follow XDG: ~/.config/nullgrid/{nullgrid.toml,themes/,templates/,keybinds/} and
~/.local/state/nullgrid/ for bookkeeping. User themes, templates and keybind sets shadow system
ones by name. Rendered wallpapers are cached in ~/.cache/nullgrid/.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

SYSTEM_DIR = Path("/usr/share/nullgrid")


@dataclass(frozen=True)
class Paths:
    themes: list[Path]          # searched in order, user first
    templates: list[Path]       # searched in order, user first
    keybinds: list[Path]        # keybind sets, searched in order, user first
    default_config: Path
    skel: Path                  # default dotfiles, copied into $HOME by `nullgrid init`
    config_home: Path           # $XDG_CONFIG_HOME
    config_dir: Path            # ~/.config/nullgrid
    state_dir: Path             # ~/.local/state/nullgrid
    cache_dir: Path             # ~/.cache/nullgrid

    @property
    def config_file(self) -> Path:
        return self.config_dir / "nullgrid.toml"

    @property
    def state_file(self) -> Path:
        return self.state_dir / "generated.json"

    @property
    def init_marker(self) -> Path:
        return self.state_dir / "initialized"

    @property
    def user_themes(self) -> Path:
        return self.themes[0]

    @property
    def user_templates(self) -> Path:
        return self.templates[0]


def _system_layout() -> tuple[Path, Path, Path, Path, Path]:
    """(themes dir, templates dir, keybinds dir, default config, skel dir) of the system data."""
    if env := os.environ.get("NULLGRID_DATA_DIR"):
        base = Path(env)
    else:
        repo = Path(__file__).resolve().parents[3]
        if (repo / "themes").is_dir() and (repo / "config" / "templates").is_dir():
            c = repo / "config"
            return repo / "themes", c / "templates", c / "keybinds", c / "nullgrid.toml", c / "skel"
        base = SYSTEM_DIR
    return base / "themes", base / "templates", base / "keybinds", base / "nullgrid.toml", base / "skel"


def _xdg(var: str, fallback: str) -> Path:
    value = os.environ.get(var)
    return Path(value) if value and os.path.isabs(value) else Path.home() / fallback


def resolve() -> Paths:
    themes, templates, keybinds, default_config, skel = _system_layout()
    config_home = _xdg("XDG_CONFIG_HOME", ".config")
    config_dir = config_home / "nullgrid"
    return Paths(
        themes=[config_dir / "themes", themes],
        templates=[config_dir / "templates", templates],
        keybinds=[config_dir / "keybinds", keybinds],
        default_config=default_config,
        skel=skel,
        config_home=config_home,
        config_dir=config_dir,
        state_dir=_xdg("XDG_STATE_HOME", ".local/state") / "nullgrid",
        cache_dir=_xdg("XDG_CACHE_HOME", ".cache") / "nullgrid",
    )

"""Where nullgrid reads and writes files.

System data (presets, templates, the default config) comes from, in order:
  1. $NULLGRID_DATA_DIR             installed layout, used by tests and packaging
  2. the git checkout this file is in (themes/, config/templates/, config/nullgrid.toml)
  3. /usr/share/nullgrid            installed layout
User files follow XDG: ~/.config/nullgrid/{nullgrid.toml,themes/,templates/} and
~/.local/state/nullgrid/ for bookkeeping. User themes and templates shadow system ones by name.
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
    default_config: Path
    config_home: Path           # $XDG_CONFIG_HOME
    config_dir: Path            # ~/.config/nullgrid
    state_dir: Path             # ~/.local/state/nullgrid

    @property
    def config_file(self) -> Path:
        return self.config_dir / "nullgrid.toml"

    @property
    def state_file(self) -> Path:
        return self.state_dir / "generated.json"

    @property
    def user_themes(self) -> Path:
        return self.themes[0]

    @property
    def user_templates(self) -> Path:
        return self.templates[0]


def _system_layout() -> tuple[Path, Path, Path]:
    """(themes dir, templates dir, default config) of the system data."""
    if env := os.environ.get("NULLGRID_DATA_DIR"):
        base = Path(env)
        return base / "themes", base / "templates", base / "nullgrid.toml"
    repo = Path(__file__).resolve().parents[3]
    if (repo / "themes").is_dir() and (repo / "config" / "templates").is_dir():
        return repo / "themes", repo / "config" / "templates", repo / "config" / "nullgrid.toml"
    return SYSTEM_DIR / "themes", SYSTEM_DIR / "templates", SYSTEM_DIR / "nullgrid.toml"


def _xdg(var: str, fallback: str) -> Path:
    value = os.environ.get(var)
    return Path(value) if value and os.path.isabs(value) else Path.home() / fallback


def resolve() -> Paths:
    themes, templates, default_config = _system_layout()
    config_home = _xdg("XDG_CONFIG_HOME", ".config")
    config_dir = config_home / "nullgrid"
    return Paths(
        themes=[config_dir / "themes", themes],
        templates=[config_dir / "templates", templates],
        default_config=default_config,
        config_home=config_home,
        config_dir=config_dir,
        state_dir=_xdg("XDG_STATE_HOME", ".local/state") / "nullgrid",
    )

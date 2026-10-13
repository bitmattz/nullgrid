"""Default dotfiles (the skel dir) and first-run setup of a home directory."""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .paths import Paths


@dataclass
class InstallReport:
    copied: list[Path] = field(default_factory=list)
    kept: list[Path] = field(default_factory=list)  # already there, left alone


def destination(paths: Paths, rel: Path) -> Path:
    """Where a skel file goes. Files under skel/.config/ follow $XDG_CONFIG_HOME."""
    if rel.parts[0] == ".config":
        return paths.config_home.joinpath(*rel.parts[1:])
    return Path.home() / rel


def install(paths: Paths, *, overwrite: bool = False) -> InstallReport:
    """Copy every skel file that's missing in $HOME (all of them with overwrite=True)."""
    report = InstallReport()
    if not paths.skel.is_dir():
        return report
    for src in sorted(p for p in paths.skel.rglob("*") if p.is_file()):
        dst = destination(paths, src.relative_to(paths.skel))
        if dst.exists() and not overwrite:
            report.kept.append(dst)
            continue
        if dst.exists():
            shutil.copy2(dst, dst.with_name(dst.name + ".bak"))
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        report.copied.append(dst)
    return report

"""Shared helpers of the installer tests (a module of its own: there are several conftest.py)."""
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for p in (REPO / "tools" / "nullgrid", REPO / "tools" / "nullgrid-dash", REPO / "tools" / "installer"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from nullgrid_install.install import InstallError, System  # noqa: E402

KVER = "7.2.9-arch1-1"
LOCALE_GEN = "# Configuration file for locale-gen\n#  en_US.UTF-8 UTF-8\n#en_US.UTF-8 UTF-8\n#en_US ISO-8859-1\n#pt_BR.UTF-8 UTF-8\n#pt_BR ISO-8859-1\n"


class FakeSystem(System):
    """Files are real (in tmp dirs), commands are only recorded. `fail` maps a command name to
    the error it raises; `outputs` to what it prints."""

    def __init__(self):
        self.lines: list[str] = []
        super().__init__(self.lines.append)
        self.commands: list[tuple[str, ...]] = []
        self.inputs: dict[str, str] = {}
        self.fail: set[str] = set()
        self.uuids = {}

    def run(self, *argv, input=None, capture=False, check=True):
        self.log("$ " + " ".join(argv))
        self.commands.append(argv)
        cmd = argv[2] if argv[0] == "arch-chroot" else argv[0]
        if input is not None:
            self.inputs[" ".join(argv)] = input
        if cmd in self.fail:
            if check:
                raise InstallError(f"{cmd} failed (exit 1)")
            return ""
        if argv[0] == "lsblk":
            d = argv[-1]
            p = "p" if d[-1].isdigit() else ""
            return f"{d} disk\n{d}{p}1 part\n{d}{p}2 part\n"
        if argv[0] == "blkid":
            return self.uuids.setdefault(argv[-1], f"UUID-{len(self.uuids) + 1}") + "\n"
        if argv[0] == "du":
            return "1000\t/src\n"
        return ""

    def copy_tree(self, src, dst, total, progress):
        self.log(f"$ cp -a {src}/. {dst}")
        shutil.copytree(src, dst, symlinks=True, dirs_exist_ok=True)
        progress(1.0)

    def ran(self, *prefix) -> bool:
        n = len(prefix)
        return any(c[:n] == prefix for c in self.commands)

    def chrooted(self, *prefix) -> bool:
        return any(c[0] == "arch-chroot" and c[2:2 + len(prefix)] == prefix for c in self.commands)

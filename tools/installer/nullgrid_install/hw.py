"""What the installer needs to know about the machine: firmware, disks, GPUs, the live image."""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# The live system as it was built: the squashfs under the live overlay (no changes made in
# the live session end up on the installed system).
LIVE_ROOT = Path("/run/archiso/airootfs")
LIVE_MEDIUM = Path("/run/archiso/bootmnt")
MIN_DISK = 16 * 1024**3   # the system takes ~7 GB; leave room for a home and updates


def firmware(sys_root: Path = Path("/sys")) -> str:
    """'uefi' or 'bios': how this machine booted the live system."""
    return "uefi" if (sys_root / "firmware" / "efi").is_dir() else "bios"


def human_size(n: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return ""  # unreachable


# --------------------------------------------------------------------------- disks
@dataclass
class Disk:
    path: str
    size: int
    model: str = ""
    transport: str = ""
    removable: bool = False
    busy: str = ""          # why it can't be used (mounted, the live medium, too small)

    @property
    def label(self) -> str:
        what = " ".join(x for x in (self.transport.upper(), self.model) if x) or "disk"
        return f"{self.path}  {human_size(self.size)}  {what}"


def _mounts(dev: dict) -> list[str]:
    found = [m for m in dev.get("mountpoints") or [] if m]
    for child in dev.get("children") or []:
        found += _mounts(child)
    return found


def parse_disks(lsblk: dict, live_disk: str | None = None) -> list[Disk]:
    """Disks from `lsblk -J -b -o NAME,PATH,SIZE,TYPE,MODEL,TRAN,RM,RO,MOUNTPOINTS`."""
    disks = []
    for dev in lsblk.get("blockdevices", []):
        if dev.get("type") != "disk" or dev.get("ro") in (True, "1", 1):
            continue
        name = dev.get("name", "")
        if name.startswith(("zram", "loop", "ram")):
            continue
        size = int(dev.get("size") or 0)
        if size == 0:
            continue
        disk = Disk(path=dev.get("path") or f"/dev/{name}", size=size,
                    model=(dev.get("model") or "").strip(), transport=dev.get("tran") or "",
                    removable=dev.get("rm") in (True, "1", 1))
        mounts = _mounts(dev)
        if live_disk and disk.path == live_disk or any(m.startswith("/run/archiso") for m in mounts):
            disk.busy = "the live medium"
        elif mounts:
            disk.busy = f"in use ({', '.join(mounts[:2])})"
        elif size < MIN_DISK:
            disk.busy = f"too small (needs {human_size(MIN_DISK)})"
        disks.append(disk)
    return disks


def _run(*argv: str) -> str:
    try:
        return subprocess.run(argv, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return ""


def live_disk() -> str | None:
    """The disk the live system booted from (a USB stick, the CD drive), so it's never offered."""
    source = _run("findmnt", "-no", "SOURCE", str(LIVE_MEDIUM)).strip()
    if not source:
        return None
    parent = _run("lsblk", "-no", "PKNAME", source).strip().splitlines()
    return f"/dev/{parent[0]}" if parent and parent[0] else source


def list_disks() -> list[Disk]:
    out = _run("lsblk", "-J", "-b", "-o", "NAME,PATH,SIZE,TYPE,MODEL,TRAN,RM,RO,MOUNTPOINTS")
    try:
        data = json.loads(out)
    except ValueError:
        return []
    return parse_disks(data, live_disk())


# --------------------------------------------------------------------------- GPUs
VENDORS = {0x8086: "intel", 0x1002: "amd", 0x10DE: "nvidia"}
# NVIDIA device ids from Turing (GTX 16xx / RTX 20xx, 0x1e00 and up) on work with the open
# kernel modules (nvidia-open). Older cards would need legacy drivers Arch no longer packages:
# they stay on nouveau.
NVIDIA_OPEN_FROM = 0x1E00


@dataclass
class Gpu:
    slot: str
    vendor: str           # intel, amd, nvidia, other
    device: int
    boot_vga: bool = False
    name: str = ""

    @property
    def label(self) -> str:
        return self.name or f"{self.vendor} device {self.device:04x}"


def _pci_names(path: Path = Path("/usr/share/hwdata/pci.ids")) -> dict[tuple[int, int], str]:
    """(vendor, device) -> name, for display GPUs only (from hwdata's pci.ids)."""
    names: dict[tuple[int, int], str] = {}
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return names
    vendor = None
    for line in lines:
        if not line or line.startswith("#"):
            continue
        if not line.startswith("\t"):
            try:
                v = int(line[:4], 16)
            except ValueError:
                vendor = None
                continue
            vendor = (v, line[4:].strip()) if v in VENDORS else None
        elif vendor and not line.startswith("\t\t"):
            try:
                d = int(line[1:5], 16)
            except ValueError:
                continue
            short = vendor[1].split()[0].split(",")[0]
            names[(vendor[0], d)] = f"{short} {line[5:].strip()}"
    return names


def list_gpus(sys_root: Path = Path("/sys"), pci_ids: Path = Path("/usr/share/hwdata/pci.ids")) -> list[Gpu]:
    """Display controllers (PCI class 0x03xxxx)."""
    gpus = []
    names: dict | None = None
    base = sys_root / "bus" / "pci" / "devices"
    for dev in sorted(base.iterdir()) if base.is_dir() else []:
        try:
            if not (dev / "class").read_text().strip().startswith("0x03"):
                continue
            vendor = int((dev / "vendor").read_text(), 16)
            device = int((dev / "device").read_text(), 16)
        except (OSError, ValueError):
            continue
        try:
            boot = (dev / "boot_vga").read_text().strip() == "1"
        except OSError:
            boot = False
        if names is None:
            names = _pci_names(pci_ids)
        gpus.append(Gpu(dev.name, VENDORS.get(vendor, "other"), device, boot, names.get((vendor, device), "")))
    return gpus


@dataclass
class DriverPlan:
    packages: list[str] = field(default_factory=list)
    kernel_params: list[str] = field(default_factory=list)
    initramfs_modules: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def driver_plan(gpus: list[Gpu], choice: str = "auto") -> DriverPlan:
    """Extra packages for these GPUs. 'open': nothing to download (Mesa from the live system
    drives Intel, AMD and older NVIDIA); 'auto': Vulkan/video decode for Intel and AMD and the
    NVIDIA driver for Turing and newer; 'nvidia': the NVIDIA driver whatever the card."""
    plan = DriverPlan()
    vendors = {g.vendor for g in gpus}
    if choice == "open":
        plan.notes.append("open drivers only (Mesa), nothing downloaded")
        return plan
    if "intel" in vendors:
        plan.packages += ["vulkan-intel", "intel-media-driver"]
    if "amd" in vendors:
        plan.packages += ["vulkan-radeon"]
    nvidia = [g for g in gpus if g.vendor == "nvidia"]
    if nvidia:
        modern = choice == "nvidia" or any(g.device >= NVIDIA_OPEN_FROM for g in nvidia)
        if modern:
            plan.packages += ["nvidia-open", "nvidia-utils"]
            plan.kernel_params.append("nvidia_drm.modeset=1")
            if vendors & {"intel", "amd"}:
                # hybrid laptop: the integrated GPU drives the screen, `prime-run app` uses NVIDIA
                plan.packages.append("nvidia-prime")
                plan.notes.append("hybrid graphics: run apps on the NVIDIA GPU with prime-run")
            else:
                # NVIDIA drives the screen: load it early so the boot splash shows on it
                plan.initramfs_modules += ["nvidia", "nvidia_modeset", "nvidia_uvm", "nvidia_drm"]
        else:
            plan.packages.append("vulkan-nouveau")
            plan.notes.append("older NVIDIA card: open nouveau driver")
    return plan

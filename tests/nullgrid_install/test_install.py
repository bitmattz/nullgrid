import json
from pathlib import Path

import pytest

from insttest import KVER
from nullgrid_install import cli, hw, install, options
from nullgrid_install import config as cfgmod
from nullgrid_install.install import InstallError, Installer

REPO = Path(__file__).resolve().parents[2]


def make_cfg(**kw) -> cfgmod.InstallConfig:
    base = dict(disk="/dev/vda", username="ada", fullname="Ada L", password="pa:ss word",
                hostname="deck", locale="pt_BR.UTF-8", keyboard="br-abnt2", timezone="America/Sao_Paulo")
    base.update(kw)
    return cfgmod.InstallConfig(**base)


def run_install(fake, live, cfg=None, gpus=(), firmware="uefi", cmdline="", progress=None):
    src, target = live
    inst = Installer(cfg or make_cfg(), fake, firmware=firmware, gpus=list(gpus), source=src, target=target,
                     cmdline=cmdline, progress=progress)
    inst.run()
    return inst


# --------------------------------------------------------------------------- hardware
LSBLK = {"blockdevices": [
    {"name": "sda", "path": "/dev/sda", "size": 500 * 1024**3, "type": "disk", "model": "Samsung SSD 870 ",
     "tran": "sata", "rm": False, "ro": False, "mountpoints": [None]},
    {"name": "sdb", "path": "/dev/sdb", "size": 32 * 1024**3, "type": "disk", "model": "USB stick", "tran": "usb",
     "rm": True, "ro": False, "mountpoints": [None],
     "children": [{"name": "sdb1", "path": "/dev/sdb1", "type": "part", "mountpoints": ["/run/archiso/bootmnt"]}]},
    {"name": "nvme0n1", "path": "/dev/nvme0n1", "size": 1024**4, "type": "disk", "model": "WD", "tran": "nvme",
     "rm": False, "ro": False, "mountpoints": [None],
     "children": [{"name": "nvme0n1p2", "path": "/dev/nvme0n1p2", "type": "part", "mountpoints": ["/home"]}]},
    {"name": "vdc", "path": "/dev/vdc", "size": 8 * 1024**3, "type": "disk", "rm": False, "ro": False},
    {"name": "sr0", "path": "/dev/sr0", "size": 2 * 1024**3, "type": "rom", "rm": True, "ro": False},
    {"name": "zram0", "path": "/dev/zram0", "size": 4 * 1024**3, "type": "disk", "rm": False, "ro": False},
    {"name": "mmcblk0boot0", "path": "/dev/mmcblk0boot0", "size": 4 * 1024**2, "type": "disk", "ro": True},
]}


def test_parse_disks():
    disks = {d.path: d for d in hw.parse_disks(LSBLK)}
    assert list(disks) == ["/dev/sda", "/dev/sdb", "/dev/nvme0n1", "/dev/vdc"]
    assert disks["/dev/sda"].busy == "" and disks["/dev/sda"].label == "/dev/sda  500.0 GiB  SATA Samsung SSD 870"
    assert disks["/dev/sdb"].busy == "the live medium"
    assert disks["/dev/nvme0n1"].busy.startswith("in use (/home")
    assert disks["/dev/vdc"].busy.startswith("too small")
    # the live medium found by its device even when nothing of it is mounted (copytoram)
    assert hw.parse_disks(LSBLK, live_disk="/dev/sda")[0].busy == "the live medium"


def fake_pci(tmp_path, devices):
    for slot, (cls, vendor, device, boot) in devices.items():
        d = tmp_path / "sys/bus/pci/devices" / slot
        d.mkdir(parents=True)
        (d / "class").write_text(cls + "\n")
        (d / "vendor").write_text(f"0x{vendor:04x}\n")
        (d / "device").write_text(f"0x{device:04x}\n")
        if boot is not None:
            (d / "boot_vga").write_text(f"{int(boot)}\n")
    ids = tmp_path / "pci.ids"
    ids.write_text("# comment\n8086  Intel Corporation\n\t46a6  Alder Lake-P GT2 [Iris Xe Graphics]\n"
                   "\t\t1028 0b19  sub\n10de  NVIDIA Corporation\n\t25a0  GA107M [GeForce RTX 3050 Ti Mobile]\n")
    return tmp_path / "sys", ids


def test_list_gpus(tmp_path):
    sys_root, ids = fake_pci(tmp_path, {
        "0000:00:02.0": ("0x030000", 0x8086, 0x46A6, True),
        "0000:01:00.0": ("0x030200", 0x10DE, 0x25A0, False),
        "0000:00:1f.3": ("0x040300", 0x8086, 0x51C8, None),   # audio: not a GPU
    })
    gpus = hw.list_gpus(sys_root, ids)
    assert [(g.vendor, g.boot_vga) for g in gpus] == [("intel", True), ("nvidia", False)]
    assert gpus[0].label == "Intel Alder Lake-P GT2 [Iris Xe Graphics]"
    assert gpus[1].label == "NVIDIA GA107M [GeForce RTX 3050 Ti Mobile]"
    assert hw.list_gpus(tmp_path / "nothing", ids) == []


G = hw.Gpu
INTEL, AMD = G("a", "intel", 0x46A6, True), G("b", "amd", 0x73BF, True)
RTX, GTX970 = G("c", "nvidia", 0x2484, False), G("d", "nvidia", 0x13C2, True)


@pytest.mark.parametrize("gpus,choice,packages,params,modules", [
    ([INTEL], "auto", ["vulkan-intel", "intel-media-driver"], [], []),
    ([AMD], "auto", ["vulkan-radeon"], [], []),
    ([INTEL], "open", [], [], []),
    ([G("c", "nvidia", 0x2484, True)], "auto", ["nvidia-open", "nvidia-utils"], ["nvidia_drm.modeset=1"],
     ["nvidia", "nvidia_modeset", "nvidia_uvm", "nvidia_drm"]),
    ([INTEL, RTX], "auto", ["vulkan-intel", "intel-media-driver", "nvidia-open", "nvidia-utils", "nvidia-prime"],
     ["nvidia_drm.modeset=1"], []),
    ([GTX970], "auto", ["vulkan-nouveau"], [], []),
    ([GTX970], "nvidia", ["nvidia-open", "nvidia-utils"], ["nvidia_drm.modeset=1"],
     ["nvidia", "nvidia_modeset", "nvidia_uvm", "nvidia_drm"]),
    ([G("v", "other", 0x1050, True)], "auto", [], [], []),
])
def test_driver_plan(gpus, choice, packages, params, modules):
    plan = hw.driver_plan(gpus, choice)
    assert (plan.packages, plan.kernel_params, plan.initramfs_modules) == (packages, params, modules)


# --------------------------------------------------------------------------- options
def test_keyboards_exist():
    kbd, xkb = Path("/usr/share/kbd/keymaps"), Path("/usr/share/X11/xkb/symbols")
    if not kbd.is_dir() or not xkb.is_dir():
        pytest.skip("kbd / xkeyboard-config not installed")
    keymaps = {p.name.split(".")[0] for p in kbd.rglob("*.map.gz")}
    assert len({k.keymap for k in options.KEYBOARDS}) == len(options.KEYBOARDS)
    for k in options.KEYBOARDS:
        assert k.keymap in keymaps, k
        for layout in k.layout.split(","):
            assert (xkb / layout).is_file(), k
        if k.variant:
            assert f'xkb_symbols "{k.variant}"' in (xkb / k.layout).read_text(), k


def test_locales_and_zones(tmp_path):
    f = tmp_path / "SUPPORTED"
    f.write_text("en_US.UTF-8 UTF-8\nen_US ISO-8859-1\npt_BR.UTF-8 UTF-8\nsr_RS@latin UTF-8\n")
    assert options.locales(f) == ["en_US.UTF-8", "pt_BR.UTF-8"]
    assert options.locales(tmp_path / "missing") == ["en_US.UTF-8"]
    zones = options.timezones()
    assert zones[0] == "UTC" and "Europe/Berlin" in zones and "Etc/GMT+3" not in zones
    link = tmp_path / "localtime"
    link.symlink_to("/usr/share/zoneinfo/America/Sao_Paulo")
    assert options.current_timezone(link) == "America/Sao_Paulo"


# --------------------------------------------------------------------------- config
def test_config_file(tmp_path):
    f = tmp_path / "install.toml"
    f.write_text('[disk]\ndevice = "/dev/vda"\nencrypt = true\npassphrase = "x y"\n'
                 '[user]\nusername = "ada"\npassword = "secret"\n[region]\ntimezone = "Europe/Berlin"\n')
    cfg = cfgmod.load(f)
    assert (cfg.disk, cfg.encrypt, cfg.username, cfg.timezone, cfg.hostname) == \
        ("/dev/vda", True, "ada", "Europe/Berlin", "nullgrid")
    assert cfgmod.validate(cfg, locales=["en_US.UTF-8"]) == []
    assert cfg.public()["password"] == "***" and cfg.public()["passphrase"] == "***"
    for bad, msg in (('[disk]\ndevce = "x"\n', "unknown key disk.devce"), ('[dsk]\n', "unknown section"),
                     ('[disk]\nencrypt = "yes"\n', "must be a bool")):
        f.write_text(bad)
        with pytest.raises(cfgmod.ConfigError, match=msg):
            cfgmod.load(f)


@pytest.mark.parametrize("change,problem", [
    (dict(username="Ada"), "user name"), (dict(username="root"), "used by the system"),
    (dict(username="9lives"), "user name"), (dict(password=""), "password"),
    (dict(password="a\nb"), "line breaks"), (dict(hostname="-deck"), "hostname"),
    (dict(fullname="a:b"), "full name"), (dict(disk=""), "disk"),
    (dict(encrypt=True, passphrase=""), "passphrase"), (dict(keyboard="klingon"), "keyboard"),
    (dict(timezone="Mars/Olympus"), "timezone"), (dict(locale="xx_XX.UTF-8"), "locale"),
    (dict(gpu="fast"), "drivers.gpu"),
])
def test_validate(change, problem):
    errors = cfgmod.validate(make_cfg(**change), locales=["pt_BR.UTF-8", "en_US.UTF-8"])
    assert len(errors) == 1 and problem in errors[0], errors


# --------------------------------------------------------------------------- the install
def test_airootfs_files_are_classified():
    """Every file the live ISO adds is either removed by the installer or meant to stay."""
    root = REPO / "iso" / "airootfs"
    known = install.LIVE_ONLY + install.KEEP
    for path in root.rglob("*"):
        if path.is_dir() and not path.is_symlink():
            continue
        rel = path.relative_to(root).as_posix()
        assert any(rel == k or rel.startswith(k + "/") for k in known), f"{rel}: add it to LIVE_ONLY or KEEP"


def test_install_plan(fake, live):
    seen = []
    inst = run_install(fake, live, progress=lambda f, t: seen.append((f, t)))
    src, mnt = live
    # progress goes up to 100 % through every step
    assert seen[-1] == (1.0, "done")
    assert [f for f, _ in seen] == sorted(f for f, _ in seen)
    assert {t for _, t in seen} >= {s.title for s in inst.steps()}

    # disk: GPT with a BIOS-bootable ESP and root; no encryption
    sfdisk = next(c for c in fake.commands if c[0] == "sfdisk")
    script = fake.inputs[" ".join(sfdisk)]
    assert "label: gpt" in script and 'type=uefi' in script and "LegacyBIOSBootable" in script
    assert fake.ran("mkfs.fat", "-F", "32", "-n", "NULLGRID", "/dev/vda1")
    assert fake.ran("mkfs.ext4", "-F", "-q", "-L", "nullgrid", "/dev/vda2")
    assert not fake.ran("cryptsetup")
    assert fake.ran("mount", "/dev/vda2", str(mnt))
    # /boot (FAT) mounted after the copy: cp -a would fail to set the mount point's owner
    copied = next(i for i, line in enumerate(fake.lines) if line.startswith("$ cp -a"))
    boot = fake.lines.index(f"$ mount -o fmask=0077,dmask=0077 /dev/vda1 {mnt / 'boot'}")
    assert boot > copied

    # the copy, the kernel from the package's place
    assert fake.ran("cp", str(mnt / f"usr/lib/modules/{KVER}/vmlinuz"), str(mnt / "boot/vmlinuz-linux"))

    # live-only files gone, the live user removed
    for rel in install.LIVE_ONLY:
        assert not (mnt / rel).exists() and not (mnt / rel).is_symlink(), rel
    assert (mnt / "etc/systemd/system/multi-user.target.wants/nullgrid-console-palette.service").is_symlink()
    assert fake.chrooted("userdel", "--remove", "nullgrid")

    # system settings
    assert (mnt / "etc/hostname").read_text() == "deck\n"
    assert "127.0.1.1 deck.localdomain deck" in (mnt / "etc/hosts").read_text()
    gen = (mnt / "etc/locale.gen").read_text().splitlines()
    assert "pt_BR.UTF-8 UTF-8" in gen and "en_US.UTF-8 UTF-8" in gen and "#pt_BR ISO-8859-1" in gen
    assert fake.chrooted("locale-gen")
    assert (mnt / "etc/locale.conf").read_text() == "LANG=pt_BR.UTF-8\n"
    assert str((mnt / "etc/localtime").readlink()) == "../usr/share/zoneinfo/America/Sao_Paulo"
    assert (mnt / "etc/vconsole.conf").read_text() == "KEYMAP=br-abnt2\nFONT=ter-v16b\n"
    assert 'Option "XkbLayout" "br"' in (mnt / "etc/X11/xorg.conf.d/00-keyboard.conf").read_text()
    fstab = (mnt / "etc/fstab").read_text()
    assert "UUID=UUID-1  /      ext4" in fstab and "UUID=UUID-2  /boot  vfat" in fstab

    # the user, sudo, root locked; the password only on stdin
    assert fake.chrooted("useradd", "--create-home", "--groups", "wheel,video,audio,input", "--shell",
                         "/usr/bin/zsh", "--comment", "Ada L", "ada")
    assert fake.inputs[f"arch-chroot {mnt} chpasswd"] == "ada:pa:ss word\n"
    assert not any("pa:ss" in line for line in fake.lines)
    assert (mnt / "etc/sudoers.d/10-nullgrid-wheel").stat().st_mode & 0o777 == 0o440
    assert fake.chrooted("passwd", "--lock", "root")

    # boot: keyring, splash, greeter, initramfs, both boot loaders
    assert fake.chrooted("pacman-key", "--init") and fake.chrooted("pacman-key", "--populate", "archlinux", "nullgrid")
    assert fake.chrooted("systemctl", "enable", "greetd.service", "nullgrid-console-palette.service")
    assert fake.chrooted("plymouth-set-default-theme", "nullgrid")
    hooks = (mnt / "etc/mkinitcpio.conf.d/nullgrid.conf").read_text()
    assert "kms keyboard keymap consolefont plymouth block filesystems" in hooks and "encrypt" not in hooks
    assert "'fallback'" in (mnt / "etc/mkinitcpio.d/linux.preset").read_text()
    assert fake.chrooted("mkinitcpio", "-P")
    assert fake.chrooted("bootctl", "install", "--esp-path=/boot")
    entry = (mnt / "boot/loader/entries/nullgrid.conf").read_text()
    assert "options  root=UUID=UUID-1 rw quiet splash fbcon=nodefer\n" in entry
    assert "plymouth.enable=0" in (mnt / "boot/loader/entries/nullgrid-fallback.conf").read_text()
    sl = (mnt / "boot/syslinux/syslinux.cfg").read_text()
    assert "APPEND root=UUID=UUID-1 rw quiet splash fbcon=nodefer\n" in sl and "SERIAL" not in sl
    assert fake.ran("extlinux", "--install", str(mnt / "boot/syslinux"))
    assert fake.ran("dd", "bs=440", "count=1", "conv=notrunc",
                    f"if={mnt / 'usr/lib/syslinux/bios/gptmbr.bin'}", "of=/dev/vda")
    assert "firmware=uefi" in (mnt / "etc/nullgrid/installed").read_text()
    assert not (mnt / "etc/nullgrid/install-notes").exists()
    # unmounted at the end
    assert fake.commands[-1] == ("umount", "--recursive", str(mnt))
    assert not fake.ran("pacman", "-Sy")


def test_install_encrypted_serial_nvidia_bios(fake, live):
    cfg = make_cfg(disk="/dev/nvme0n1", encrypt=True, passphrase="open sesame")
    inst = run_install(fake, live, cfg, gpus=[G("c", "nvidia", 0x2484, True)], firmware="bios",
                       cmdline="initrd=x console=ttyS0,115200 console=tty0 quiet")
    src, mnt = live
    assert fake.ran("mkfs.fat", "-F", "32", "-n", "NULLGRID", "/dev/nvme0n1p1")
    fmt = next(c for c in fake.commands if c[:2] == ("cryptsetup", "luksFormat"))
    assert fmt[-1] == "/dev/nvme0n1p2" and fake.inputs[" ".join(fmt)] == "open sesame"
    assert fake.ran("cryptsetup", "open", "--key-file", "-", "/dev/nvme0n1p2", "nullgrid-root")
    assert fake.ran("mkfs.ext4", "-F", "-q", "-L", "nullgrid", "/dev/mapper/nullgrid-root")
    assert not any("open sesame" in line for line in fake.lines)
    hooks = (mnt / "etc/mkinitcpio.conf.d/nullgrid.conf").read_text()
    assert "plymouth block encrypt filesystems" in hooks
    assert "MODULES=(nvidia nvidia_modeset nvidia_uvm nvidia_drm)" in hooks
    assert fake.chrooted("pacman", "-Sy", "--noconfirm", "--needed", "nvidia-open", "nvidia-utils")
    # luks UUID (blkid of the partition) in the kernel options; root by its file system UUID
    opts = inst.kernel_options()
    assert opts == ("root=UUID=UUID-2 rw cryptdevice=UUID=UUID-1:nullgrid-root quiet splash fbcon=nodefer "
                    "nvidia_drm.modeset=1 console=ttyS0,115200 console=tty0 plymouth.ignore-serial-consoles")
    assert fake.chrooted("bootctl", "install", "--esp-path=/boot", "--no-variables")
    assert (mnt / "boot/syslinux/syslinux.cfg").read_text().startswith("SERIAL 0 115200\n")
    assert fake.commands[-2:] == [("umount", "--recursive", str(mnt)), ("cryptsetup", "close", "nullgrid-root")]


def test_drivers_offline_leave_a_note(fake, live):
    fake.fail.add("pacman")
    inst = run_install(fake, live, gpus=[INTEL])
    assert any("vulkan-intel" in n for n in inst.notes)
    assert "sudo pacman -Sy --needed vulkan-intel intel-media-driver" in (live[1] / "etc/nullgrid/install-notes").read_text()


def test_uefi_entry_failure_falls_back(fake, live):
    calls = []
    orig = fake.run

    def run(*argv, **kw):
        if argv[2:4] == ("bootctl", "install") and "--no-variables" not in argv:
            calls.append(argv)
            raise InstallError("bootctl failed")
        return orig(*argv, **kw)
    fake.run = run
    run_install(fake, live)
    assert calls and fake.chrooted("bootctl", "install", "--esp-path=/boot", "--no-variables")


def test_failure_cleans_up(fake, live):
    fake.fail.add("mkinitcpio")
    with pytest.raises(InstallError, match="mkinitcpio"):
        run_install(fake, live, make_cfg(encrypt=True, passphrase="x"))
    assert fake.commands[-2:] == [("umount", "--recursive", str(live[1])), ("cryptsetup", "close", "nullgrid-root")]


def test_refuses_without_live_image(fake, tmp_path):
    with pytest.raises(InstallError, match="no live system image"):
        Installer(make_cfg(), fake, firmware="uefi", gpus=[], source=tmp_path / "nope", target=tmp_path).run()
    assert not fake.ran("wipefs")


def test_mkinitcpio_hooks_exist():
    hooks_dir = Path("/usr/lib/initcpio/install")
    if not (hooks_dir / "base").exists():
        pytest.skip("mkinitcpio not installed")
    text = install.mkinitcpio_conf(True, [])
    hooks = text.split("HOOKS=(")[1].split(")")[0].split()
    missing = [h for h in hooks if not (hooks_dir / h).exists()]
    have_all_packages = (hooks_dir / "plymouth").exists() and (hooks_dir / "encrypt").exists()
    if not have_all_packages:
        missing = [h for h in missing if h not in ("plymouth", "encrypt")]
    assert missing == []


# --------------------------------------------------------------------------- CLI
def test_cli_dry_run(tmp_path, capsys):
    f = tmp_path / "i.toml"
    f.write_text('[disk]\ndevice = "/dev/vdz"\n[user]\nusername = "ada"\npassword = "hunter2"\n')
    assert cli.main(["--config", str(f), "--dry-run"]) in (0, 1)  # 1 when there's no live image here
    out = capsys.readouterr()
    assert "/dev/vdz  (erased)" in out.out and "hunter2" not in out.out + out.err


def test_dry_run_plan(tmp_path, monkeypatch, capsys):
    """--dry-run walks the whole plan (against the live image it would copy)."""
    src = tmp_path / "live"
    (src / f"usr/lib/modules/{KVER}").mkdir(parents=True)
    (src / f"usr/lib/modules/{KVER}/vmlinuz").write_text("k")
    (src / "etc").mkdir()
    (src / "etc/passwd").write_text("nullgrid:x:1000:1000::/home/nullgrid:/usr/bin/zsh\n")
    (src / "etc/sysusers.d").mkdir()
    (src / "etc/sysusers.d/nullgrid-live.conf").write_text("u nullgrid\n")
    monkeypatch.setattr(hw, "LIVE_ROOT", src)
    log = []
    system = cli.DryRunSystem(log.append)
    Installer(make_cfg(), system, firmware="uefi", gpus=[], source=src, target=Path("/mnt")).run()
    text = "\n".join(log)
    assert "remove /mnt/etc/sysusers.d/nullgrid-live.conf" in text
    assert "arch-chroot /mnt userdel --remove nullgrid" in text
    assert "$ arch-chroot /mnt mkinitcpio -P" in text and "--- /mnt/boot/loader/entries/nullgrid.conf" in text
    assert "pa:ss word" not in text


def test_cli_rejects_bad_config(tmp_path, capsys):
    f = tmp_path / "i.toml"
    f.write_text('[user]\nusername = "Root!"\n')
    assert cli.main(["--config", str(f), "--dry-run"]) == 2
    err = capsys.readouterr().err
    assert "user name" in err and "disk" in err

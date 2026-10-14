#!/usr/bin/env python3
"""Install test: boot the ISO, install to a blank virtual disk, boot the installed system.

1. The live ISO (UEFI) runs `nullgrid-install --config` unattended onto a 24 GB virtio disk.
2. The disk boots on its own (UEFI, fresh firmware variables: systemd-boot's fallback path).
   Over serial the test logs in as the new user and checks the installed system: no live
   leftovers, greeter, splash, keyboard/locale/time zone, sudo with a password, the theme engine.
   On tty1 it logs in through the greeter, goes through the first-run wizard (picking TTY mode)
   and checks the dashboard starts. Screenshots: out/screens/installed-*.png.
3. The same disk boots with legacy BIOS (syslinux).

Usage: install_smoke.py [--encrypt]   (normally via `make test-install`; --encrypt types the
       LUKS passphrase into the boot splash)
"""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boot_smoke as bs  # noqa: E402

USER, PASSWORD, HOST = "op", "nullgrid8", "testdeck"
PASSPHRASE = "open8sesame"
INSTALL_TIMEOUT = int(os.environ.get("INSTALL_TIMEOUT", "1500"))
CONFIG = f"""[disk]
device = "/dev/vda"
encrypt = {{encrypt}}
passphrase = "{PASSPHRASE}"
[user]
username = "{USER}"
fullname = "Test Operator"
password = "{PASSWORD}"
hostname = "{HOST}"
[region]
locale = "en_US.UTF-8"
keyboard = "br-abnt2"
timezone = "America/Sao_Paulo"
[drivers]
gpu = "auto"
"""

INSTALLED_CHECKS = [
    ("systemctl is-system-running --wait", r"running"),
    ("findmnt -no FSTYPE / ; findmnt -no FSTYPE /boot", r"vfat"),
    ("cat /proc/cmdline", r".*root=UUID=\S+ rw .*quiet splash fbcon=nodefer.*console=ttyS0.*"),
    # the live system's parts are gone
    ("id nullgrid >/dev/null 2>&1 || echo NO_LIVE_USER", r"NO_LIVE_USER"),
    ("ls /etc/sudoers.d/10-nullgrid-live /etc/systemd/system/getty@tty1.service.d /etc/nullgrid/live-hints"
     " /etc/systemd/system/etc-pacman.d-gnupg.mount /etc/mkinitcpio.conf.d/archiso.conf 2>/dev/null | wc -l", r"0"),
    ("ls -d /var/log/journal/*/ | wc -l", r"1"),   # journal on disk now
    # what the installer set up
    ("cat /etc/hostname", HOST),
    ("cat /etc/vconsole.conf | tr '\\n' ' '", r"KEYMAP=br-abnt2 FONT=ter-v16b ?"),
    ("grep -o '\"XkbLayout\" \"br\"' /etc/X11/xorg.conf.d/00-keyboard.conf", r'"XkbLayout" "br"'),
    ("timedatectl show -p Timezone --value", r"America/Sao_Paulo"),
    ("locale | grep ^LANG=", r"LANG=en_US.UTF-8"),
    ("id -nG", r".*\bwheel\b.*"),
    ("sudo -n true 2>/dev/null || echo NEEDS_PASSWORD", r"NEEDS_PASSWORD"),
    (f"echo {PASSWORD} | sudo -S -p '' true && echo SUDO_OK", r"SUDO_OK"),
    ("sudo -n passwd -S root | cut -d' ' -f2", r"L"),
    ("systemctl is-active greetd nullgrid-console-palette NetworkManager | sort -u", r"active"),
    ("pgrep -x tuigreet >/dev/null && echo GREETER_UP", r"GREETER_UP"),
    ("sudo -n plymouth-set-default-theme", r"nullgrid"),
    ("sudo -n lsinitcpio /boot/initramfs-linux.img | grep -cE 'plymouth|ter-v16b|consolefont'", r"[1-9]\d*"),
    ("sudo -n bootctl is-installed --esp-path=/boot", r"yes"),
    ("sudo -n pacman-key --list-keys 2>/dev/null | grep -c '^uid'", r"[1-9]\d+"),
    ("cat /etc/nullgrid/installed | grep -o '^firmware=.*'", r"firmware=uefi"),
    ("nullgrid --version", r"nullgrid \d+\.\d+\.\d+"),
    ("nullgrid doctor >/dev/null && echo DOCTOR_OK", r"DOCTOR_OK"),
    ("nullgrid-welcome --status", r"pending"),
    ("cat ~/.config/nullgrid/generated/theme.json | grep -o '\"name\": \"crimson-hud\"'", r'"name": "crimson-hud"'),
    ("sudo -n grep -c 'INSTALL\\|== finishing' /var/log/nullgrid-install.log", r"[1-9]\d*"),
]
ENCRYPTED_CHECKS = [
    ("lsblk -dno TYPE,FSTYPE /dev/vda2", r"part\s+crypto_LUKS"),
    ("findmnt -no SOURCE /", r"/dev/mapper/nullgrid-root"),
]


def enter_bash(con: bs.Console) -> None:
    """Swap the login zsh for a plain bash (parseable output). zsh may still be starting up and
    drop typed-ahead input, so try until a command answers."""
    for _ in range(8):
        con.send("exec bash --norc --noprofile --noediting")
        time.sleep(3)
        try:
            con.run("stty -echo; PS1=''; export TERM=dumb SYSTEMD_COLORS=0", 15)
            return
        except TimeoutError:
            continue
    raise TimeoutError("no shell after login")


def serial_login(con: bs.Console, timeout: float) -> None:
    con.wait_for(f"{HOST} login:", timeout)
    con.send(USER)
    con.wait_for("Password:", 30)
    con.send(PASSWORD)
    enter_bash(con)


def vm(tmp: str, disk: str, *extra: str) -> tuple[bs.Console, bs.Monitor]:
    mon_path = os.path.join(tmp, f"monitor-{time.monotonic_ns()}.sock")
    con = bs.Console([os.path.join(bs.ROOT, "build", "run-vm.sh"), "--serial", f"--monitor={mon_path}",
                      f"--disk={disk}", *extra])
    for _ in range(100):
        if os.path.exists(mon_path):
            break
        time.sleep(0.1)
    return con, bs.Monitor(mon_path)


def poweroff(con: bs.Console) -> None:
    con.send(f"sudo -n poweroff 2>/dev/null || echo {PASSWORD} | sudo -S -p '' poweroff")
    con.vm.wait(timeout=180)


def unlock(con: bs.Console, mon: bs.Monitor) -> None:
    """Type the LUKS passphrase into the splash until the system comes up."""
    for _ in range(30):
        time.sleep(8)
        if f"{HOST} login:" in con.text:
            return
        mon.screenshot("installed-unlock")
        mon.keys(*PASSPHRASE, "ret")
    raise TimeoutError("the encrypted disk was not unlocked")


def install(c: bs.Checker, con: bs.Console, encrypt: bool) -> bool:
    con.wait_for(bs.PROMPT, bs.BOOT_TIMEOUT)
    enter_bash(con)
    c.check("nullgrid-install --list-disks", r"/dev/vda\s+24\.0 GiB.*")
    c.check("ls /usr/local/share/applications/nullgrid-install.desktop", r".*nullgrid-install\.desktop")
    for line in CONFIG.format(encrypt=str(encrypt).lower()).splitlines():
        con.run(f"printf '%s\\n' '{line}' >> /tmp/install.toml", 30)
    c.check("sudo nullgrid-install --config /tmp/install.toml --dry-run | grep -c '^\\$ '", r"[1-9]\d+")
    t0 = time.monotonic()
    out = con.run("sudo nullgrid-install --config /tmp/install.toml --yes 2>&1 | tail -n 25", INSTALL_TIMEOUT)
    ok = c.verify(f"install finished in {time.monotonic() - t0:.0f}s", any(l.startswith("INSTALL_OK") for l in out),
                  " | ".join(out[-6:]))
    if not ok:
        c.info("sudo tail -n 40 /var/log/nullgrid-install.log")
    return ok


def greeter_and_wizard(c: bs.Checker, mon: bs.Monitor) -> None:
    """tty1: log in through the greeter, take the wizard to TTY mode, land in the dashboard."""
    mon.screenshot("installed-greeter")
    mon.keys(*USER, "ret")
    time.sleep(2)
    mon.keys(*PASSWORD, "ret")
    if not c.wait("pgrep -f nullgrid-welcome >/dev/null && echo UP", "UP", 90):
        mon.screenshot("installed-greeter-failed")
        return
    time.sleep(4)
    mon.screenshot("installed-welcome")
    mon.keys("ret")                    # theme: crimson-hud (already)
    time.sleep(2)
    mon.keys("ret")                    # sound pack: the current one
    time.sleep(2)
    mon.keys("down", "ret")            # mode: TTY
    time.sleep(2)
    mon.screenshot("installed-welcome-done")
    mon.keys("ret")
    c.wait("nullgrid-welcome --status", "done", 60)
    c.check("nullgrid mode", r"tty")
    if c.wait("ps -o tty= -C nullgrid-dash | grep -c tty1", "1", 90):
        time.sleep(4)
        mon.screenshot("installed-tty-dashboard")


def main() -> int:
    encrypt = "--encrypt" in sys.argv[1:]
    tmp = tempfile.mkdtemp()
    disk = os.path.join(tmp, "disk.qcow2")
    failures: list[str] = []
    phase = "live ISO"
    con = None
    try:
        # 1. install from the live ISO
        con, mon = vm(tmp, disk)
        c = bs.Checker(con)
        failures = c.failures
        ok = install(c, con, encrypt)
        poweroff(con)
        if not ok:
            raise RuntimeError("install failed")

        # 2. the installed system, UEFI
        phase = "installed system (UEFI)"
        t0 = time.monotonic()
        con, mon = vm(tmp, disk, "--hd")
        c.con = con
        if encrypt:
            unlock(con, mon)
        serial_login(con, bs.BOOT_TIMEOUT)
        print(f"[ok] installed system: logged in {time.monotonic() - t0:.0f}s after power on")
        for command, expect in INSTALLED_CHECKS + (ENCRYPTED_CHECKS if encrypt else []):
            c.check(command, expect)
        if encrypt:
            # typed-ahead passphrase attempts may sit in the greeter's username field
            con.run(f"echo {PASSWORD} | sudo -S -p '' systemctl restart greetd", 60)
            time.sleep(5)
        greeter_and_wizard(c, mon)
        if c.failures:
            print("---- diagnostics ----")
            print("\n".join(con.run(bs.DIAGNOSTICS, 60)))
        poweroff(con)

        # 3. the same disk, legacy BIOS (syslinux)
        phase = "installed system (BIOS)"
        con, mon = vm(tmp, disk, "--hd", "--bios")
        c.con = con
        if encrypt:
            unlock(con, mon)
        serial_login(con, bs.BOOT_TIMEOUT)
        c.check("[ -d /sys/firmware/efi ] && echo UEFI || echo BIOS", r"BIOS")
        c.check("systemctl is-system-running --wait", r"running")
        mon.screenshot("installed-bios-tty1")
        poweroff(con)
    except (TimeoutError, RuntimeError, OSError) as exc:
        print(f"[FAIL] {phase}: {exc}")
        if con is not None:
            print("---- last serial output ----")
            print(con.text[-3000:])
        failures.append(str(exc))
    finally:
        if con is not None and con.vm.poll() is None:
            con.vm.kill()
        if os.path.exists(disk):
            os.remove(disk)

    print("PASS" if not failures else f"FAIL ({len(failures)} problem(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

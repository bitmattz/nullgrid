#!/usr/bin/env python3
"""Upgrade test: a system installed from an older ISO updates through the [nullgrid] repository.

1. Installs the old ISO (default: the published 1.0.0, out/v1.0.0/) to a blank VM disk.
2. Boots it, then does what docs/UPDATING.md tells a 1.0.0 user to do once: install the
   nullgrid-keyring package (it trusts the key and adds [nullgrid] to pacman.conf), then
   `pacman -Syu`. The repository is out/publish (signed by `make publish-repo`'s signing step),
   served from the test container at http://10.0.2.2:8080, so it can be tested before upload.
3. Checks the new version is installed and working, and that logging in again refreshes the
   user's configs (the pacman hook's stamp).

Usage: upgrade_smoke.py [old.iso]   (normally via `make test-upgrade`)
"""
import os
import re
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boot_smoke as bs  # noqa: E402
import install_smoke as ins  # noqa: E402

OLD_ISO = os.path.join(bs.ROOT, "out", "v1.0.0", "nullgrid-1.0.0-x86_64.iso")
PUBLISH = os.path.join(bs.ROOT, "out", "publish")
VERSION = open(os.path.join(bs.ROOT, "VERSION")).read().strip()
V = re.escape(VERSION)
SUDO = f"echo {ins.PASSWORD} | sudo -S -p ''"
UPGRADE_TIMEOUT = int(os.environ.get("UPGRADE_TIMEOUT", "1800"))


def install_old(c: bs.Checker, con: bs.Console) -> bool:
    con.wait_for(bs.PROMPT, bs.BOOT_TIMEOUT)
    ins.enter_bash(con)
    for line in ins.CONFIG.format(encrypt="false").splitlines():
        con.run(f"printf '%s\\n' '{line}' >> /tmp/install.toml", 30)
    out = con.run("sudo nullgrid-install --config /tmp/install.toml --yes 2>&1 | tail -n 5", ins.INSTALL_TIMEOUT)
    return c.verify("old version installed", any(l.startswith("INSTALL_OK") for l in out), " | ".join(out[-3:]))


def main() -> int:
    old_iso = sys.argv[1] if len(sys.argv) > 1 else OLD_ISO
    if not os.path.exists(old_iso):
        print(f"[FAIL] no old ISO at {old_iso} (gh release download v1.0.0 -D out/v1.0.0)")
        return 1
    keyring = next((f for f in sorted(os.listdir(PUBLISH)) if f.startswith("nullgrid-keyring-") and f.endswith(".zst")), None) \
        if os.path.isdir(PUBLISH) else None
    if keyring is None:
        print("[FAIL] no signed repository in out/publish (make publish-repo builds it)")
        return 1
    server = subprocess.Popen([sys.executable, "-m", "http.server", "8080", "--directory", PUBLISH],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    tmp = tempfile.mkdtemp()
    disk = os.path.join(tmp, "disk.qcow2")
    con = None
    c = bs.Checker(None)
    try:
        # 1. the old version, installed
        con, mon = ins.vm(tmp, disk, old_iso)
        c.con = con
        ok = install_old(c, con)
        ins.poweroff(con)
        if not ok:
            raise RuntimeError("install of the old version failed")

        # 2. boot it, set up updates once, update
        con, mon = ins.vm(tmp, disk, "--hd")
        c.con = con
        ins.serial_login(con, bs.BOOT_TIMEOUT)
        c.check("pacman -Q nullgrid-desktop", r"nullgrid-desktop 1\.0\.0-1")
        c.check(f"curl -fsSLO http://10.0.2.2:8080/{keyring} && echo FETCHED", r"FETCHED")
        c.check(f"{SUDO} pacman -U --noconfirm ./{keyring} 2>&1 | grep -o 'added the \\[nullgrid\\] repository'",
                r"added the \[nullgrid\] repository", 120)
        c.check("grep -c '^\\[nullgrid\\]' /etc/pacman.conf", r"1")
        c.check(f"{SUDO} pacman-key --list-keys 2>/dev/null | grep -c 'NULLGRID packages'", r"1")
        # the test serves the repository itself (the real one is on GitHub, same files)
        # (sudo -S reads the password from stdin, so the new content comes from sh -c)
        c.con.run(f"{SUDO} sh -c \"echo 'Server = http://10.0.2.2:8080' > /etc/pacman.d/nullgrid-mirrorlist\"", 30)
        c.check("cat /etc/pacman.d/nullgrid-mirrorlist", r"Server = http://10\.0\.2\.2:8080")
        t0 = time.monotonic()
        out = c.con.run(f"{SUDO} pacman -Syu --noconfirm > /tmp/upgrade.log 2>&1; echo rc=$?", UPGRADE_TIMEOUT)
        if not c.verify(f"pacman -Syu ({time.monotonic() - t0:.0f}s)", "rc=0" in out, " ".join(out)):
            c.info("tail -n 25 /tmp/upgrade.log")
        c.info("grep -E '^(:: |upgrading nullgrid|installing)' /tmp/upgrade.log | head -n 20")
        for pkg in ("nullgrid-core", "nullgrid-desktop", "nullgrid-terminal", "nullgrid-base"):
            c.check(f"pacman -Q {pkg}", rf"{pkg} {V}-1")
        c.check("nullgrid --version", rf"nullgrid {V}")
        c.check(". /etc/os-release; echo $VERSION_ID", V)
        c.check("ls /etc/xdg/quickshell/nullgrid/NetPicker.qml /etc/xdg/quickshell/nullgrid/BtPicker.qml | wc -l", r"2")
        c.check("pacman -Q bluez bluez-utils | wc -l", r"2")
        c.check("systemctl is-enabled bluetooth", r"enabled")   # once, by the nullgrid-desktop upgrade
        c.check("test -s /var/lib/nullgrid/updated && echo STAMPED", r"STAMPED")
        c.check("command -v nullgrid-shell >/dev/null && grep -c 'wifi|bluetooth' $(command -v nullgrid-shell)", r"[1-9]")

        # 3. a new login refreshes this user's configs (zsh: the update stamp is newer)
        c.check("[ /var/lib/nullgrid/updated -nt ~/.local/state/nullgrid/initialized ] && echo STALE", r"STALE")
        con.send("exit")
        ins.serial_login(con, 120)
        c.check("[ ~/.local/state/nullgrid/initialized -nt /var/lib/nullgrid/updated ] && echo REFRESHED", r"REFRESHED")
        c.check("nullgrid update --no-system 2>&1 | grep -o 'refreshing your NULLGRID configs'",
                r"refreshing your NULLGRID configs", 120)
        c.check("systemctl is-system-running --wait", r"running")
        ins.poweroff(con)
    except (TimeoutError, RuntimeError, OSError) as exc:
        print(f"[FAIL] {exc}")
        if con is not None:
            print("---- last serial output ----")
            print(con.text[-3000:])
        c.failures.append(str(exc))
    finally:
        if con is not None and con.vm.poll() is None:
            con.vm.kill()
        server.kill()
        if os.path.exists(disk):
            os.remove(disk)
    print("PASS" if not c.failures else f"FAIL ({len(c.failures)} problem(s))")
    return 1 if c.failures else 0


if __name__ == "__main__":
    sys.exit(main())

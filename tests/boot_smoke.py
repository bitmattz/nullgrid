#!/usr/bin/env python3
"""Headless boot smoke test: boot the ISO, log in over serial, check the live system.

Usage: boot_smoke.py [--bios] [iso]   (normally via `make test-boot`)
Env:   BOOT_TIMEOUT  seconds to wait for the shell prompt (default 600; TCG is slow)
"""
import os
import re
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOT_TIMEOUT = int(os.environ.get("BOOT_TIMEOUT", "600"))
PROMPT = "nullgrid@nullgrid"
ANSI = re.compile(r"\x1b(\[[0-9;?]*[ -/]*[@-~]|\][^\x07\x1b]*(\x07|\x1b\\)|P[^\x1b]*\x1b\\|.)")

CHECKS = [
    # (command, regex that one output line must fully match)
    ("systemctl is-system-running --wait", r"running"),
    (". /etc/os-release; echo ID=$ID", r"ID=nullgrid"),
    ("id -nG", r".*\bwheel\b.*"),
    ("sudo -n true && echo SUDO_OK", r"SUDO_OK"),
    ("systemctl is-active NetworkManager", r"active"),
]
# Run when a check fails, to make the report actionable.
DIAGNOSTICS = "systemctl --failed --no-legend --plain --full; journalctl -b -p warning --no-pager -o cat | tail -n 30"


class Console:
    """Serial console of the VM as one growing text buffer."""

    def __init__(self, cmd):
        self.vm = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, bufsize=0)
        self.raw = ""
        self.text = ""
        self.pos = 0  # everything before this has been consumed by wait_for
        self.lock = threading.Condition()
        self.alive = True
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        try:
            while chunk := os.read(self.vm.stdout.fileno(), 4096):
                with self.lock:
                    self.raw += chunk.decode(errors="replace")
                    # Strip escapes on the whole buffer: one sequence may span two chunks.
                    self.text = ANSI.sub("", self.raw).replace("\r", "")
                    self.lock.notify_all()
        finally:
            with self.lock:
                self.alive = False
                self.lock.notify_all()

    def wait_for(self, needle: str, timeout: float) -> str:
        """Return the text between the last consumed position and needle."""
        deadline = time.monotonic() + timeout
        with self.lock:
            while (i := self.text.find(needle, self.pos)) < 0:
                left = deadline - time.monotonic()
                if left <= 0:
                    raise TimeoutError(f"timed out waiting for {needle!r}")
                if not self.alive:
                    raise RuntimeError("VM exited")
                self.lock.wait(min(left, 1))
            out, self.pos = self.text[self.pos:i], i + len(needle)
            return out

    def send(self, line: str):
        self.vm.stdin.write(line.encode() + b"\n")
        self.vm.stdin.flush()

    def run(self, command: str, timeout: float = 180) -> list[str]:
        # The marker is spelled with $((...)) so the echoed command line never matches it.
        self.send(f"{command}; echo __D$((1))NE__")
        out = self.wait_for("__D1NE__", timeout)
        return [l.strip() for l in out.splitlines() if l.strip() and "__D$((1))NE__" not in l]


def main() -> int:
    con = Console([os.path.join(ROOT, "build", "run-vm.sh"), "--serial", *sys.argv[1:]])
    failures = []
    try:
        t0 = time.monotonic()
        con.wait_for(PROMPT, BOOT_TIMEOUT)
        print(f"[ok] reached shell prompt in {time.monotonic() - t0:.0f}s")
        # A plain shell without line editing or echo keeps the output parseable.
        con.send("exec bash --norc --noprofile --noediting")
        time.sleep(2)  # zsh drops typed-ahead input when it execs
        con.run("stty -echo; PS1=''; export TERM=dumb SYSTEMD_COLORS=0", 30)
        for command, expect in CHECKS:
            body = con.run(command)
            ok = any(re.fullmatch(expect, l) for l in body)
            print(f"[{'ok' if ok else 'FAIL'}] {command}  ->  {' | '.join(body)[-200:]}")
            if not ok:
                failures.append(command)
        if failures:
            print("---- diagnostics ----")
            print("\n".join(con.run(DIAGNOSTICS, 60)))
        con.send("sudo poweroff")
        con.vm.wait(timeout=120)
    except (TimeoutError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"[FAIL] {exc}")
        print("---- last serial output ----")
        print(con.text[-3000:])
        failures.append(str(exc))
    finally:
        if con.vm.poll() is None:
            con.vm.kill()

    print("PASS" if not failures else f"FAIL ({len(failures)} problem(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

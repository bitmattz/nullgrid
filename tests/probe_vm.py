#!/usr/bin/env python3
"""Debugging harness: boot the ISO once, then run commands in it from files.

Write a shell command line into out/probe/cmd-NN.sh; the harness runs it over the serial console
(as the live user, in bash) and writes the output to out/probe/out-NN.txt. Much faster than
re-running a whole boot test per question. The QEMU monitor is at out/probe/monitor.sock.

    docker run --rm -d --name ngprobe --device /dev/kvm -v $PWD:/src nullgrid-builder \\
        python3 /src/tests/probe_vm.py [run-vm.sh options, e.g. --bios]
    echo 'free -m' > out/probe/cmd-01.sh; cat out/probe/out-01.txt   # once it exists
    docker kill ngprobe
"""
import glob
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boot_smoke as bs  # noqa: E402

D = os.path.join(bs.ROOT, "out", "probe")


def main() -> int:
    os.makedirs(D, exist_ok=True)
    mon = os.path.join(D, "monitor.sock")
    for f in [mon, os.path.join(D, "READY")]:
        if os.path.exists(f):
            os.remove(f)
    con = bs.Console([os.path.join(bs.ROOT, "build", "run-vm.sh"), "--serial", f"--monitor={mon}", *sys.argv[1:]])
    con.wait_for(bs.PROMPT, bs.BOOT_TIMEOUT)
    con.send("exec bash --norc --noprofile --noediting")
    time.sleep(2)
    con.run("stty -echo; PS1=''; export TERM=dumb SYSTEMD_COLORS=0", 30)
    open(os.path.join(D, "READY"), "w").write("ok\n")
    print("ready: write out/probe/cmd-NN.sh", flush=True)
    while con.vm.poll() is None:
        for f in sorted(glob.glob(os.path.join(D, "cmd-*.sh"))):
            cmd = open(f).read().strip()
            os.rename(f, f + ".done")
            try:
                out = con.run(cmd, 900)
            except TimeoutError as exc:
                out = [f"TIMEOUT {exc}"]
            target = f.replace("cmd-", "out-").replace(".sh", ".txt")
            with open(target, "w") as fh:
                fh.write("\n".join(out) + "\n")
            os.chmod(target, 0o666)
        time.sleep(0.5)
    return 0


if __name__ == "__main__":
    sys.exit(main())

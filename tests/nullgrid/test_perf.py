"""nullgrid perf: per-component memory and CPU, from a fake /proc."""
import json

from nullgrid import cli, perf

HZ = 100


def fake_proc(root, procs, cpu_line, mem_avail=3 * 1024**2):
    root.mkdir(exist_ok=True)
    (root / "meminfo").write_text(f"MemTotal:       4000000 kB\nMemFree:        1000 kB\nMemAvailable:   {mem_avail} kB\n")
    (root / "stat").write_text("cpu  " + " ".join(map(str, cpu_line)) + "\ncpu0 1 2 3\n")
    for pid, (comm, cmdline, ticks, start, pss) in procs.items():
        d = root / str(pid)
        d.mkdir(exist_ok=True)
        (d / "comm").write_text(comm + "\n")
        (d / "cmdline").write_bytes(cmdline.replace(" ", "\0").encode() + b"\0")
        ppid = {400: 399, 399: 1}.get(pid, 1)
        fields = ["S", str(ppid)] + ["0"] * 9 + [str(ticks), "0"] + ["0"] * 6 + [str(start * HZ)] + ["0"] * 10
        (d / "stat").write_text(f"{pid} ({comm}) " + " ".join(fields) + "\n")
        (d / "statm").write_text("100 50 10 1 0 40 0\n")
        if pss is not None:
            (d / "smaps_rollup").write_text(f"Rss:  9999 kB\nPss:   {pss} kB\n")


def test_component_of():
    assert perf.component_of("Hyprland") == "compositor"
    assert perf.component_of("quickshell") == "shell"
    assert perf.component_of("python3", "python3 /usr/bin/nullgrid-dash") == "dashboard"
    assert perf.component_of("kworker") == "other"


def test_measure(tmp_path, monkeypatch):
    monkeypatch.setattr(perf.os, "sysconf", lambda name: {"SC_CLK_TCK": HZ, "SC_PAGE_SIZE": 4096}[name])
    proc = tmp_path / "proc"
    procs = {1: ("systemd", "/sbin/init", 50, 0, 8000),
             200: ("Hyprland", "Hyprland", 1000, 6, 150_000),
             201: ("quickshell", "qs -c nullgrid", 2000, 7, 90_000),
             202: ("sh", "", 0, 7, None)}            # kernel thread style: no cmdline -> skipped
    procs[399] = ("sudo", "sudo nullgrid perf", 0, 9, 1000)
    procs[400] = ("nullgrid", "python nullgrid perf", 0, 9, 1000)
    fake_proc(proc, procs, [100, 0, 100, 800, 0, 0, 0, 0])

    def tick(seconds):
        # 10 s later: Hyprland used 0.5 s of CPU, quickshell 0.1 s; a new process, one without PSS
        procs[200] = ("Hyprland", "Hyprland", 1050, 6, 150_000)
        procs[201] = ("quickshell", "qs -c nullgrid", 2010, 7, 90_000)
        procs[300] = ("swaybg", "swaybg -i x", 5, 9, None)
        procs[399] = ("sudo", "sudo nullgrid perf", 0, 9, 1000)
        procs[400] = ("nullgrid", "python nullgrid perf", 40, 9, 1000)
        fake_proc(proc, procs, [150, 0, 150, 1700, 0, 0, 0, 0])
    r = perf.measure(10, top=3, proc=proc, sleep=tick, me=400)
    assert r.mem_used == (4_000_000 - 3 * 1024**2) * 1024 - 2 * 1000 * 1024   # minus itself and its sudo
    assert round(r.cpu_total, 1) == 10.0          # (100 busy) / (1000 total)
    assert r.components["compositor"].mem == 150_000 * 1024
    assert round(r.components["compositor"].cpu, 2) == 5.0     # 50 ticks / 100 Hz / 10 s
    assert round(r.components["shell"].cpu, 2) == 1.0
    assert r.components["shell"].started == 7
    assert r.components["wallpaper"].cpu == 0.0 and r.components["wallpaper"].mem == 50 * 4096
    assert not r.exact
    assert [t[0] for t in r.top] == ["Hyprland", "quickshell", "systemd"]
    assert "other" not in r.components


def test_cli_perf(tmp_path, monkeypatch, capsys):
    rep = perf.Report(1, 4 * 1024**3, 600 * 1024**2, 2, 3.5,
                      {"shell": perf.Usage(90 * 1024**2, 0.4, 1, 7.2)}, [("quickshell", 90 * 1024**2, 0.4, "shell")])
    monkeypatch.setattr(perf, "measure", lambda s, t: rep)
    assert cli.main(["perf", "--seconds", "1"]) == 0
    out = capsys.readouterr().out
    assert "memory used 600 MiB of 4096 MiB" in out and "shell" in out and "7.2s" in out
    assert cli.main(["perf", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["components"]["shell"]["started"] == 7.2 and data["mem_used"] == 600 * 1024**2

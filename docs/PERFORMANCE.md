# Performance

NULLGRID is meant for old laptops and cyberdecks, so the idle desktop has a budget: about
700 MB of RAM in a 4 GB VM, and no widget above 2% of a CPU core.

## Measuring

```sh
nullgrid perf                 # 10 s: memory and CPU per component, and when each came up
sudo nullgrid perf --seconds 60 --top 20
nullgrid perf --json          # for scripts
```

- **Memory** per process is PSS: its share of the pages it uses, so shared libraries count once
  overall. Without root, other users' processes fall back to RSS (overcounted); use `sudo`.
- **Memory used** is MemTotal − MemAvailable, what the kernel can't give back (the number `free`
  shows). `nullgrid perf` leaves itself and its `sudo` out of it.
- **CPU** is per core, over the window: 100% = one core busy.
- **UP AT** is when the component's first process started, in seconds after boot.

Processes are grouped into components: compositor (Hyprland/Sway, Xwayland), shell (Quickshell:
bar, dock, every HUD widget, menu, notifications), wallpaper (swaybg), sound (nullgrid-sfx),
audio (PipeWire), terminal (kitty, shells), login, desktop services (D-Bus, portals), network,
system.

`make perf` boots the ISO in a 4 GB, 2-CPU QEMU/KVM VM with virtio-gpu **without 3D**, lets the
Hyprland desktop settle for 90 s, measures for 60 s, then does the same with the lite (Sway)
session. It writes `out/perf/report.md` and `report.json` and checks the budget.

## Results

From `make perf` on the live ISO (2026-10-14, NULLGRID 0.9.0). The VM draws everything in
software (Mesa llvmpipe), the worst case: on a machine with a 3D GPU, Hyprland and kitty need
less memory and the compositor less CPU.

| Idle desktop | Memory used | Compositor CPU | Shell (widgets) CPU | Wallpaper / sound CPU |
|---|---:|---:|---:|---:|
| Hyprland (default) | 722-738 MiB | 2.1% | 0.20% | 0% / 0% |
| Sway (`[performance] profile = "lite"`) | 585-608 MiB | 0.17% | 0.12-0.15% | 0% / 0% |

(Two fresh boots of the same ISO; memory varies by ~20 MiB from boot to boot.)

Biggest processes at the idle Hyprland desktop (PSS): Hyprland 178 MiB, kitty (the login
terminal) 111 MiB, Quickshell 64 MiB, Xwayland 31 MiB, kitty's exit helper 27 MiB, the desktop
portal 16 MiB, the sound daemon 13 MiB, NetworkManager 13 MiB.

Boot (UEFI, KVM): power-on to the serial shell prompt 20 s; kernel 1.7 s; the shell (bar, dock,
widgets) is up 14.7 s after the kernel starts. On the live ISO, `pacman-init` (the keyring,
~9 s) and `systemd-time-wait-sync` run in parallel and only delay `multi-user.target`, not the
desktop.

The budget in `make perf`: < 700 MiB for the lite session, < 750 MiB for Hyprland (software
rendering inflates Hyprland and kitty there; on real GPUs it should be lower, but the test VM
can't show that), < 2% of a core for the shell, the wallpaper and the sound daemon.

## What was fixed (phase 9)

| Change | Effect (measured) |
|---|---|
| Transparent huge pages `madvise` instead of `always` (`/usr/lib/tmpfiles.d/nullgrid-memory.conf`) | −150 MiB: heaps grew in 2 MB steps (288 MB of huge pages at idle) |
| Without a 3D GPU: widgets sample every 2 s instead of 1 s | compositor idle CPU 6.6% → 3.3%: every widget update is a software redraw |
| Without a 3D GPU: no blur in Hyprland (the neon glow stays) | −24 MiB, compositor CPU 3.3% → 2.1% |
| kitty `auto_reload_config -1` | −16-20 MiB per kitty: no config-watcher process (themes reload kitty by signal) |
| Live ISO: autologin gettys `Type=simple` | desktop ~4 s sooner: `Type=idle` waited 5 s for `pacman-init` |

Tried and left out (no measurable effect): `MALLOC_ARENA_MAX=2`, `LP_NUM_THREADS=1`, turning off
shadows (Hyprland's are already off; the glow is a separate option).

## Lighter still

- `[performance] profile = "lite"` in `nullgrid.toml`: the Sway session, no blur, glow or
  animations, widgets every 3 s (~135 MiB less than Hyprland in the VM).
- `nullgrid widget toggle NAME` hides HUD widgets; `[decor]` turns off the matrix rain.
- `nullgrid mode tty`: no graphics at all, the console dashboard.

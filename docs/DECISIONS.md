# Design decisions

Small choices are recorded here as they're made. Big ones were agreed up front (2026-10-12).

## Agreed with the project owner

| Topic | Decision |
|---|---|
| Name | NULLGRID |
| Base | Arch Linux, ISO built with archiso |
| Compositor | Hyprland, with a Sway fallback config for GPUs where Hyprland misbehaves |
| Desktop shell | Quickshell (QML): custom shapes (chamfers, gauges, graphs), built-in Hyprland/PipeWire/UPower/tray/notification support, hot reload |
| Target hardware | x86_64 VMs and laptops (incl. old ThinkPads, NVIDIA hybrid), **plus** Raspberry Pi and DIY cyberdecks (aarch64), see below |
| Distribution | Only NULLGRID itself; no separate theme/dotfiles package for other Arch systems |
| Build host | Any Linux with Docker; mkarchiso runs in an Arch container |
| TTY dashboard | Python + Textual |
| Live ISO login | Auto-login (no greeter on the live ISO; tuigreet on installed systems) |
| Repo | https://github.com/bitmattz/nullgrid |

## Phase 1

- **Own packages via a local pacman repo.** Everything NULLGRID-specific ships as PKGBUILDs in
  `pkg/`, built into `out/repo` and installed by name from `iso/packages.x86_64`. The installer
  (phase 8) installs the exact same packages, so live and installed systems can't drift apart.
- **NetworkManager instead of releng's systemd-networkd + iwd.** It has `nmtui` for users and a
  D-Bus API that the status bar and Quickshell can read for wifi state.
- **zstd instead of xz** for the squashfs and the initramfs. The ISO is slightly bigger but
  decompresses much faster, which helps boot time on old/slow machines and SD cards.
- **Live user `nullgrid` (uid 1000) created with sysusers.d**, not by shipping a full
  `/etc/group`. That avoids fighting pacman over files `filesystem` owns. The password is locked,
  tty1 auto-logs in, and sudo is passwordless (live ISO only).
- **Serial console enabled** (`console=ttyS0`, autologin on ttyS0). This makes `make test-boot`
  possible without a display and is harmless on real hardware.
- **Removed from releng:** speech/accessibility boot entries, memtest/HDT, cloud-init, hypervisor
  guest daemons, ssh, ModemManager, and the PXE initramfs hooks (which need nbd/nfs tools).
  They can be re-added if needed. The accessibility entry
  should probably come back once the desktop exists.
- **`/etc/os-release` belongs to `nullgrid-base`.** `/usr/lib/os-release` stays Arch's (owned by
  `filesystem`); `/etc/os-release` takes precedence and is otherwise unowned on Arch.
- **Makefile rather than justfile.** `make` is preinstalled everywhere and `just` isn't.

## Light hardware strategy (from the target-hardware answer)

- Every NULLGRID tool is Python/QML/shell (`arch=any`), so it is architecture-neutral by design.
- A `[performance]` profile in `nullgrid.toml` (phase 2) will offer `full | lite`. `lite` turns off
  blur, shadows and animations, slows widget refresh, and can pick Sway over Hyprland.
- **Raspberry Pi (aarch64):** archiso's `bios`/`uefi` boot modes don't fit the Pi's firmware boot.
  The plan is a separate SD-card image builder (`image/rpi/`, after phase 9) that starts from the
  Arch Linux ARM rootfs and installs the same `pkg/` packages, cross-built in Docker with
  qemu-user/binfmt. Hyprland runs on Pi 4/5 (V3D GPU, Mesa). Pi 3 and older would get the `lite`
  profile on Sway, or TTY mode.
- **`systemd-loop@.service` is masked on the live ISO.** systemd 262 loop-attaches an optical
  boot disk whose GPT the kernel can't parse. archiso's hybrid ISO triggers this, the attach fails
  ("No suitable partitions found"), and the system shows as degraded. The live root is mounted by
  the archiso hook, so this feature has nothing to do.

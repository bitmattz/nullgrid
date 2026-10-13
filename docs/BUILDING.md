# Building NULLGRID

## Host requirements

| Need | Why | Install (Debian/Ubuntu/Zorin) | Install (Arch) |
|---|---|---|---|
| Docker (user in `docker` group) | everything Arch-specific runs in the `nullgrid-builder` image | `sudo apt install docker.io` | `sudo pacman -S docker` |
| ~15 GB free disk | package cache + build tree (Docker volume `nullgrid-work`) + ISO | | |
| QEMU + OVMF (optional) | `make run` on the host with a GUI window | `sudo apt install qemu-system-x86 ovmf` | `sudo pacman -S qemu-desktop edk2-ovmf` |
| `/dev/kvm` access (optional) | fast VMs; without it QEMU falls back to slow emulation | add yourself to the `kvm` group | same |

The host does **not** need to run Arch. `make check-host` reports what's missing.

## Targets

| Command | What it does |
|---|---|
| `make builder` | builds the `nullgrid-builder` Docker image (Arch + archiso + QEMU) |
| `make repo` | builds every `pkg/*/PKGBUILD` into the local pacman repo `out/repo/` |
| `make iso` | `repo`, then `mkarchiso` → `out/nullgrid-YYYY.MM.DD-x86_64.iso` |
| `make run` / `run-bios` / `run-gl` | boot the newest ISO in QEMU: UEFI / legacy BIOS / UEFI + virgl 3D (for Hyprland, later phases) |
| `make test` | unit + snapshot tests of `nullgrid` and `nullgrid-dash`, in the builder container |
| `make test-boot` / `test-boot-bios` | headless boot in Docker: logs in over serial and checks systemd state, branding, sudo, NetworkManager, that `nullgrid` can switch themes and passes `doctor`, and that the terminal apps load their generated configs. It also screenshots tty1 (dashboard, theme switch, shell) into `out/screens/` |
| `make shell` | interactive shell inside the builder |
| `make clean` / `distclean` | remove `out/` / also the Docker work volume |

`run-vm.sh` honours `MEM` (default `4G`) and `CPUS` (default `2`), e.g. `MEM=2G make run`.

## How the build works

1. `build/build-packages.sh` runs `makepkg` for each directory in `pkg/` (as an unprivileged
   user inside the container) and indexes the results with `repo-add` into `out/repo/`.
2. `iso/pacman.conf` lists that directory as the `[nullgrid]` repo, so `iso/packages.x86_64`
   can install NULLGRID's own packages like any other package.
3. `build/build-iso.sh` runs `mkarchiso` on `iso/` in a privileged container. The work tree lives
   in a Docker volume so no root-owned files land in the repo, and output is `chown`ed back to you.

## Using the ISO elsewhere

The ISO is a standard hybrid image. It boots in VirtualBox, virt-manager or VMware (UEFI or BIOS),
or from a USB stick (`dd if=out/nullgrid-*.iso of=/dev/sdX bs=4M status=progress oflag=sync`).
The live user is `nullgrid` with passwordless sudo.

## Working on the `nullgrid` tool without building an ISO

From a checkout, the tool finds `themes/` and `config/templates/` in the repo by itself:

```sh
python3 -m venv .venv && .venv/bin/pip install jinja2 tomlkit pytest
PYTHONPATH=tools/nullgrid .venv/bin/python -m nullgrid theme list
.venv/bin/python -m pytest tests/nullgrid
```

Set `HOME` (or `XDG_CONFIG_HOME` and `XDG_STATE_HOME`) to a scratch directory to keep it away
from your own configs.

# Installing NULLGRID

Boot the ISO, then start the installer:

- **Desktop:** start menu → *Install NULLGRID* (opens it in a terminal window)
- **Terminal:** `sudo nullgrid-install`, or `install` in the TTY dashboard's launcher

The installer is a TUI that works in kitty and on a bare Linux console alike. It asks for:

| Step | What |
|---|---|
| DISK | the disk to install to (it is **erased**), and optionally LUKS2 encryption with a passphrase |
| ACCOUNT | your user (gets `sudo` with its password; root has no password), the hostname |
| REGION | keyboard layout, language (locale), time zone |
| DRIVERS | extra GPU packages: recommended / open only / NVIDIA (see below) |
| CONFIRM | a summary; type `ERASE` to start |

Then it installs (a few minutes; the log goes to `/var/log/nullgrid-install.log`, and is copied
to the installed system) and offers to reboot. Remove the USB stick or ISO first.

## What it does

The installed system is **a copy of the live system** (its read-only image, not the running
session), so no network is needed and you get exactly what you tried live. Then:

- **Disk:** GPT. 1 GiB FAT32 `/boot` (the EFI system partition, also marked BIOS-bootable), the
  rest ext4 `/`, inside LUKS2 if you chose encryption. No swap partition.
- **Boot loaders, both:** systemd-boot for UEFI (also at the fallback path `EFI/BOOT/BOOTX64.EFI`,
  for firmware that forgets its boot entries) and syslinux for legacy BIOS. The disk boots on
  either kind of machine. Each has a normal entry (splash) and a fallback one (boot messages,
  initramfs without autodetection).
- **Boot and login:** the Plymouth splash (it also asks for the LUKS passphrase), the console font
  and palette set early (`kms consolefont plymouth` hooks, `fbcon=nodefer`), and the greeter
  (greetd + tuigreet) instead of the live ISO's autologin.
- **Removed:** the live user `nullgrid`, autologin, passwordless sudo, the RAM-only journal and
  keyring, the archiso boot image. Your system gets its own pacman keyring.
- **Keyboard:** console keymap in `/etc/vconsole.conf`, XKB layout in
  `/etc/X11/xorg.conf.d/00-keyboard.conf`. The desktop reads the latter (Hyprland and Sway), so
  `localectl set-x11-keymap de` changes it for the next session.

## GPU drivers

Mesa (on the ISO) already drives Intel, AMD and older NVIDIA cards, which is all the desktop
needs. The installer adds, when it can download them:

| GPU | Recommended | Why |
|---|---|---|
| Intel | `vulkan-intel intel-media-driver` | Vulkan, hardware video decoding |
| AMD | `vulkan-radeon` | Vulkan (video decoding is in Mesa) |
| NVIDIA GTX 16xx / RTX 20xx and newer | `nvidia-open nvidia-utils` | the proprietary driver (open kernel modules); `nvidia_drm.modeset=1`; modules in the initramfs so the splash shows on it |
| NVIDIA + Intel/AMD (hybrid laptop) | the above + `nvidia-prime` | the integrated GPU drives the screen; `prime-run app` runs an app on NVIDIA |
| older NVIDIA | `vulkan-nouveau` | Arch no longer packages the legacy drivers: nouveau |

*Open only* downloads nothing. *NVIDIA* forces the proprietary driver. Without a network the
install still completes; the first-run wizard then shows the `pacman` command to run later.

When NVIDIA drives the screen, `nullgrid-session` exports `LIBVA_DRIVER_NAME=nvidia` and
`__GLX_VENDOR_LIBRARY_NAME=nvidia`, and Sway gets `--unsupported-gpu`.

## First boot

Log in at the greeter. The first login on a console runs **`nullgrid-welcome`**: pick a theme
(applied right away, so you see it), a sound pack (each one plays a sample) or *muted*, and
desktop or terminal mode. `ESC` skips it. Run `nullgrid-welcome` again any time, or script it:

```sh
nullgrid-welcome --theme ice-protocol --sound minimal-ops --mode desktop
```

## Unattended installs

The same answers can come from a TOML file (the boot test does this):

```toml
[disk]
device = "/dev/vda"
encrypt = false
passphrase = ""

[user]
username = "ada"
fullname = "Ada"
password = "change-me"
hostname = "deck"

[region]
locale = "en_US.UTF-8"
keyboard = "us"          # a console keymap: us, uk, de-latin1, br-abnt2, fr-latin1, ... (nullgrid_install/options.py)
timezone = "Europe/Berlin"

[drivers]
gpu = "auto"             # auto | open | nvidia

[boot]
serial_console = "auto"  # auto: when the live system was booted with console=ttyS0
```

```sh
sudo nullgrid-install --config install.toml --dry-run   # print every command and file, touch nothing
sudo nullgrid-install --config install.toml             # asks you to type ERASE; --yes skips that
nullgrid-install --list-disks                           # what it could install to
nullgrid-install --detect                               # firmware, GPUs, the drivers it would add
```

## Testing

`make test-install` (Docker + KVM, ~10 minutes) boots the ISO with a blank 24 GB virtual disk,
installs to it unattended, then boots the disk with UEFI and checks the installed system over
serial: the live leftovers are gone, the greeter runs, keyboard/locale/time zone, sudo asks for
the password, the pacman keyring, the splash in the initramfs. On tty1 it logs in through the
greeter and walks through the first-run wizard into TTY mode. Then it boots the same disk with
legacy BIOS. `make test-install ENCRYPT=1` does the same with LUKS, typing the passphrase into
the boot splash. Screenshots: `out/screens/installed-*.png`.

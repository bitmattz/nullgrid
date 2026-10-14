# Changelog

All notable changes to NULLGRID OS. Versions follow [semantic versioning](https://semver.org/);
the version lives in `VERSION` and every NULLGRID package carries it.

## Unreleased

- **Wi-Fi and Bluetooth pickers in the bar.** Click the Wi-Fi icon: networks in range with
  signal bars and security, connect with a click, type a password inline, disconnect/forget;
  a wrong password shows and asks again. Click the Bluetooth icon: paired devices (connect,
  disconnect, battery, forget) and devices in range (pair + trust + connect). Right click still
  turns the radio on/off. `nullgrid-shell wifi|bluetooth` opens them.
- **Bluetooth works at all now:** `bluez` and `bluez-utils` are installed and the service is
  enabled (it starts when an adapter appears). In 1.0.0 the Bluetooth toggle never showed.
- **`dnsmasq`** on the ISO: NetworkManager hotspots and connection sharing (`nmtui` "Hotspot").
- Tests: the boot test joins a real NetworkManager hotspot through the picker (two virtual
  radios, `mac80211_hwsim`), wrong password first; the shell test drives both pickers with fake
  networks and devices (`NULLGRID_SHELL_DEMO=1`).

## 1.0.0 (2026-10-14)

The first release: all nine build phases of the project brief. Release notes:
[docs/releases/v1.0.0.md](docs/releases/v1.0.0.md).

- **Base:** Arch Linux live/install ISO (archiso), UEFI and legacy BIOS, Plymouth splash,
  autologin on the live ISO, greetd + tuigreet on installed systems.
- **Desktop:** Hyprland (Sway fallback and `lite` profile), the NULLGRID shell in Quickshell
  (bar, dock, HUD widgets, start menu, notifications), hyprlock HUD lock screen, generated
  wallpaper, fuzzel launcher.
- **Terminal and TTY mode:** kitty, zsh, starship, fastfetch, themed btop/yazi/neovim/lazygit/
  cava/tmux; the console dashboard `nullgrid-dash`.
- **Theme engine:** `nullgrid` CLI and `nullgrid.toml`; 32 generated configs, live theme switching;
  presets crimson-hud, ice-protocol, toxic-grid; GTK/Qt themes, generated icons and cursors.
- **Sound:** `nullgrid-sfx` daemon, synthesized packs neural-link and minimal-ops.
- **Installer:** `nullgrid-install` (offline, LUKS2 optional, both boot loaders, GPU drivers) and
  the first-run wizard `nullgrid-welcome`.
- **Performance tooling:** `nullgrid perf`, `make perf`; idle desktop 718-738 MiB (Hyprland) /
  585-608 MiB (lite) in a 4 GB VM without 3D.
- **Tests:** `make test`, `test-shell`, `test-boot`, `test-install`, `perf`.

Known limitations: see the release notes (VM-tested only; NULLGRID packages don't update through
pacman yet; no Secure Boot; x86_64 only).

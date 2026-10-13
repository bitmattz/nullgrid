# NULLGRID OS

A lightweight, terminal-first Arch Linux distro with a cyberpunk HUD look:
dark crimson, neon cyan, chamfered frames, live system widgets and subtle UI sounds.
It's meant to run on old ThinkPads, Raspberry Pis (planned) and DIY cyberdecks.

> Status: **phase 6 (sound)**. The ISO boots into a Hyprland desktop (Sway as fallback and
> lite session) with the NULLGRID shell: status bar, dock, HUD widgets, start menu, notifications
> and a HUD lock screen, over a generated wallpaper, with synthesized UI sounds on PipeWire.
> TTY mode gives a themed dashboard instead. Everything, down to zsh, kitty and neovim, is styled
> from one TOML file by the `nullgrid` tool. GTK/Qt theming, the boot splash and the installer
> come in later phases (see `CLAUDE.md` section 9).

## Screenshots

Taken by `make test-boot` on the live ISO in QEMU (1600x900, no 3D: software rendering).

| | |
|---|---|
| ![Desktop, crimson-hud](docs/screenshots/desktop-hyprland.png) | ![Start menu](docs/screenshots/desktop-hyprland-menu.png) |
| **Desktop** (crimson-hud): status bar, dock, HUD widgets, the login terminal, the generated wallpaper | **Start menu** (`SUPER+SPACE`): search, categories, favorites, power |
| ![Live theme switch with notifications](docs/screenshots/desktop-hyprland-notifications.png) | ![Lock screen](docs/screenshots/desktop-lock.png) |
| **`nullgrid theme set toxic-grid`** restyles everything live; notifications (critical in red) | **Lock screen** (`SUPER+CTRL+L`) |
| ![Keybind popup](docs/screenshots/desktop-hyprland-keys.png) | ![Sway session](docs/screenshots/desktop-sway.png) |
| **`SUPER+/`**: the keybinds, from the same file Hyprland and Sway use | **Sway**: the fallback and `lite` session, same shell |
| ![TTY dashboard](docs/screenshots/tty1-dashboard.png) | ![Wallpaper, ice-protocol](docs/screenshots/wallpaper-ice-protocol.png) |
| **TTY mode**: the dashboard on the Linux console | **The wallpaper** alone (ice-protocol): circuit traces, logo plate, keymap, data blocks, all generated |

## Quick start

```sh
make iso         # build out/nullgrid-*.iso inside Docker (any Linux host)
make run         # boot it in QEMU (UEFI); needs qemu + OVMF on the host
make test        # unit + snapshot tests of the nullgrid tool and the sound daemon (Docker)
make sounds      # synthesize the sound packs into out/sounds (Docker)
make test-shell  # the desktop shell in a headless Sway: QML errors, IPC, screenshots (Docker)
make test-boot   # headless boot test; needs only Docker
```

```sh
nullgrid theme list               # crimson-hud, ice-protocol, toxic-grid
nullgrid theme set ice-protocol   # restyle everything live
nullgrid keys                     # the desktop keybinds (SUPER+/ shows them too)
nullgrid sound test all           # hear the active sound pack; sound set minimal-ops, sound mute
nullgrid mode tty                 # log in to the TTY dashboard instead of the desktop
nullgrid doctor                   # check config and generated files
```

See [docs/BUILDING.md](docs/BUILDING.md) for requirements and details.

## Docs

- [BUILDING.md](docs/BUILDING.md): build and run
- [CUSTOMIZING.md](docs/CUSTOMIZING.md): `nullgrid.toml`, themes, templates
- [DESKTOP.md](docs/DESKTOP.md): the desktop session, keybinds, wallpaper
- [TERMINAL.md](docs/TERMINAL.md): shell, apps, TTY mode and the dashboard
- [SOUND.md](docs/SOUND.md): UI sounds, events, sound packs
- [DECISIONS.md](docs/DECISIONS.md): design choices and why
- [STYLE.md](docs/STYLE.md): visual style guide
- [LOGO.md](docs/LOGO.md): the logo
- [assets/LICENSES.md](assets/LICENSES.md): licenses of all bundled assets

## License

MIT (see `LICENSE`). Bundled third-party assets keep their own licenses (see `assets/LICENSES.md`).

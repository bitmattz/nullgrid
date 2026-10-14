# Updating

NULLGRID updates through pacman, like the rest of the system. Its own packages (`nullgrid-*`)
come from the signed `[nullgrid]` repository; everything else from Arch.

```sh
nullgrid update        # sudo pacman -Syu, then refresh your NULLGRID configs right away
```

`nullgrid update` runs `sudo pacman -Syu`, then brings your generated configs and default
dotfiles up to date (files you edited by hand are kept, with `.bak` copies where a generated
file had edits), restarts the desktop shell if it was updated, and tells you when to log out
(Hyprland was updated) or reboot (the kernel was). It ends with a `nullgrid doctor` summary.

Plain `sudo pacman -Syu` works too: then every user's configs refresh at their next login (a
pacman hook marks the update; zsh notices).

Options: `nullgrid update --yes` (no questions from pacman), `--no-system` (only refresh the
configs), `--restart-shell`.

## Systems installed from 1.0.0: set up updates once

1.0.0 didn't know about the repository yet. Once, in a terminal:

```sh
curl -LO https://github.com/bitmattz/nullgrid/releases/download/repo/nullgrid-keyring-20261014-1-any.pkg.tar.zst
sudo pacman -U nullgrid-keyring-20261014-1-any.pkg.tar.zst
pacman-key --finger 3494FF826CBF4E4AB1E83049FD658A9D368049E7   # must show "NULLGRID packages"
sudo pacman -Syu
```

The keyring package adds NULLGRID's signing key to pacman's keyring and the `[nullgrid]`
section to `/etc/pacman.conf`. The fingerprint check shows you trusted the right key: it must
be exactly `3494 FF82 6CBF 4E4A B1E8  3049 FD65 8A9D 3680 49E7`. Then log out and back in (or
run `nullgrid update --no-system`). From then on, `nullgrid update` is all it takes.

Systems installed from a 1.1.0 or newer ISO have all this already.

## What's in the repository

- `[nullgrid]` in `/etc/pacman.conf`, `SigLevel = Required DatabaseRequired`: pacman refuses
  packages or a package list that aren't signed by the NULLGRID key.
- Server: `/etc/pacman.d/nullgrid-mirrorlist`, the `repo` release of
  [github.com/bitmattz/nullgrid](https://github.com/bitmattz/nullgrid/releases/tag/repo).
- It carries released versions only (see [CHANGELOG.md](../CHANGELOG.md)); a new ISO may come
  later than the packages.

## Troubleshooting

- **`signature from "NULLGRID packages" is invalid` / `unknown trust`**: the key isn't in
  pacman's keyring. `sudo pacman-key --populate nullgrid` (the keyring package does it).
- **`failed retrieving file 'nullgrid.db'`**: no network, or GitHub is unreachable. Arch's
  repositories still update; try again later.
- **The desktop looks broken after an update**: `nullgrid doctor`, then `nullgrid update
  --no-system --restart-shell`. If Hyprland itself was updated, log out and back in. As a last
  resort, the TTY mode (`nullgrid mode tty`, or pick "NULLGRID terminal" at the greeter) works
  without the desktop.
- **Stop NULLGRID updates**: remove the `[nullgrid]` section from `/etc/pacman.conf`.

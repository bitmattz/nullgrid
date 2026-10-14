# Boot splash, greeter and console

Package `nullgrid-boot`: everything you see before your own session starts. It runs before any
user's theme is known, so it always uses the **crimson-hud** colors.

## Boot splash (Plymouth)

A "system boot" HUD: the lattice logo flickers on, then its dead pixel wanders from cell to cell.
A scanline sweeps down the screen, a fake boot log scrolls at the bottom left and a segmented bar
fills with the boot progress. Shutdown and reboot show the same screen with their own caption.
Encrypted disks ask for the passphrase in an "AUTHENTICATION REQUIRED" frame.

- Theme files: `/usr/share/plymouth/themes/nullgrid/`. All images, text included, are drawn at
  package build time by `plymouth/generate.py` (from the logo geometry and the theme colors), and
  `plymouth/nullgrid.script` animates them.
- On the live ISO: kernel options `quiet splash plymouth.ignore-serial-consoles`, the `plymouth`
  hook in the initramfs, `Theme=nullgrid` in `/etc/plymouth/plymouthd.conf`. The second boot menu
  entry ("boot messages") shows the kernel and systemd output instead.
- On an installed system: `sudo plymouth-set-default-theme -R nullgrid` (sets the theme and
  rebuilds the initramfs). The `plymouth` hook must be in `/etc/mkinitcpio.conf`, and the kernel
  needs `quiet splash`.
- Press Esc during boot to see the messages behind the splash.

Preview without a VM: `make splash` runs the theme with Plymouth's X11 renderer in the builder
container and writes `out/screens/splash-*.png` (boot, password prompt, shutdown).

## Greeter (greetd + tuigreet)

A text-mode login on the first console: a matrix-rain background, a "NULLGRID // NODE ACCESS"
frame, date and time. F3 picks the session:

- **NULLGRID desktop**: Hyprland, with Sway as fallback (as `nullgrid mode desktop`),
- **NULLGRID terminal**: TTY mode, the console dashboard (as `nullgrid mode tty`).

tuigreet remembers the last user and each user's last session. F12 offers shutdown and reboot.
Leaving the desktop brings the greeter back.

The live ISO logs in by itself and doesn't run the greeter. On an installed system:

```sh
sudo systemctl disable getty@tty1     # if it auto-logs in
sudo systemctl enable greetd
```

Files: `/etc/tuigreet/config.toml` (look and sessions; yours to edit), the sessions in
`/usr/share/nullgrid/sessions/`, the greetd config in `/usr/share/nullgrid/greetd/greetd.toml` (a
drop-in for `greetd.service` points greetd there). Both sessions run `nullgrid-login desktop|tty`:
the normal zsh login, told which mode to start.

## Console colors

`nullgrid-console-palette.service` loads the crimson-hud colors into the Linux console as soon as
the splash is gone (`setvtrgb /usr/share/nullgrid/console/vtrgb`; Plymouth puts back the colors it
found when it quits), so the greeter, the login prompt and later boot messages match the theme.
After you log in, your own theme's console colors apply (`[theme]` in `nullgrid.toml`).
`nullgrid theme palette --format vtrgb` prints any theme in that format.

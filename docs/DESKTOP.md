# The desktop

Logging in on tty1 starts the desktop when `nullgrid mode` is `desktop` (the default). It's a
Hyprland session with neon window borders, a generated HUD wallpaper, and the NULLGRID shell:
status bar, dock, HUD widgets, start menu and notifications, with UI sounds from the
`nullgrid-sfx` daemon ([SOUND.md](SOUND.md)). Sway takes over on GPUs where Hyprland can't
start, and when `[performance] profile = "lite"` is set.

## Keybinds

`SUPER+/` shows all of them in a popup, and `nullgrid keys` prints them in a terminal. The
defaults:

| Keys | Action |
|---|---|
| `SUPER+ENTER` | terminal (kitty) |
| `SUPER+SPACE` | start menu |
| `SUPER+D` | app launcher (fuzzel) |
| `SUPER+E` | file manager (yazi) |
| `` SUPER+` `` | system dashboard |
| `SUPER+B` | btop |
| `SUPER+/` | show keybinds |
| `SUPER+T` | next theme |
| `SUPER+CTRL+L` | lock screen (on the live ISO the password is `nullgrid`; the lock screen says so) |
| `PRINT` / `SHIFT+PRINT` | screenshot of a region / the screen, saved to `~/Pictures/Screenshots` and copied |
| `SUPER+Q` | close window |
| `SUPER+F` / `SUPER+V` | fullscreen / float or tile |
| `SUPER+arrows` or `SUPER+H/J/K/L` | move focus |
| `SUPER+SHIFT+arrows` or `+H/J/K/L` | move the window |
| `SUPER+1..0` / `SUPER+SHIFT+1..0` | go to / move the window to workspace 1-10 |
| `SUPER+mouse` | left button drags a window, right button resizes it |
| `SUPER+SHIFT+E` | leave the desktop (back to the tty1 shell; `nullgrid-session` starts it again) |
| volume keys, mute, mic mute | volume of the default output (PipeWire), with a tick; they also work on the lock screen |
| brightness keys | screen brightness (brightnessctl), with a tick; also on the lock screen |

Lock, leave and the media keys run small scripts that also play the matching sound:
`nullgrid-lock`, `nullgrid-power logout|reboot|poweroff|suspend` (the start menu's power
buttons use it too) and `nullgrid-media volume up|down|mute`, `mic mute`,
`brightness up|down`.

### Your own keybinds

The binds come from a **keybind set**, `keybinds/<name>.toml`. One file drives Hyprland, Sway,
`nullgrid keys` and the keymap on the wallpaper, so they always agree.

```sh
mkdir -p ~/.config/nullgrid/keybinds
cp /usr/share/nullgrid/keybinds/default.toml ~/.config/nullgrid/keybinds/mine.toml
$EDITOR ~/.config/nullgrid/keybinds/mine.toml      # set meta.name = "mine"
```

Then set `[behavior] keybinds = "mine"` in `nullgrid.toml` and run `nullgrid theme reload`.
Hyprland and Sway reload by themselves.

```toml
[meta]
name = "mine"

[keys]                          # action = combo, or a list of combos
terminal = "ALT+Return"
focus_left = ["SUPER+Left", "SUPER+H"]
workspace = "SUPER"             # modifiers only: + 1..9, 0
launcher = []                   # unbound

[exec]                          # extra binds: combo = command
"SUPER+W" = "firefox"
```

Combos are modifiers (`SUPER SHIFT CTRL ALT`) plus one xkb key name (`Return`, `Left`,
`slash`, `F1`, `Print`...). A combo bound twice is an error that names both places.

## The shell

The shell is a [Quickshell](https://quickshell.org) config (QML) in
`/etc/xdg/quickshell/nullgrid/` (`shell/` in the repo). The session starts it with
`nullgrid-shell`. It takes its colors, fonts and layout from
`~/.config/nullgrid/generated/theme.json` and restyles as soon as `nullgrid theme ...` changes it.

- **Status bar** (bottom): mode and profile, workspaces, window title, now playing (MPRIS), tray,
  quick toggles (Wi-Fi, Bluetooth, brightness, volume: click toggles, scroll adjusts), CPU, RAM,
  GPU, network down/up, CPU/GPU temperature, battery and power draw, date and time. Readings that
  the hardware doesn't have are left out.
- **Dock** (left): the start button, then pinned apps (terminal, files, editor, monitor,
  dashboard, settings) as circular buttons. The focused app's button is hatched, and a dot
  marks running ones. Below: a dot per workspace and the current workspace's number.
- **HUD widgets** (bottom right, under the windows): RAM gauge, CPU per-core bars with load
  average, network graph with its scale, CPU activity dot matrix, and the workspace strip.
- **Start menu** (`SUPER+SPACE` or the dock's top button): type to search, arrows and Enter to
  launch, Esc to close. Categories on the left, favorites by default. At the bottom: lock, log
  out, sleep, restart and shut down. Log out, restart and shut down ask for a second click.
- **Notifications**: chamfered cards in the top right corner. Critical ones are red and stay
  until clicked; the others go after 6 s (or the sender's timeout). Hovering keeps them.
- **Matrix rain**: a few falling character columns over the wallpaper (`decor.matrix_rain`).
  Off with `reduce_motion` and with the lite profile.
- **Lock screen**: hyprlock, as a "system locked" HUD over the blurred wallpaper.
  `~/.config/hypr/hyprlock.conf` is yours; its colors come from the generated
  `nullgrid-hyprlock.conf`.

Show or hide parts with `nullgrid widget toggle <name>`, and move them with `position` in
`[widgets]`: the bar `top`/`bottom`, the dock `left`/`right`, and each HUD widget any of the
eight positions. Widgets at the same position stack together.

```sh
nullgrid-shell menu      # open/close the start menu
nullgrid-shell status    # what the running shell sees
nullgrid-shell restart   # e.g. after changing the QML
nullgrid-shell log       # its log
```

To change the shell itself, copy it and edit: `cp -r /etc/xdg/quickshell/nullgrid
~/.config/quickshell/`. Your copy wins, and Quickshell reloads it on every save.

## Configs

| File | Who writes it | |
|---|---|---|
| `~/.config/hypr/hyprland.lua` | you (copied once by `nullgrid init`) | loads the three below, then your settings |
| `/usr/share/nullgrid/hypr/nullgrid.lua` | package | defaults: input, layout, window rules, autostart |
| `~/.config/hypr/nullgrid-theme.lua` | nullgrid | borders, glow, blur, gaps, animations, from the theme |
| `~/.config/hypr/nullgrid-keys.lua` | nullgrid | the keybind set |
| `~/.config/sway/config` | you | includes the Sway counterparts: `/usr/share/nullgrid/sway/nullgrid.conf`, `nullgrid-theme`, `nullgrid-keys` |

Hyprland 0.55+ reads Lua (`hyprland.lua`). `nullgrid-theme.lua` returns the palette, so your own
rules can use it, for example `border_color = ng.primary`.

## Wallpaper and decor

The wallpaper is drawn for each screen's exact resolution from the theme and `[decor]`. It
includes:
- circuit traces with vias along the edges, and corner brackets (`circuit_lines`);
- faint character columns (`matrix_rain`);
- a barcode/ID strip, a "system manifest" block, a warning triangle, a hex dump, and the keymap
  (`data_text`);
- optional scanlines (`scanlines`);
- always: the NULLGRID logo plate (top right), a dot grid, and a large faint lattice behind the windows.

The logo plate, data blocks and keymap stay out of the areas where the dock, bar and HUD
widgets go.

```sh
nullgrid wallpaper apply                        # render for every screen and show it (swaybg)
nullgrid wallpaper render --size 2560x1440 -o wall.png   # or .svg, or SVG to stdout
```

`nullgrid theme set` re-renders it on the fly. Renders are cached in `~/.cache/nullgrid/wallpaper/`;
`current.png` there links to the one in use (the lock screen shows it). The moving matrix
columns are drawn by the shell.

## Sessions

`nullgrid-session [hyprland|sway]` starts the desktop on the current VT. tty1 runs it at login
in desktop mode. Without an argument, it picks Hyprland, or Sway for the lite profile. If the
compositor quits within 10 seconds (for example on a GPU Hyprland doesn't support), it tries the
other one, and as a last resort Sway with pure software rendering. If nothing starts, the login
falls back to TTY mode (the dashboard). `nullgrid doctor` shows what happened at the last start;
the compositors' output is in `~/.local/state/nullgrid/session-<name>.log`.

### In VirtualBox

Use the VMSVGA graphics controller with "Enable 3D Acceleration" on and 128 MB video memory,
and give the VM at least 4 GB of RAM. Without 3D, Hyprland may not start there and the session
falls back to Sway.

Sway is the plain variant. It has no blur, glow, gradients or animations, and a solid neon
border marks the active window. On NVIDIA's proprietary driver it starts with `--unsupported-gpu`.

### In a VM

`make run` uses virtio-gpu without 3D. Mesa then renders in software (llvmpipe). That works
and uses no CPU at idle, but animations and blur are slower. `make run-gl` turns on virgl 3D.
For long sessions in a VM, `[performance] profile = "lite"` helps.

# The desktop

Logging in on tty1 starts the desktop when `nullgrid mode` is `desktop` (the default). It's a
Hyprland session with neon window borders and a generated HUD wallpaper. Sway takes over on
GPUs where Hyprland can't start, and when `[performance] profile = "lite"` is set. The dock,
status bar and HUD widgets arrive in phase 5.

## Keybinds

`SUPER+/` shows all of them in a popup, and `nullgrid keys` prints them in a terminal. The
defaults:

| Keys | Action |
|---|---|
| `SUPER+ENTER` | terminal (kitty) |
| `SUPER+D` | app launcher (fuzzel) |
| `SUPER+E` | file manager (yazi) |
| `` SUPER+` `` | system dashboard |
| `SUPER+B` | btop |
| `SUPER+/` | show keybinds |
| `SUPER+T` | next theme |
| `SUPER+CTRL+L` | lock screen |
| `PRINT` / `SHIFT+PRINT` | screenshot of a region / the screen, saved to `~/Pictures/Screenshots` and copied |
| `SUPER+Q` | close window |
| `SUPER+F` / `SUPER+V` | fullscreen / float or tile |
| `SUPER+arrows` or `SUPER+H/J/K/L` | move focus |
| `SUPER+SHIFT+arrows` or `+H/J/K/L` | move the window |
| `SUPER+1..0` / `SUPER+SHIFT+1..0` | go to / move the window to workspace 1-10 |
| `SUPER+mouse` | left button drags a window, right button resizes it |
| `SUPER+SHIFT+E` | leave the desktop (back to the tty1 shell; `nullgrid-session` starts it again) |

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

The logo plate, data blocks and keymap stay out of the areas where the phase 5 dock, bar and
HUD widgets go.

```sh
nullgrid wallpaper apply                        # render for every screen and show it (swaybg)
nullgrid wallpaper render --size 2560x1440 -o wall.png   # or .svg, or SVG to stdout
```

`nullgrid theme set` re-renders it on the fly. Renders are cached in `~/.cache/nullgrid/wallpaper/`.
The animated layer (moving matrix columns) comes with the Quickshell overlay in phase 5.

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

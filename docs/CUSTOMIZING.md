# Customizing NULLGRID

Everything about the look and behavior lives in one file, `~/.config/nullgrid/nullgrid.toml`.
The `nullgrid` command reads it, renders a config file for each app from templates, and reloads
the apps that are running. You never set the same color in twelve places.

## The `nullgrid` command

| Command | What it does |
|---|---|
| `nullgrid theme list` | list theme presets; `*` marks the active one, `[user]` your own |
| `nullgrid theme set <name>` | switch preset, regenerate everything, reload running apps |
| `nullgrid theme set <name> --reset-colors` | ...and drop your `[theme.colors]` overrides |
| `nullgrid theme next` / `prev` | switch to the next / previous preset (`SUPER+T` on the desktop) |
| `nullgrid theme edit` | open `nullgrid.toml` in `$EDITOR`; on save it's validated, then applied. An invalid edit can be re-edited or reverted |
| `nullgrid theme reload` | regenerate every file and reload every running app (`--dry-run`: only list what would change) |
| `nullgrid widget list` / `widget toggle <name>` | show or hide a desktop widget |
| `nullgrid keys [--pause]` | list the desktop keybinds (see [DESKTOP.md](DESKTOP.md)) |
| `nullgrid wallpaper apply` | render the HUD wallpaper for every screen of the running session and show it |
| `nullgrid wallpaper render [--size WxH] [-o FILE]` | write it as SVG or PNG (default: 1920x1080 SVG to stdout) |
| `nullgrid mode` / `mode desktop\|tty` | print or set the session started at login |
| `nullgrid init [--reset]` | set up a home: default dotfiles (existing ones kept unless `--reset`), `nullgrid.toml`, generated files. Runs by itself at first login |
| `nullgrid doctor [-v]` | check config, themes, templates, generated files, fonts, session. Exit code 1 only on real errors |

The first command that changes a setting creates `nullgrid.toml` from the commented default
(`/usr/share/nullgrid/nullgrid.toml`). Edits made by the CLI keep your comments and formatting.
A config that doesn't validate is never written and never applied: the last good files stay in place.

## `nullgrid.toml`

Every key is optional. Unknown keys are errors (with a "did you mean" hint), so typos don't
silently do nothing.

### `[theme]`

| Key | Default | |
|---|---|---|
| `preset` | `"crimson-hud"` | a name from `nullgrid theme list` |
| `[theme.colors]` | | override any palette color of the preset (see below) |
| `[theme.colors.terminal]` | | override terminal colors |
| `[theme.fonts]` | | `ui`, `mono`, `display` (font family names), `size`, `mono_size` (pt) |
| `[theme.style]` | | `border_width` (0-8), `glow` (0-1), `corners` (`sharp`/`chamfer`/`round`), `surface_opacity`, `terminal_opacity` (0.3-1), `blur` (bool), `gaps` (px) |

Overrides apply on top of whatever preset is active, also after `theme set`. `doctor -v` lists them.

### `[sound]`

`enabled`, `volume` (0-1), `pack` (`neural-link` / `minimal-ops`),
`[sound.quiet_hours]` (`enabled`, `start`, `end` as `"HH:MM"`, `volume` multiplier) and
`[sound.events]` with one entry per event, e.g. `window_open = { enabled = true, volume = 0.5 }`.
The `nullgrid sound` commands change the common ones; [SOUND.md](SOUND.md) explains every event
and how to make a sound pack.

Events: `boot login logout shutdown workspace_switch window_open window_close window_focus
launcher_open launcher_close menu_hover button_click notification notification_critical
volume_change brightness_change usb_connect usb_disconnect battery_low charger_plug screenshot
error lock unlock terminal_bell command_done command_failed`. Off by default: `window_focus`,
`menu_hover`, `terminal_bell`, `command_done`, `command_failed`.

### `[widgets]`

`dock bar ram_gauge net_graph cpu_bars workspace_strip activity_grid`, each
`{ visible = bool, position = "..." }` with positions `top bottom left right top-left top-right
bottom-left bottom-right`. The bar goes `top` or `bottom`, the dock `left` or `right`; HUD
widgets that share a position stack together. The shell applies changes at once.

### `[decor]`, `[behavior]`, `[performance]`

| Key | Default | |
|---|---|---|
| `decor.circuit_lines` | `true` | wallpaper: circuit traces and corner brackets |
| `decor.matrix_rain` | `true` | wallpaper: faint character columns |
| `decor.data_text` | `true` | wallpaper: barcode, data blocks, warning triangle, keymap |
| `decor.scanlines` | `false` | wallpaper: scanline overlay |
| `behavior.animation_speed` | `1.0` | multiplier, 0.25-4 (2 = twice as fast) |
| `behavior.reduce_motion` | `false` | no animations or glitch effects |
| `behavior.default_mode` | `"desktop"` | `desktop` or `tty` |
| `behavior.keybinds` | `"default"` | keybind set: `keybinds/<name>.toml` in `~/.config/nullgrid/` or `/usr/share/nullgrid/` ([DESKTOP.md](DESKTOP.md)) |
| `behavior.greeting` | `"fastfetch"` | `none`: no fastfetch when a desktop terminal opens |
| `performance.profile` | `"full"` | `lite`: the Sway session, no blur, glow or animations, slower widget refresh |

## Theme presets

Presets live in `/usr/share/nullgrid/themes/` and `~/.config/nullgrid/themes/` (yours win on a
name clash). To make your own, copy one, rename the file **and** `meta.name`:

```sh
mkdir -p ~/.config/nullgrid/themes
cp /usr/share/nullgrid/themes/crimson-hud.toml ~/.config/nullgrid/themes/my-theme.toml
$EDITOR ~/.config/nullgrid/themes/my-theme.toml     # set meta.name = "my-theme"
nullgrid theme set my-theme
```

A preset needs `[meta] name`, the nine `[colors]` (`bg bg_alt surface primary secondary glow
text dim warning`) and the 20 `[colors.terminal]` entries (`foreground background cursor
selection color0`..`color15`). `[fonts]` and `[style]` are optional (defaults as in the table above).
`doctor` warns when text or accent colors have too little contrast against the background.

## Generated files

| Name | File | Reloaded live |
|---|---|---|
| kitty | `~/.config/kitty/nullgrid-theme.conf` | yes (SIGUSR1) |
| hyprland / hyprland-keys | `~/.config/hypr/nullgrid-theme.lua` / `nullgrid-keys.lua` | yes (`hyprctl reload`) |
| sway / sway-keys | `~/.config/sway/nullgrid-theme` / `nullgrid-keys` | yes (`swaymsg reload`) |
| wallpaper | `~/.config/nullgrid/generated/wallpaper.json` (the wallpaper's input) | yes (`nullgrid wallpaper apply`) |
| hyprlock | `~/.config/hypr/nullgrid-hyprlock.conf` | read at each lock |
| quickshell | `~/.config/nullgrid/generated/theme.json` (the desktop shell's look and layout) | yes (file is watched) |
| fuzzel | `~/.config/fuzzel/fuzzel.ini` | read at each launch |
| btop | `~/.config/btop/themes/nullgrid.theme` | at next start |
| nvim | `~/.config/nvim/lua/nullgrid/palette.lua` | at next start |
| gtk | `~/.config/nullgrid/generated/gtk-colors.css` | phase 7 |
| qt | `~/.config/qt6ct/colors/nullgrid.conf` | at next start |
| tty | `~/.config/nullgrid/generated/tty-palette.sh` | yes, when run on a console |
| shell-env | `~/.config/nullgrid/generated/shell-env.sh` | next shell |
| banner | `~/.config/nullgrid/generated/banner` | next login |
| starship / starship-tty | `~/.config/starship.toml` / `starship-tty.toml` | next prompt |
| fastfetch | `~/.config/fastfetch/config.jsonc` | next run |
| tmux | `~/.config/tmux/nullgrid-theme.conf` | yes (`tmux source-file`) |
| yazi / yazi-tty | `~/.config/yazi/theme.toml` / `yazi-tty/theme.toml` | next start |
| lazygit | `~/.config/lazygit/config.yml` | next start |
| cava / cava-tty | `~/.config/cava/config` / `config-tty` | yes (SIGUSR1) |

Most are fragments that the app's main config includes, so the rest of that config stays yours.
If you edit a generated file by hand, the next render saves your version as `<file>.bak` before
replacing it (`doctor` tells you beforehand). Files whose content didn't change aren't touched,
and only apps whose file changed are reloaded.

## Templates

Templates are [Jinja](https://jinja.palletsprojects.com/) files in `/usr/share/nullgrid/templates/`,
listed in its `manifest.toml`. To change one, copy it to `~/.config/nullgrid/templates/` under the
same name. To add an app, put a template there and a `manifest.toml` next to it:

```toml
[foot]
template = "foot.ini.j2"
target = "{config_home}/foot/colors.ini"     # also {config_dir} = ~/.config/nullgrid, {home}
process = "foot"                             # optional reload hook: only if foot is running...
signal = "USR1"                              # ...send it a signal, or
# reload = ["some-cmd", "--reload", "{target}"]   ...run a command
# env = "WAYLAND_DISPLAY"                    # only if this env var is set (or "VAR=value")
# vars = { tty = true }                      # extra template variables (variants of one template)

[btop]
enabled = false                              # stop generating a system target
```

What templates can use:

| Name | Contents |
|---|---|
| `c` | the palette: `c.bg`, `c.primary`, ... |
| `t` | terminal colors: `t.foreground`, `t.color0`..`t.color15`, ... |
| `fonts`, `style` | the resolved `[fonts]` / `[style]` |
| `theme` | the whole theme, incl. `theme.meta.name` |
| `sound`, `widgets`, `decor`, `behavior`, `performance` | the config sections |
| `effects` | `blur`, `shadows`, `animations`, `lite` after applying `performance.profile` and `reduce_motion` |
| `keybinds`, `binds`, `keymap` | the keybind set; its binds (`combo`, `action`, `label`, `command`, `workspace`); the wallpaper's short list |
| `ms(base)` | an animation duration in ms scaled by `animation_speed` (0 when motion is off) |
| `header(prefix[, suffix])` | the "generated, don't edit" comment in the file's comment syntax |
| `Color("#rrggbb")` | make a color |
| `ansi(color)`, `ansi_roles` | the terminal palette slot (0-15) closest to a color, and that slot for each role (`ansi_roles.primary`, ...). Use these for anything that must also work on the Linux console |
| `ansi_name(i, flavor)` | how an app spells slot `i`: `plain` (`bright_cyan`), `starship`, `textual`, `ratatui` (yazi), `basic` (8 names) |
| `sgr(i[, bold])` | the escape sequence for slot `i` as foreground; `sgr()` resets |
| `\| json`, `\| tf`, `\| lua` | filters: JSON dump (colors as `"#rrggbb"`); `true`/`false`; a Lua string literal |
| `\| hypr_combo`, `\| sway_combo` | a key combo in Hyprland (`SUPER + Q`) or Sway (`Mod4+q`) spelling |

Colors print as `#rrggbb` and have formats and math built in:
`.hex` `.bare` (`rrggbb`) `.rgb` (`r, g, b`) `.hexa(a)` (`#rrggbbaa`) `.barea(a)` `.argb(a)`
(`#aarrggbb`, Qt) `.rgba(a)` (CSS) `.hypr(a)` (`rgba(rrggbbaa)`, Hyprland),
`.mix(other, t)` `.lighten(t)` `.darken(t)` `.contrast(other)` `.distance(other)` (perceptual, CIELAB).

Templates use `StrictUndefined`: a misspelled name is an error, and when any template fails
nothing is written. `nullgrid doctor` renders all of them as a check.

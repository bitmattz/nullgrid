# The terminal experience

NULLGRID is terminal-first. This page covers the shell, the apps, and TTY mode.

## First login

The first time a user's zsh starts, it runs `nullgrid init`. That command:
- copies the default dotfiles from `/usr/share/nullgrid/skel/` into the home (kitty, tmux, btop,
  neovim, Hyprland, Sway). Files that already exist are kept;
- creates `~/.config/nullgrid/nullgrid.toml`;
- renders every themed config.

To get the defaults back later, run `nullgrid init --reset`. Replaced files are kept as `.bak`.

## Shell (zsh)

`~/.zshrc` sources `/usr/share/nullgrid/zsh/nullgrid.zsh`, so improvements arrive with package
updates. Put your own settings below that line.

- **Plugins:** zsh-autosuggestions and zsh-syntax-highlighting (highlight colors follow the theme).
- **Prompt:** starship.
  - In kitty: angular powerline segments `user@host`, `dir`, `git`, with command duration and a clock on the right.
  - On the Linux console: a variant that only uses glyphs the console font has.
- **History** in `~/.local/state/zsh/history` (50k entries, shared between shells).

### Aliases

| Alias | Runs |
|---|---|
| `v` | `nvim` |
| `lg` | `lazygit` |
| `ff` | `fastfetch` |
| `hud` | `nullgrid-dash` |
| `y` | yazi. When you quit, the shell stays in the directory you left yazi in |
| `ll`, `la` | `ls -lh`, `ls -lAh` |

When a desktop terminal (kitty) opens, it greets with fastfetch. Turn that off with
`[behavior] greeting = "none"`.

## Apps

| App | Role | Config |
|---|---|---|
| kitty | terminal | `~/.config/kitty/kitty.conf` (yours) includes `nullgrid-theme.conf` (generated) |
| starship | prompt | generated whole: `starship.toml`, `starship-tty.toml` |
| fastfetch | system info + logo | generated: `fastfetch/config.jsonc` |
| btop | monitor | `btop/btop.conf` (yours), theme `btop/themes/nullgrid.theme` (generated) |
| yazi | file manager | generated: `yazi/theme.toml` (+ `yazi-tty/` without icons, used on the console) |
| neovim | editor | `nvim/init.lua` (yours), colorscheme `nullgrid` reads the generated `lua/nullgrid/palette.lua` and restyles when it changes |
| lazygit | git | generated: `lazygit/config.yml` |
| cava | audio visualizer | generated: `cava/config` (+ `config-tty`) |
| tmux | multiplexer | `tmux/tmux.conf` (yours) sources `nullgrid-theme.conf` (generated). Prefix `C-b`; `\|` and `-` split, `r` reloads |

All of them follow `nullgrid theme set`. kitty, tmux, cava, neovim and the dashboard restyle while
running. The others pick up the new theme the next time they start.

## TTY mode

Run `nullgrid mode tty` (or set `[behavior] default_mode = "tty"`). After that, logging in on tty1
starts the **dashboard** (`nullgrid-dash`) instead of the desktop ([DESKTOP.md](DESKTOP.md)).
If the desktop can't start (no usable GPU), desktop mode falls back to the dashboard too.

On the Linux console:
- the font is Terminus (`/etc/vconsole.conf`);
- the 16 console colors are set from the theme at login (`generated/tty-palette.sh`);
- the prompt, yazi and cava switch to console-safe variants.

### Dashboard

The panels: CPU (total, load, per core, history), MEMORY (RAM, swap, disk, history),
NETWORK (down/up graph), SYSTEM (node, kernel, uptime, power, theme), LAUNCH.

| Key | Action |
|---|---|
| `1`..`8` | launch btop, yazi, nvim, lazygit, cava, tmux (session `main`), nmtui, fastfetch (only installed ones are listed). Quitting the app returns to the dashboard |
| `t` | switch to the next theme (restyles the console live) |
| `p` | power menu: `o` power off, `r` reboot, `esc` cancel |
| `q` / `s` / `esc` | leave the dashboard and drop to the shell |

The dashboard refreshes every second, or every 3 s with `[performance] profile = "lite"`.
`nullgrid-dash --check` prints one sample without starting the UI.

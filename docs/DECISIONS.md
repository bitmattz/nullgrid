# Design decisions

Small choices are recorded here as they're made. Big ones were agreed up front (2026-10-12).

## Agreed with the project owner

| Topic | Decision |
|---|---|
| Name | NULLGRID |
| Logo | B, "Dead pixel lattice" (`docs/LOGO.md`): 4x4 cyan lattice with one glowing red missing cell; simplified variant for 16 px |
| Base | Arch Linux, ISO built with archiso |
| Compositor | Hyprland, with a Sway fallback config for GPUs where Hyprland misbehaves |
| Desktop shell | Quickshell (QML): custom shapes (chamfers, gauges, graphs), built-in Hyprland/PipeWire/UPower/tray/notification support, hot reload |
| Target hardware | x86_64 VMs and laptops (incl. old ThinkPads, NVIDIA hybrid), **plus** Raspberry Pi and DIY cyberdecks (aarch64), see below |
| Distribution | Only NULLGRID itself; no separate theme/dotfiles package for other Arch systems |
| Build host | Any Linux with Docker; mkarchiso runs in an Arch container |
| TTY dashboard | Python + Textual |
| Live ISO login | Auto-login (no greeter on the live ISO; tuigreet on installed systems) |
| Repo | https://github.com/bitmattz/nullgrid |

## Phase 1

- **Own packages via a local pacman repo.** Everything NULLGRID-specific ships as PKGBUILDs in
  `pkg/`, built into `out/repo` and installed by name from `iso/packages.x86_64`. The installer
  (phase 8) installs the exact same packages, so live and installed systems can't drift apart.
- **NetworkManager instead of releng's systemd-networkd + iwd.** It has `nmtui` for users and a
  D-Bus API that the status bar and Quickshell can read for wifi state.
- **zstd instead of xz** for the squashfs and the initramfs. The ISO is slightly bigger but
  decompresses much faster, which helps boot time on old/slow machines and SD cards.
- **Live user `nullgrid` (uid 1000) created with sysusers.d**, not by shipping a full
  `/etc/group`. That avoids fighting pacman over files `filesystem` owns. The password is locked,
  tty1 auto-logs in, and sudo is passwordless (live ISO only).
- **Serial console enabled** (`console=ttyS0`, autologin on ttyS0). This makes `make test-boot`
  possible without a display and is harmless on real hardware.
- **Removed from releng:** speech/accessibility boot entries, memtest/HDT, cloud-init, hypervisor
  guest daemons, ssh, ModemManager, and the PXE initramfs hooks (which need nbd/nfs tools).
  They can be re-added if needed. The accessibility entry
  should probably come back once the desktop exists.
- **`/etc/os-release` belongs to `nullgrid-base`.** `/usr/lib/os-release` stays Arch's (owned by
  `filesystem`); `/etc/os-release` takes precedence and is otherwise unowned on Arch.
- **Makefile rather than justfile.** `make` is preinstalled everywhere and `just` isn't.

## Phase 2

- **Validation is a ~150-line schema module, not pydantic.** pydantic-core is a compiled
  dependency that matters on a Pi; the schema here does what's needed (types, ranges, enums,
  defaults, dotted error paths, "did you mean" for typos) with Jinja + tomlkit as the only deps.
- **Unknown config keys are errors.** A misspelled key that silently does nothing is worse than
  a refusal; the error names the key and suggests the right one.
- **Presets + overrides.** `[theme] preset` picks a theme file; `[theme.colors|fonts|style]` in
  the user config override single values on top of it. `theme set` keeps overrides (it warns
  and offers `--reset-colors`) rather than deleting what the user wrote.
- **Fragments over whole files.** Where an app can include a file (kitty, Hyprland, hyprlock,
  GTK, nvim), nullgrid generates only the theme fragment and the app's main config includes it.
  Whole files are generated only where the app has no include (mako, fuzzel, btop theme, qt6ct).
- **Generated files are tracked by hash** in `~/.local/state/nullgrid/generated.json`. Unchanged
  output isn't rewritten (no needless reloads); a file edited by hand or not written by nullgrid
  is copied to `.bak` before it's replaced.
- **All-or-nothing rendering.** Every template renders into memory before anything is written,
  and the config is validated before the CLI saves it, so a mistake can't leave half the apps
  restyled.
- **Reload hooks are declarative** (`process`/`signal`/`reload`/`env` in the manifest) and only
  fire for running apps whose file changed. kitty gets SIGUSR1 sent directly (no `pkill`).
  Apps that can't hot-reload (btop, fuzzel, qt6ct apps, nvim) pick changes up on next start.
- **Hyprland can't cut window corners**, so `corners = "chamfer"` gives square windows; the
  chamfers are drawn on panels and frames (Quickshell). `round` maps to `rounding = 10`.
- **`[performance] profile = "lite"`** turns off blur, shadows and animations in every generated
  file and tells the shell to refresh widgets every 3 s instead of 1 s. `reduce_motion` only
  turns off motion. Choosing Sway for `lite` is left for phase 4.
- **All three presets use the same fonts for now** (Rajdhani / JetBrains Mono / Orbitron). Per-theme
  fonts are a one-line change once the fonts are packaged (phases 3 and 7).
- **The `nullgrid sound` subcommands are left for phase 6**, together with the daemon; the
  `[sound]` schema exists now so the config file format doesn't change later.
- **`nullgrid mode` only records the choice for now.** Phase 3 makes login honor it.
- **Tests:** `make test` runs pytest in the builder container; `makepkg` runs the same suite in
  `check()`, so a broken `nullgrid-core` can't reach the ISO. Snapshot files under
  `tests/nullgrid/snapshots/` hold every template rendered for every preset; refresh them after an
  intended change with `make test NULLGRID_UPDATE_SNAPSHOTS=1` and review the diff.
- **Repo code reaches PKGBUILDs as a tarball.** `build-packages.sh` puts `nullgrid-src.tar`
  (tools, themes, config, tests) next to each PKGBUILD, which lists it in `source=()`.

## Phase 3

- **Palette slots, not hex, for anything that can run on the console.** The Linux console has
  16 colors and ignores 24-bit color. Each preset's terminal palette already contains its accent
  colors. So the engine maps each role to its nearest palette slot (`ansi_roles`, by CIELAB
  distance: plain RGB distance mapped gray `dim` to green). tmux, yazi, lazygit, fastfetch, the
  zsh highlighting, the console prompt and the dashboard all use slots. The same file then looks
  right in kitty and on a TTY, and it follows the theme.
- **Console variants where glyphs differ.** Terminus has no powerline or Nerd glyphs, no half
  blocks and no double lines. Starship, yazi and cava get a `-tty` variant from the same template
  (`vars = { tty = true }` in the manifest), and zsh picks it when `TERM=linux`. The Phase 1 motd
  wordmark used half blocks and rendered as junk on the console. It's replaced by a generated,
  themed login banner drawn with box-drawing characters.
- **Dotfiles: system file + skel + `nullgrid init`.** `~/.zshrc` is two lines that source
  `/usr/share/nullgrid/zsh/nullgrid.zsh`, so fixes ship with updates. The editable defaults (kitty,
  tmux, btop, nvim) are copied once by `nullgrid init`, which runs at first login and never
  overwrites existing files. Generated theme fragments are separate files that those configs include.
- **Settings reach the shell as env vars** (`generated/shell-env.sh`), so login doesn't start
  Python just to read the mode or theme roles.
- **tmux, not zellij.** Lighter (1.5 MB vs 52 MB), and its status bar is easy to theme with slots.
- **Hand-written neovim colorscheme, no plugin manager.** It reads the generated palette, sets
  gui and cterm colors (the console uses `notermguicolors`), and re-applies itself when the palette
  file changes (it watches the directory, because the file is replaced atomically).
- **Dashboard: Textual with an ANSI theme.** The panels draw their own text graphics: segmented
  `■·` bars, and column graphs with `░▒█` on the console or eighth blocks in kitty. Textual's
  stock widgets use glyphs the console lacks. It watches `theme.json`, and on a theme change it
  also sets the console palette itself. Apps launch with `App.suspend()`.
- **Fonts:** Rajdhani and Orbitron come from google/fonts at a pinned commit with checksums
  (`pkg/nullgrid-fonts`). JetBrains Mono and Terminus come from Arch. kitty's built-in Nerd symbols
  cover the prompt glyphs, so no Nerd Font package is needed.
- **Packages:** `nullgrid-terminal` (zsh setup, skel, logo; it depends on all the terminal apps)
  and `nullgrid-dash`. `build-packages.sh` now builds in dependency order through a local
  `[nullgrid]` repo, so packages can depend on each other.
- **Boot test screenshots.** The headless VM now has a VGA screen. The test drives tty1 through
  the QEMU monitor (screenshots plus key presses) and saves PNGs to `out/screens/`.
- **Not verified yet:** cava. It crashes without an audio server, even with an empty config, and
  PipeWire arrives in phase 6. Also kitty's look, because it needs the Wayland session (phase 4).
  kitty's config does parse in the boot test.

## Phase 4

- **Hyprland's Lua config.** Arch ships Hyprland 0.56, which reads `hyprland.lua` (the old
  hyprlang format is legacy). The generated files are Lua: `nullgrid-theme.lua` (look) and
  `nullgrid-keys.lua` (binds). `~/.config/hypr/hyprland.lua` is the user's file. It `dofile`s the
  package defaults (`/usr/share/nullgrid/hypr/nullgrid.lua`, so fixes ship with updates) and the
  two generated files, then holds the user's own settings. `dofile` rather than `require`, so a
  reload always re-reads them. The theme file returns the palette for the user's own rules.
- **Configs are checked by the compositors themselves.** `Hyprland --verify-config` rejects
  unknown options, rule fields and dispatcher arguments. The boot test runs it on the live
  system. Sway's `-C` needs a backend even to validate, which is fine on the ISO. The unit tests
  compile the generated Lua with `luac -p` (`lua` is now in the builder image).
- **The glow is Hyprland's `decoration.glow`** (new in 0.5x): a neon halo in `colors.glow`, sized by
  `style.glow`. The drop shadow is off. The active border is a glow-to-secondary gradient at 45°.
- **One keybind file for both compositors.** A keybind set (`keybinds/<name>.toml`, chosen with
  `behavior.keybinds`) maps actions to combos. Templates turn it into Hyprland Lua and Sway
  syntax, and the same data feeds `nullgrid keys` and the keymap on the wallpaper, so none of
  them can drift. Duplicate combos are errors. User sets live in `~/.config/nullgrid/keybinds/`,
  the same way themes do. `behavior.keybinds` is a set name, not a path.
- **Session start: tty1 login → `nullgrid-session`.** No display manager on the live ISO
  (auto-login was agreed). The script picks Hyprland, or Sway for the `lite` profile. A compositor
  that quits within 10 s counts as a failed start, whatever its exit status: in VirtualBox
  Hyprland gives up at startup and still exits 0. The next one is tried, ending with Sway on
  pure software rendering (pixman), which needs no working GPU driver. Exit status 1 (nothing
  started) makes the login fall back to the TTY dashboard. Each start is logged to
  `~/.local/state/nullgrid/session-status`, and `nullgrid doctor` reports failures. Hyprland goes through `start-hyprland` (its watchdog
  wrapper, recommended since 0.53). On NVIDIA's proprietary driver Sway gets `--unsupported-gpu`.
  Leaving the desktop drops back to the tty1 shell rather than logging out.
- **Wallpaper: procedural SVG, rendered per screen size.** `nullgrid/wallpaper.py` draws every
  decor layer from the theme colors and `[decor]`, with a seeded RNG so the same input gives the
  same picture. `rsvg-convert` turns it into a PNG for each screen's exact resolution, cached by
  content hash, and `swaybg` shows it. swaybg works on both compositors (hyprpaper is
  Hyprland-only, and it can't do SVG). Its input is `generated/wallpaper.json`, a normal
  template target, so `theme set` re-renders it through the usual reload hooks. The new swaybg
  starts before the old one is stopped, so there's no flash. The animated layer (falling matrix
  columns) is left to the Quickshell overlay in phase 5, where `reduce_motion` can turn it off.
- **Decor keeps clear of the phase 5 widgets.** The logo plate is top right, the data blocks top
  left and bottom left (right of the dock), and the keymap is under the logo plate. The matrix
  columns skip the text blocks so those stay readable.
- **The keymap on the wallpaper is real data.** It lists the essential binds of the active set.
  A new user sees where to start without a cheat sheet, and decoration earns its place.
- **The login terminal floats.** It's `kitty --class nullgrid-welcome`, at 52% x 60%, left of
  center. A tiled terminal would cover the whole HUD on first login. `SUPER+V` tiles it.
- **Logo from one geometry.** `nullgrid/logo.py` holds the lattice (4x4, hole at 2.2) and draws it
  as ASCII (the fastfetch logo, byte-identical to phase 3; a test guards it), as SVG, and as
  a group inside the wallpaper. The SVG is also the `nullgrid` icon that os-release's `LOGO=` names.
- **Package `nullgrid-desktop`**: the session scripts, compositor defaults, logo files and a
  `wayland-sessions` entry (for the phase 7 greeter). It depends on hyprland, sway, swaybg,
  librsvg, fuzzel, mako, hyprlock, grim, slurp, wl-clipboard and libnotify. All packages are 0.4.0.
- **Measured in the boot test VM** (4 GB, virtio-gpu without 3D, so llvmpipe): about 700-750 MB
  used at idle on Hyprland and 550-620 MB on Sway, and 0% CPU at idle. Software GL inflates
  Hyprland (237 MB RSS) and kitty (178 MB). Xwayland starts eagerly (61 MB). Phase 9 measures on
  real GPUs against the 700 MB target, and can make Xwayland lazy.
- **Gotcha: zsh `print -P` runs command substitutions** once starship has turned on
  `prompt_subst`. A backticked command name in a message started the desktop a second time.
  Messages printed with `print -P` must not contain backticks or `$(...)`.

## Light hardware strategy (from the target-hardware answer)

- Every NULLGRID tool is Python/QML/shell (`arch=any`), so it is architecture-neutral by design.
- A `[performance]` profile in `nullgrid.toml` (phase 2) will offer `full | lite`. `lite` turns off
  blur, shadows and animations, slows widget refresh, and can pick Sway over Hyprland.
- **Raspberry Pi (aarch64):** archiso's `bios`/`uefi` boot modes don't fit the Pi's firmware boot.
  The plan is a separate SD-card image builder (`image/rpi/`, after phase 9) that starts from the
  Arch Linux ARM rootfs and installs the same `pkg/` packages, cross-built in Docker with
  qemu-user/binfmt. Hyprland runs on Pi 4/5 (V3D GPU, Mesa). Pi 3 and older would get the `lite`
  profile on Sway, or TTY mode.
- **`systemd-loop@.service` is masked on the live ISO.** systemd 262 loop-attaches an optical
  boot disk whose GPT the kernel can't parse. archiso's hybrid ISO triggers this, the attach fails
  ("No suitable partitions found"), and the system shows as degraded. The live root is mounted by
  the archiso hook, so this feature has nothing to do.

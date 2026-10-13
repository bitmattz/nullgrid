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
- **The login terminal floats.** It's `kitty --class nullgrid-welcome`, at 44% x 58%, left of
  center (phase 5 made it smaller, clear of the HUD widgets). A tiled terminal would cover the whole HUD on first login. `SUPER+V` tiles it.
- **Logo from one geometry.** `nullgrid/logo.py` holds the lattice (4x4, hole at 2.2) and draws it
  as ASCII (the fastfetch logo, byte-identical to phase 3; a test guards it), as SVG, and as
  a group inside the wallpaper. The SVG is also the `nullgrid` icon that os-release's `LOGO=` names.
- **Package `nullgrid-desktop`**: the session scripts, compositor defaults, logo files and a
  `wayland-sessions` entry (for the phase 7 greeter). It depends on hyprland, sway, swaybg,
  librsvg, fuzzel, mako (removed in phase 5), hyprlock, grim, slurp, wl-clipboard and libnotify. All packages are 0.4.0.
- **Measured in the boot test VM** (4 GB, virtio-gpu without 3D, so llvmpipe): about 700-750 MB
  used at idle on Hyprland and 550-620 MB on Sway, and 0% CPU at idle. Software GL inflates
  Hyprland (237 MB RSS) and kitty (178 MB). Xwayland starts eagerly (61 MB). Phase 9 measures on
  real GPUs against the 700 MB target, and can make Xwayland lazy.
- **Gotcha: zsh `print -P` runs command substitutions** once starship has turned on
  `prompt_subst`. A backticked command name in a message started the desktop a second time.
  Messages printed with `print -P` must not contain backticks or `$(...)`.

## Phase 5

- **Quickshell from Arch's repos** (0.3.2), installed as the config `/etc/xdg/quickshell/nullgrid/`
  so `qs -c nullgrid` runs it and a user copy in `~/.config/quickshell/nullgrid/` takes over
  without touching system files. `nullgrid-shell` starts it (`--no-duplicate --daemonize`) and
  wraps its IPC (`menu`, `status`, `restart`, `log`).
- **One QML tree for Hyprland and Sway.** `Wm.qml` hides the difference: workspaces come from
  Quickshell's Hyprland or I3 module, and switching uses Hyprland's Lua dispatch
  (`Hyprland.usingLua`) or `workspace number N` on Sway.
- **Readings straight from /proc and /sys** (`Sys.qml`), no helper process per tick: CPU (per
  core), memory, swap, network, load, uptime, plus sensor files found once at startup (hwmon
  CPU/GPU temperature, amdgpu busy %, battery). The interval is `refresh_ms` (1 s, 3 s on lite).
  Values a machine doesn't have are hidden, not shown as zero.
- **The shell is the notification daemon** (Quickshell's NotificationServer) and **mako is gone**:
  mako can't draw chamfered cards, and the shell will also be where phase 6 hooks the
  notification sounds. Its template and package were removed.
- **Icons are SVG path strings** (`shell/Icons.js`, original line drawings on a 24 px grid),
  drawn with QtQuick Shapes in the theme colors. No icon theme or Nerd font is needed in QML.
  The start menu shows real app icons from the icon theme for desktop entries.
- **Panels are `Chamfer.qml`**: a Shape path with 45° cuts that follows `style.corners`
  (sharp/chamfer/round). The active state is diagonal hatching (`Hatch.qml`), as in STYLE.md.
- **Layers:** bar, dock (exclusive zones) on Top; HUD widgets and the matrix rain on Bottom,
  under the windows and above the wallpaper; start menu, notifications on Overlay. Hyprland
  blurs behind the bar, dock, menu and notifications.
- **Matrix rain moves in steps** (8 per second, every column in the same frame) instead of smooth
  animation, a few columns kept away from the HUD cluster. It's off with `reduce_motion`, with
  the lite profile, with `decor.matrix_rain = false`, and **without a GPU with 3D**: under
  software rendering every step makes the compositor redraw the screen on the CPU, which took
  Hyprland to 150-170% CPU in the boot-test VM (8% with it off). Per-column surfaces didn't
  help (each commit still costs a full frame) and doubled the shell's memory.
- **Software rendering is detected** by `nullgrid-session` from the DRM driver: framebuffer
  drivers (simpledrm, bochs, qxl...) and QEMU's virtio-gpu without the VIRGL feature bit
  (`/sys/.../virtioN/features`, bit 0) count as "no GPU". It exports
  `NULLGRID_SOFTWARE_RENDER=1`; the shell then also uses Qt's software renderer
  (`QT_QUICK_BACKEND=software`): 106 MB instead of 490 MB RSS and less CPU per redraw. Measured
  in the VM with Hyprland: 848 MB used and ~5% CPU at idle, vs 1150 MB / 95% before.
- **Start menu** = a full-screen Overlay surface: a click outside closes it, and it has the
  keyboard (type to search). Destructive power buttons need a second click within 3 s.
  `SUPER+SPACE` opens it (new `start_menu` action in the keybind set); fuzzel stays on `SUPER+D`
  as the keyboard launcher.
- **Lock screen: hyprlock** with a HUD layout (`~/.config/hypr/hyprlock.conf`, skel) over the
  current wallpaper: `nullgrid wallpaper apply` keeps `~/.cache/nullgrid/wallpaper/current.png`
  pointing at it.
- **Live ISO: the password is `nullgrid`** (`nullgrid-live-password.service` sets it at boot).
  Before, the password was locked, so the lock screen could never be unlocked. An empty password
  doesn't work either: PAM then succeeds without asking, and hyprlock never unlocks ("not waiting
  for input"). The lock screen shows the password on the live ISO only, from
  `/etc/nullgrid/lock-hint`. Login is still by autologin, and sudo needs no password.
- **`make test-shell`** runs the shell under a headless Sway in the builder container (Quickshell,
  Sway, grim and hyprlock are now in the image). It fails on QML errors and warnings, checks the
  IPC, the start menu and a live theme switch, and saves screenshots. That's seconds instead of a
  VM boot. The boot test then checks the real session, including unlocking with Enter.
- **swaybg liveness ignores zombies.** A swaybg that died but wasn't reaped still has the name
  `swaybg` in /proc, which made `wallpaper apply` think it was running.
- All NULLGRID packages except fonts and base are 0.5.0.

## Phase 6

- **Sounds are synthesized at package build time**, not stored in git. `assets/sounds/generate.py`
  (numpy) builds both packs in about 7 s, deterministically (a seed per sound), and the
  `nullgrid-sfx` PKGBUILD runs it; numpy is a build dependency only. The repo stays free of
  binary audio, and a recipe change can be reviewed as code.
- **WAV, 48 kHz mono, 16-bit.** 48 kHz is PipeWire's default rate (no resampling), mono is
  enough for UI sounds, and WAV needs no decoder. Both packs together are 1.2 MB.
- **Loudness-matched, not peak-normalized.** Peak normalization left the crushed buzzes far louder
  than the sine blips at the same peak. Each sound is scaled so its loudest 50 ms has the target
  RMS (ticks -8 dB, alerts +3 dB relative to the pack level), with a -1 dBFS peak ceiling.
  minimal-ops sits 5 dB below neural-link.
- **The daemon is Python** (like the rest of the tooling): one `select()` loop over its socket,
  the compositor's event stream, `udevadm monitor` and signals, with a battery poll every 60 s.
  No CPU while idle (0 ticks over a minute in the VM; 21 MB RSS); it starts `pw-play` per sound
  and never waits for it. A long-lived PipeWire stream would save `pw-play`'s startup (some tens
  of ms), but needs native bindings; that delay isn't noticeable for UI sounds. PipeWire and
  WirePlumber add about 30 MB; pipewire-pulse only starts when a PulseAudio client connects.
- **Who reports what:** the compositor gives workspace/window events (Hyprland socket2, `swaymsg
  -t subscribe`); the shell reports its own UI (menu, clicks, notifications) over the daemon's
  socket with Quickshell's `Socket`, so nothing is spawned per click; the hardware keys go
  through `nullgrid-media`; lock and power actions through `nullgrid-lock` and `nullgrid-power`,
  which wait for the sound before logging out or shutting down. Lock/unlock can't come from
  Hyprland: it has no lock event in its socket.
- **Power events from udev + /sys, not UPower.** `udevadm monitor` reports USB devices and power
  supply changes; the daemon then reads `/sys/class/power_supply`. UPower would be one more
  service on the ISO for the same information.
- **zsh writes to the socket directly** (`zsh/net/socket`), so the command-done/failed hooks cost
  no process per prompt, and only run when those events are switched on (`NULLGRID_SFX_SHELL`
  in the generated shell-env). `command_done` only sounds for commands of 10 s or longer.
- **The daemon's settings are a generated file** (`generated/sfx.json`, a manifest target with
  `process = "nullgrid-sfx"`, `signal = "HUP"`), like the shell's theme.json: the same render
  and reload path as every other app, no TOML parsing in the daemon.
- **Reload signals only go to processes that handle them** (`SigCgt` in `/proc/PID/status`).
  The boot test caught `nullgrid theme set` killing a kitty that was still starting: SIGUSR1's
  default action is to terminate, and kitty installs its handler a moment after it starts.
- **The daemon belongs to the session:** it exits when the compositor's event stream closes, and
  a new daemon asks an old one to quit before taking the socket. `boot` plays for the first
  session after the machine started (boot id kept in `~/.local/state/nullgrid/sfx-boot-id`),
  `login` for later ones.
- **Media keys are new keybind actions** (`volume_up` ... `brightness_down`) on the XF86 keys,
  bound with `locked` (they work on the lock screen; volume and brightness also repeat), and
  `lock` / `exit` now run `nullgrid-lock` / `nullgrid-power logout`.
- **PipeWire on the ISO:** pipewire, wireplumber, pipewire-pulse (browsers, cava), pipewire-alsa,
  pipewire-jack (cava depends on JACK; this avoids a jack2 server) and sof-firmware (sound on many
  recent laptops). The user units are enabled globally by the packages' install hooks. cava,
  which crashed without an audio server in phase 3, now runs.
- **The boot test listens:** QEMU records the VM's HDA output to a WAV file, and the test checks
  that `nullgrid sound test` makes it non-silent. `make run` sends the VM's sound to the host.
- All NULLGRID packages except fonts and base are 0.6.0; new package `nullgrid-sfx`.

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

# Project Brief: NULLGRID OS — a terminal-first, cyberpunk-styled Linux distro

> Working codename: **NULLGRID** (rename freely; replace every occurrence).
> Save this file as `CLAUDE.md` (or reference it) in an empty project folder, then start Claude Code there.

---

## 0. How I want you to work

- **Start in plan mode.** Before writing any code, read this whole brief, then give me a phased implementation plan, the repo layout, and a list of open questions. Wait for my approval before building.
- Work **phase by phase** (see section 9). At the end of each phase: summarize what changed, how to test it, and what's next. Commit after each working milestone with clear commit messages.
- Prefer **simple, well-maintained, scriptable tools** over clever custom code. Only write custom components when nothing existing fits.
- Everything must be **reproducible from the repo**: one command builds the ISO, one command boots it in a VM.
- When you're unsure about a design choice that's expensive to undo, **ask me**. For small choices, pick a sensible default and note it in `docs/DECISIONS.md`.
- Never use copyrighted assets (fonts without open licenses, game logos, brand names such as Cyberpunk 2077 / Arasaka / Night City, or files from existing themes like "Daemon"). All art, icons, sounds and wallpapers must be **original, generated, or properly open-licensed**, with licenses recorded in `assets/LICENSES.md`.

---

## 1. Vision

A lightweight Linux OS whose **core experience is the terminal**, wrapped in a **cyberpunk / sci-fi HUD aesthetic**: dark crimson backgrounds, neon cyan accents, angular frames with cut corners, glowing borders, thin technical typography, decorative "data" text, barcode/scanline motifs, and live system-monitor widgets. It should feel like operating a hacker's cyberdeck.

Key pillars:
1. **Terminal-first** — the terminal is the main app; GUI elements exist to frame and support it.
2. **Distinctive visuals** — HUD-style desktop, not a generic tiling setup.
3. **Sound design** — subtle, techy UI sound effects for system events.
4. **Fully customizable** — one central config controls colors, fonts, sounds, widgets, and layout; theme presets can be swapped live.
5. **Light** — boots fast, idles at low RAM (target: < 700 MB at desktop idle), runs well on modest hardware and in a VM.

---

## 2. Base system

- **Base:** Arch Linux, built with `archiso` (custom profile in `iso/`). Explain the trade-off if you think another base (e.g. Debian live-build, NixOS) is clearly better, but default to Arch.
- **Init:** systemd.
- **Display:** Wayland only.
- **Compositor:** Hyprland (for blur, animations, rounded/borders, layer rules). Provide a fallback config for Sway if Hyprland fails on a GPU.
- **Audio:** PipeWire + WirePlumber.
- **Login:** `greetd` with a themed TUI greeter (`tuigreet`) matching the aesthetic, OR auto-login on the live ISO.
- **Installer:** a themed TUI installer script (`nullgrid-install`) wrapping `archinstall` or a custom `gum`/`whiptail`-based flow: disk, user, locale, keyboard, timezone, GPU drivers (Intel/AMD/NVIDIA).
- **Package set:** keep it minimal; list every package in `iso/packages.x86_64` with a comment on why it's there.

---

## 3. Two modes of use

### 3a. Desktop mode (default)
Hyprland session with the HUD shell (section 4).

### 3b. Pure terminal mode
Selectable at the greeter or via `nullgrid-mode tty`. Boots into a TTY with:
- A themed console font and palette (setfont / kernel console colors matching the theme).
- A **TUI dashboard** on login (e.g. a custom script using `btop`-style panels, or a small Rust/Go/Python TUI with Ratatui/Bubble Tea/Textual) showing: CPU, RAM, network, disk, battery, time, and a launcher for common TUI apps.
- `tmux` or `zellij` preconfigured with the theme and a HUD-like status bar.

---

## 4. Desktop shell / UI components

Build the shell with **Quickshell** (QML) or **AGS/Astal** or **eww** — recommend one and justify it. All widgets read colors/fonts from the central theme (section 6).

Required components (inspired by the reference screenshots I have):

1. **Left vertical dock** — a column of circular icon buttons with neon outlines; a highlighted/active state; a workspace indicator (dots) and a numbered workspace badge at the bottom.
2. **Bottom status bar** — full width, thin, with: mode/profile label, quick toggles (Wi-Fi, Bluetooth, brightness, volume), app tray, CPU %, RAM %, GPU %, network up/down, CPU/GPU temps, power draw, media "now playing", clock with full date (`YYYY-MM-DD HH:MM`).
3. **Desktop HUD widgets** (bottom-right cluster, toggleable):
   - Large circular RAM usage gauge with percentage in the center.
   - Network download/upload line graph with labeled scale.
   - CPU per-core bar graph with total usage, load average, CPU and core counts.
   - Workspace overview strip (numbered panels, active one hatched/highlighted).
   - A small dot-matrix "activity" grid.
4. **Decorative layer** — angular circuit-trace lines along the screen edges, a top-right logo plate with the OS name in a techy display font, faint matrix-style dot/character columns, small "classified data" text blocks, a barcode/ID strip in the top-left, a warning triangle glyph. These should be part of the **wallpaper + overlay**, rendered at any resolution (prefer SVG or procedurally generated).
5. **App launcher / start menu** — opened from the dock's top button: search field at top, category list on the left (Development, Graphics, Internet, Multimedia, Settings, System, Utilities…), favorites grid on the right, power buttons (Sleep, Restart, Shut Down) at the bottom. Also provide a keyboard launcher (fuzzel/rofi-wayland/anyrun themed identically).
6. **Notifications** — themed daemon (mako or swaync) with angular frames.
7. **Lock screen** — hyprlock themed as a "system locked / authentication required" HUD.
8. **Window decorations** — sharp corners or chamfered look, 2px neon border on the active window (glowing red/pink), dim border on inactive, subtle blur and drop glow.
9. **Boot splash** — Plymouth theme with an animated "system boot" sequence (scanline + logo + fake boot log).

---

## 5. Apps & theming coverage

Theme everything consistently from the central palette:
- **Terminal (primary):** kitty or foot — pick one, justify. Custom 16-color palette, transparency, prompt with powerline-style segments (starship), a fastfetch config with a custom ASCII logo for the OS.
- **Shell:** zsh with plugins (autosuggestions, syntax highlighting) — or fish; your call.
- **TUI apps preinstalled & themed:** btop, yazi (file manager), neovim (with a matching colorscheme), lazygit, cava (audio visualizer), fastfetch.
- **GUI essentials (minimal):** a browser (Firefox with a userChrome theme or just a matching theme), a GUI file manager (Thunar or Nautilus), image viewer, PDF viewer.
- **Toolkits:** GTK3/GTK4 theme + Qt (Kvantum/qt6ct) theme so any GUI app inherits the look. Icon theme: original line-style neon icons (circular outline style), with fallback to an open-licensed icon set recolored.
- **Cursor:** themed cursor set.

---

## 6. Customization system (very important)

- A single config file: `~/.config/nullgrid/nullgrid.toml`, containing:
  - `[theme]` — palette (background, surface, primary accent, secondary accent, warning, text, dim), fonts (UI, mono, display), border width, glow intensity, corner style (`sharp | chamfer | round`), transparency, blur.
  - `[sound]` — enabled, master volume, per-event toggles, sound pack name.
  - `[widgets]` — which HUD widgets are visible and their positions.
  - `[decor]` — circuit lines, matrix rain, data text, scanlines on/off.
  - `[behavior]` — animations speed, default mode (desktop/tty), keybinds file.
- A CLI tool **`nullgrid`** with subcommands:
  - `nullgrid theme list | set <name> | edit | reload`
  - `nullgrid sound list | set <pack> | test <event> | mute`
  - `nullgrid widget toggle <name>`
  - `nullgrid mode desktop|tty`
  - `nullgrid doctor` (checks the system and config for problems)
- A **template engine** (e.g. a small Python/Rust script, or `matugen`/`wallust`-style templating) that takes the TOML and regenerates configs for Hyprland, the shell widgets, terminal, starship, btop, nvim, GTK, Qt, notifications, lock screen, TTY palette — then hot-reloads them. No hand-editing the same color in 12 places.
- Ship at least **3 theme presets**:
  1. `crimson-hud` — dark crimson/maroon background, neon cyan accents, red-pink window glow (the default, matching my references).
  2. `ice-protocol` — near-black + cold blue/white.
  3. `toxic-grid` — black + acid green/yellow.
- Optional: a TUI theme editor (`nullgrid theme edit`) with live preview.

---

## 7. Sound design

- A lightweight **sound daemon** (`nullgrid-sfx`) that plays short effects on events, using `pw-play` or a small binary with low latency. It must be cheap on CPU and never block the UI.
- Events to hook:
  - Boot complete / login / logout / shutdown
  - Workspace switch, window open, window close, window focus (optional, off by default)
  - Launcher open/close, menu hover (optional), button click
  - Notification received (separate sound for critical)
  - Volume / brightness change (short tick)
  - USB device connected/disconnected, battery low, charger plugged
  - Screenshot taken, error/denied action, lock/unlock
  - Terminal: optional bell replacement and command-finished/command-failed chime (via shell hook)
- Hook sources: Hyprland IPC socket events, udev, UPower (D-Bus), the notification daemon, shell `precmd` hooks.
- **Sound packs** in `/usr/share/nullgrid/sounds/<pack>/` with a `pack.toml` mapping events → files. Ship at least 2 packs:
  - `neural-link` — glitchy digital blips, data chirps, soft synth confirms.
  - `minimal-ops` — very subtle clicks and low beeps.
- Sounds must be **original** — generate them procedurally (e.g. a Python script using numpy + synthesis: sine/square blips, filtered noise bursts, bit-crush, short reverb) and keep the generator script in `assets/sounds/generate.py` so packs can be rebuilt or tweaked. Output .ogg or .wav, 50–600 ms, normalized.
- Global mute, quiet hours, and per-event volume in the config.

---

## 8. Visual style guide (put this in `docs/STYLE.md` too)

- **Colors (crimson-hud):** background `#1a0b0f`→`#2a0f15` gradient, surfaces `#24111a` at ~85% opacity, primary accent neon cyan `#5ef2f2`, secondary accent hot red `#ff3b4e`, border glow `#ff4d6d`, text `#e6f7f7`, dim text `#7a8a8f`, warning `#ffd166`.
- **Shapes:** chamfered (45° cut) corners on panels and frames, thin 1–2px lines, circular icon buttons, hatched/striped fills for active states, segmented bars.
- **Typography:** a condensed, technical UI font (open-licensed, e.g. Rajdhani, Oxanium, Chakra Petch, or Orbitron for display) and a clean mono font (JetBrains Mono / Iosevka) for the terminal. Verify licenses (OFL) before bundling.
- **Motion:** quick (120–220 ms), slightly mechanical easing; glitch/flicker only for rare events (boot, lock); no motion sickness — respect a `reduce_motion` flag.
- **Density:** small labels in uppercase, decorative serial numbers / coordinates, but readable — decoration must never cover content.

---

## 9. Phases (build in this order)

1. **Scaffold** — repo structure, `Makefile`/`justfile`, archiso profile that builds and boots to a TTY in QEMU. `make iso` and `make run` (QEMU with virtio-gpu, UEFI via OVMF).
2. **Theme engine + `nullgrid` CLI** — TOML config, templates, generation, reload. Unit-test the generator.
3. **Terminal experience** — terminal, shell, prompt, fastfetch logo, TUI apps themed, TTY mode + TUI dashboard.
4. **Compositor + window styling** — Hyprland config, borders/glow, keybinds, wallpaper + decorative layer.
5. **Shell UI** — dock, status bar, HUD widgets, launcher/start menu, notifications, lock screen.
6. **Sound system** — sound generator, packs, `nullgrid-sfx` daemon, event hooks.
7. **GTK/Qt/icons/cursor/Plymouth/greeter** — full visual coverage.
8. **Installer** — themed TUI installer, GPU driver selection, post-install first-run wizard (choose theme, sound pack, mode).
9. **Polish & performance** — measure idle RAM/CPU, boot time; fix; write docs.

---

## 10. Repo layout (suggested — adjust in your plan)

```
nullgrid/
├── CLAUDE.md              # this brief
├── justfile / Makefile
├── iso/                   # archiso profile (packages, airootfs, profiledef.sh)
├── config/                # default dotfiles & templates per app
│   └── templates/
├── shell/                 # Quickshell/AGS/eww widgets
├── tools/
│   ├── nullgrid/          # CLI + theme engine
│   ├── nullgrid-sfx/      # sound daemon
│   └── installer/
├── themes/                # crimson-hud, ice-protocol, toxic-grid (.toml)
├── assets/
│   ├── wallpapers/        # SVG / generators
│   ├── icons/
│   ├── sounds/            # generate.py + packs
│   ├── fonts/
│   └── LICENSES.md
├── plymouth/
├── tests/
└── docs/  (README, STYLE.md, DECISIONS.md, CUSTOMIZING.md, BUILDING.md)
```

---

## 11. Acceptance criteria

- `make iso` produces a bootable ISO on a clean Arch host (document dependencies); `make run` boots it in QEMU.
- Live session reaches the themed desktop with dock, status bar, HUD widgets, and working sound effects.
- `nullgrid theme set ice-protocol` restyles terminal, bar, widgets, borders, GTK/Qt apps, and lock screen **without logout**.
- TTY mode works with themed console and TUI dashboard.
- Idle RAM at desktop under ~700 MB in a 4 GB VM; no widget uses > 2% CPU at idle.
- All assets are original or open-licensed, documented in `assets/LICENSES.md`.
- The installer can install to a VM disk and the installed system boots into the same experience.

---

## 12. Things to ask me about before deciding

- Final OS name and logo concept.
- Hyprland vs. Sway, and Quickshell vs. AGS vs. eww (give me a recommendation).
- Target hardware (I'd like it to work on laptops with NVIDIA hybrid graphics too).
- Whether to also publish it as an installable dotfiles/theme package for existing Arch systems (not only an ISO).

---

## 13. Progress log (read this first when resuming)

### Status as of 2026-10-14: v1.1.0 in the update repository (v1.0.0 = latest ISO release); next: Raspberry Pi image builder

**Decisions already agreed with me (don't ask again):** name NULLGRID; Arch + archiso; Hyprland
(Sway fallback); Quickshell for the shell UI; kitty; zsh; Python (+ Jinja2) for the CLI, theme
engine and sfx daemon; Python/Textual for the TTY dashboard; auto-login on the live ISO; no
separate dotfiles/theme package for other Arch systems; build runs in Docker; repo is
github.com/bitmattz/nullgrid (push over SSH, remote `git@github.com:bitmattz/nullgrid.git`).
Targets include light hardware: old ThinkPads, DIY cyberdecks, and Raspberry Pi (aarch64, as a
separate SD-image builder after phase 9, see `docs/DECISIONS.md`). Full rationale is in `docs/DECISIONS.md`.

**Phase 1 delivered (commit `2a0ce67`):**
- `iso/`: archiso profile (from releng, trimmed): NetworkManager, zstd, live user `nullgrid`
  (sysusers.d, autologin on tty1 + ttyS0, passwordless sudo), local `[nullgrid]` repo at `out/repo`.
- `pkg/nullgrid-base`: os-release branding. All NULLGRID code ships as PKGBUILDs in `pkg/`.
- `build/`: Dockerfile (`nullgrid-builder`: archiso + QEMU + OVMF), `build-packages.sh`,
  `build-iso.sh` (fails on mkinitcpio `==> ERROR`), `run-vm.sh`.
- `tests/boot_smoke.py` + `make test-boot` / `test-boot-bios`: headless boot over serial. Both PASS
  (boots to shell in ~20 s with KVM).
- Docs: README, BUILDING, DECISIONS, STYLE, LOGO (3 concepts), `assets/LICENSES.md`.

**Gotchas learned:**
- `iso/packages.x86_64`: NO inline comments (mkarchiso keeps trailing spaces). Put the comment on the line above.
- systemd 262: `systemd-loop@.service` is masked in airootfs, otherwise the live system is "degraded".
- The host is Zorin OS (not Arch). It has Docker but no QEMU/OVMF yet (`make run` needs
  `sudo apt install qemu-system-x86 ovmf`). Disk is tight (~25 GB free).

**Logo chosen (2026-10-13):** concept B, "Dead pixel lattice" (`docs/LOGO.md`). Phase 4 draws
it as generated SVG plus a simplified small-size variant; the moving hole animates in Plymouth.

**Phase 2 delivered:**
- `tools/nullgrid/`: Python package (deps: jinja2, tomlkit). `schema.py` (own validator, dotted
  error paths, "did you mean"), `config.py` (schema for nullgrid.toml + presets, load/merge,
  comment-preserving edits), `render.py` (manifest, Jinja env, all-or-nothing render, hash-tracked
  writes with `.bak` on hand edits, reload hooks), `doctor.py`, `cli.py`.
- CLI: `theme list|set [--reset-colors]|edit|reload [--dry-run]`, `widget list|toggle`, `mode`, `doctor`.
- `themes/{crimson-hud,ice-protocol,toxic-grid}.toml`; default config `config/nullgrid.toml`.
- `config/templates/` + `manifest.toml`: kitty, hyprland, hyprlock, quickshell `theme.json`, mako,
  fuzzel, btop, nvim palette, gtk colors, qt6ct colors, tty palette script.
- `pkg/nullgrid-core` (runs pytest in `check()`), installed on the ISO. `make test` (51 tests incl.
  snapshots in `tests/nullgrid/snapshots/`). `make test-boot` checks `nullgrid` on the live ISO.
- Docs: `docs/CUSTOMIZING.md`; phase-2 section in `docs/DECISIONS.md`.

**Gotchas learned (phase 2):**
- Arch ships flit_core 4.x: don't pin `<4` in `pyproject.toml`.
- Snapshots: after an intended template change run `make test NULLGRID_UPDATE_SNAPSHOTS=1`, review the diff.
- Tests stub `render._processes` so they never signal the developer's real kitty/mako.

**Phase 3 delivered:**
- Packages: `nullgrid-fonts` (Rajdhani + Orbitron from google/fonts @ pinned commit, sha256),
  `nullgrid-dash` (`tools/nullgrid-dash/`, Textual), `nullgrid-terminal` (zsh setup
  `config/zsh/nullgrid.zsh`, `/etc/skel/.zshrc`, skel dotfiles `config/skel/`, ASCII logo
  `assets/logo/`). `build-packages.sh` builds in dependency order via a local `[nullgrid]` repo.
- Core: `nullgrid init [--reset]` (copies skel, never overwrites; zsh runs it at first login),
  manifest `vars` (one template -> desktop + `-tty` variants), `ansi()`/`ansi_roles`/`ansi_name()`/
  `sgr()` template helpers, `behavior.greeting`. New targets: shell-env, banner, starship(+tty),
  fastfetch, tmux, yazi(+tty), lazygit, cava(+tty). 22 targets total.
- TTY mode: tty1 login runs `nullgrid-dash` (desktop mode falls back to it until phase 4);
  Terminus console font (`iso/airootfs/etc/vconsole.conf`); console palette from the theme.
- Live ISO: `/etc/motd` replaced by `/etc/nullgrid/live-hints` + the generated banner.
- Tests: `make test` = 67 (incl. dashboard via Textual pilot). `make test-boot` checks every
  terminal app's config on the ISO and saves tty1 screenshots to `out/screens/` (QEMU monitor).
- Docs: `docs/TERMINAL.md`, phase-3 section in `docs/DECISIONS.md`, console glyph rule in STYLE.md.

**Gotchas learned (phase 3):**
- The Terminus console font lacks half blocks, eighth blocks, double lines, and powerline/Nerd glyphs.
  Console-safe set is in `docs/STYLE.md`; `test_tty_variants_use_only_console_glyphs` enforces it.
- Console = 16 colors: use palette slots (`ansi_roles`), never hex, in anything that may run on a TTY.
- Textual ANSI themes must define `$ansi-background` & co. (see `textual_theme()` in the dashboard).
- Two `conftest.py` files: don't `from conftest import`; shared helpers live in `tests/nullgrid/ngtest.py`.
- cava segfaults without an audio server (even with an empty config); verify it once PipeWire is in (phase 6).
- To see the console, read the PNGs `make test-boot` writes to `out/screens/`.

**Phase 4 delivered:**
- Hyprland 0.56 = **Lua config**. Skel `~/.config/hypr/hyprland.lua` dofile()s
  `/usr/share/nullgrid/hypr/nullgrid.lua` (defaults, rules, autostart) + generated
  `nullgrid-theme.lua` (look, returns palette) + `nullgrid-keys.lua`. Sway fallback: skel
  `~/.config/sway/config` includes `/usr/share/nullgrid/sway/nullgrid.conf` + generated `nullgrid-theme`/`nullgrid-keys`.
- Keybind sets: `config/keybinds/default.toml` (`keybinds.py`, `behavior.keybinds`), one file ->
  Hyprland + Sway binds + `nullgrid keys` + wallpaper keymap.
- `nullgrid-session` (tools/session/): Hyprland via `start-hyprland`, Sway for `lite`, falls back
  to the other on quick failure; exit 1 -> zsh starts the TTY dashboard. `nullgrid-screenshot`.
- Wallpaper: `nullgrid/wallpaper.py` (procedural SVG, all decor layers) + `nullgrid/logo.py`
  (lattice geometry -> ASCII/SVG; `assets/logo/generate.py`). Target `wallpaper` writes
  `generated/wallpaper.json`; `nullgrid wallpaper apply` renders PNG per screen (rsvg-convert,
  cached in ~/.cache/nullgrid) and runs swaybg. CLI also: `theme next|prev`, `keys [--pause]`, `wallpaper render`.
- Package `nullgrid-desktop`; all nullgrid packages 0.4.0. 26 manifest targets. `make test` = 115.
- `make test-boot`: virtio-gpu 1600x900 screen; checks Hyprland (verify-config, configerrors,
  wallpaper, live theme switch, keys popup, launcher, exit bind), Sway (lite), then TTY mode.
  Screenshots `out/screens/desktop-*.png`. Docs: `docs/DESKTOP.md`, phase-4 section in DECISIONS.

**Gotchas learned (phase 4):**
- `Hyprland --verify-config -c FILE` (as non-root) is a strict checker; use it. `sway -C` needs
  `WLR_BACKENDS=headless WLR_RENDERER=pixman` in a container, and a copy of the binary without
  file caps (`cp /usr/bin/sway /tmp/sway`); it doesn't validate bindsym commands.
- zsh `print -P` + starship's `prompt_subst` executes backticks/`$(...)` in messages.
- The builder needs `qemu-hw-display-virtio-vga`/`-virtio-gpu` for the boot test screen.
- virtio-gpu without virgl still has `/dev/dri/renderD128`; Mesa falls back to llvmpipe itself.
- `kitty --hold` drops into a shell (which runs the fastfetch greeting); use `nullgrid keys --pause`.
- VirtualBox: Hyprland needs "Enable 3D Acceleration" (VMSVGA). Without it Hyprland gives up at
  startup but exits 0, so nullgrid-session judges a start by time (<10 s = failed), not by status.
- While the user's VirtualBox VM runs, KVM VMs on this host fail ("KVM: entry failed, hardware
  error 0x0"); QEMU's `-vga vmware` crashes under KVM anyway. `run-vm.sh --vga=TYPE` tests adapters.
- Fast VM debugging: a scratch harness that boots the ISO with serial + monitor and takes
  commands from files (see phase-4 session) beats re-running the whole boot test.

**Phase 5 delivered:**
- `shell/` = Quickshell 0.3.2 config, installed to `/etc/xdg/quickshell/nullgrid/` (`qs -c nullgrid`;
  user copy in `~/.config/quickshell/nullgrid/` wins). Singletons: `Theme` (watches theme.json),
  `Sys` (/proc + /sys readings), `Wm` (Hyprland/Sway workspaces), `Ui` (menu state, pinned apps),
  `Backlight`, `Running`. Panels: `Bar`, `Dock`, `Hud` (one per [widgets] position) with
  `RamGauge/CpuBars/NetGraph/ActivityGrid/WorkspaceStrip`, `StartMenu`, `Notifications`
  (the notification daemon; mako removed), `MatrixRain`. Primitives `Chamfer`, `Hatch`,
  `NgIcon` (+ `Icons.js` SVG paths), `NgText`, `LatticeLogo`. IpcHandler target `shell`.
- `nullgrid-shell [menu|status|restart|log]`; autostarted by the Hyprland and Sway defaults.
  Keybind action `start_menu` (SUPER+SPACE). hyprlock HUD in skel `hypr/hyprlock.conf`;
  wallpaper keeps `~/.cache/nullgrid/wallpaper/current.png`. Live user password is `nullgrid`
  (`nullgrid-live-password.service`), shown on the lock screen via `/etc/nullgrid/lock-hint`.
- `make test-shell` (tests/shell_smoke.sh): headless Sway + shell in the builder; boot test checks
  the shell over IPC, menu, notifications, lock/unlock. All packages 0.5.0 (fonts/base unchanged).

**Gotchas learned (phase 5):**
- QML: a property named `on...` is a signal handler (`onBattery` broke loading); `top` is a FINAL
  Item property; in `ShapePath` children, `parent` is not the ShapePath (use ids/root props);
  no `;` after a grouped property block (`anchors { ... };`).
- Inside `HudPanel`, content is reparented: use ids, not `parent.parent`.
- `FileView` needs `blockLoading: true` to read /proc synchronously after `reload()`.
- A zombie swaybg still reads as `swaybg` in /proc/PID/comm: check the state in /proc/PID/stat.
- Hyprland Lua window rules: `size`/`move` take expressions (`"monitor_w*0.44 monitor_h*0.58"`);
  percentages pass `--verify-config` but are silently ignored. Check with `hyprctl clients`.
- hyprlock + an empty password never unlocks (PAM succeeds without asking). Never `kill -9`
  hyprlock in tests: Hyprland then shows its "lockscreen app died" screen.
- Under software rendering (VMs without 3D) every frame costs CPU: no continuous animations
  there (NULLGRID_SOFTWARE_RENDER), and Quickshell uses QT_QUICK_BACKEND=software (5x less RAM).
- Shell test loop: `tests/shell_smoke.sh` pattern (dbus-run-session, sway copy without caps,
  `WLR_BACKENDS=headless WLR_RENDERER=pixman`, grim) gives screenshots in seconds.

**Phase 6 delivered:**
- `assets/sounds/generate.py`: numpy synthesis (osc/FM/envelopes/FFT filters/bitcrush/Schroeder
  reverb), loudness-matched, deterministic -> packs `neural-link`, `minimal-ops` (27 events each,
  WAV 48k mono, `pack.toml`). Built in the `nullgrid-sfx` PKGBUILD (numpy = makedepend; also in
  the builder image); `make sounds` -> `out/sounds` (the system sound dir in a checkout).
- Core: `nullgrid/sound.py` (pack find/validate, `volume()` with quiet hours, player, socket
  client), `nullgrid sound list|set|test|mute|volume`, doctor checks (pack, player, PipeWire,
  daemon). Manifest target `sfx` -> `generated/sfx.json`, SIGHUP to process `nullgrid-sfx`.
  Paths: user packs in `~/.local/share/nullgrid/sounds/`.
- `tools/nullgrid-sfx/` (package `nullgrid-sfx` 0.6.0): `daemon.py` (selector loop: unix socket
  `$XDG_RUNTIME_DIR/nullgrid-sfx.sock` with play/playwait/status/reload/quit, Hyprland socket2 or
  swaymsg subscribe, udevadm monitor, battery poll; pw-play children; per-event 80 ms gap, max 4
  at once; exits with the compositor), `sources.py` (parsers), `cli.py` (`nullgrid-sfx
  daemon|play EVENT [--wait]|status|reload|quit`; play falls back to playing directly).
- Hooks: shell `Sfx.qml` (Quickshell `Socket`): menu open/close, clicks, hover, notifications
  (respects `suppress-sound`), bar volume/brightness scroll, menu no-match error. Scripts
  `nullgrid-lock`, `nullgrid-power logout|reboot|poweroff|suspend`, `nullgrid-media`; new keybind
  actions volume_up/down/mute, mic_mute, brightness_up/down (`locked`); lock/exit use the scripts.
  zsh: command_done (>= 10 s) / command_failed via `zsh/net/socket`; kitty `command_on_bell`.
- ISO: pipewire, pipewire-audio, wireplumber, pipewire-pulse, pipewire-alsa, pipewire-jack,
  sof-firmware. `run-vm.sh` sound to host (`AUDIO`), `--audio-wav=FILE` for the boot test.
- Tests: `make test` = 181 (generator output, packs, rules, CLI, daemon end to end with a fake
  pw-play and fake Hyprland socket). `make test-shell` checks daemon + shell/Sway sounds + mute.
  `make test-boot` records the VM's audio and checks a sound comes out, the volume key, lock
  sounds, boot/login sounds, cava. Docs: `docs/SOUND.md`, phase-6 section in DECISIONS.

**Gotchas learned (phase 6):**
- Never signal a process that doesn't handle the signal: a kitty that is still starting dies of
  SIGUSR1. `render.run_reload` checks `SigCgt | SigBlk` in /proc/PID/status (kitty blocks USR1
  and reads it from a signalfd: checking only SigCgt skipped it; fixed in phase 7).
- Loading a module with dataclasses via importlib needs `sys.modules[name] = mod` first.
- Two fake players started together log in either order: compare sorted in tests.
- `python -m pkg` processes are named `python`; the daemon sets its name with prctl so the
  manifest's `process = "nullgrid-sfx"` finds it however it was started.
- cava pulls `jack`: without `pipewire-jack` in the package list, pacman picks jack2.
- QEMU `-audiodev wav,path=...` records the guest's sound card; `sendkey volumeup` works.

**Phase 7 delivered:**
- `nullgrid toolkit apply [--reload] [--force]` (`toolkit.py`): from generated `toolkit.json` it
  builds the icon theme (`icons.py`: original line icons from `glyphs.py` in 4 frames, ~240 names,
  SVG, per palette) and cursors (`cursors.py`: 25 shapes, rsvg-convert sprite -> own PNG decoder ->
  own Xcursor writer, cached per palette in ~/.cache/nullgrid/cursors) into
  `~/.local/share/icons/NULLGRID/`, writes GSettings (theme/icons/cursor/fonts/color-scheme), and
  flips gtk-theme/icon-theme/cursor-theme to Adwaita and back so running GTK apps reload;
  `hyprctl setcursor` / swaymsg for the pointer. Paths gain `data_home` (`{data_home}` in manifest).
- Targets: `toolkit`, `gtk`/`gtk-dark`/`gtk4` (adw-gtk3 imported + palette + NULLGRID rules,
  `gtk-colors.inc.j2`, `gtk-rules.inc.j2`), `qt`/`qt-style`/`qt6ct` (qt6ct.conf has a palette
  `revision` so qt6ct's directory watcher restyles live), `zathura` (reload over D-Bus). 32 targets.
  `[theme.style] cursor_size`. `nullgrid theme palette [--preset] [--format vtrgb]`. Doctor checks.
- Session: `QT_QPA_PLATFORMTHEME=qt6ct` (nullgrid-session + Hyprland), XCURSOR_* in generated
  Hyprland theme, `seat * xcursor_theme` in Sway, `nullgrid toolkit apply` at session start.
  nullgrid-desktop: gschema override, `/etc/xdg/{hyprland,sway}-mimeapps.list`, Firefox policies,
  deps adw-gtk-theme qt6ct dconf gsettings-desktop-schemas. New keybind `browser` = SUPER+W, dock
  browser button.
- Package `nullgrid-boot`: Plymouth script theme (`plymouth/generate.py` pre-renders all images incl.
  text; `nullgrid.script` animates: wandering dead pixel, scanline, boot log, segmented progress,
  password prompt), greetd (drop-in -> `/usr/share/nullgrid/greetd/greetd.toml`) + tuigreet
  (`/etc/tuigreet/config.toml`, matrix background, sessions in /usr/share/nullgrid/sessions ->
  `nullgrid-login desktop|tty` -> `zsh -l` with `NULLGRID_SESSION_MODE`), console palette service
  (`setvtrgb`, crimson-hud). Splash and greeter always use crimson-hud.
- ISO: `quiet splash plymouth.ignore-serial-consoles fbcon=nodefer`, HOOKS `kms consolefont
  plymouth`, `/etc/plymouth/plymouthd.conf` Theme=nullgrid (airootfs; pacman keeps it, .pacnew),
  console palette service enabled (multi-user.target), second boot entry without splash. Firefox, Thunar, Ristretto,
  zathura(+pdf-mupdf, tesseract-data-eng), ttf-dejavu, greetd (not enabled; live = autologin).
  ISO ~1.9 GB. All packages 0.7.0 (fonts/base unchanged).
- Tests: `make test` (203+: icons, cursors incl. PNG/Xcursor round trips, toolkit apply with a fake
  gsettings, templates, splash generator, greeter files). `make test-shell` opens Thunar, zathura
  and a Qt window (`tests/qt_palette.qml`) and checks by pixels (`tests/window_color.py`) that they
  take the theme and follow a switch live. `make splash` previews Plymouth (X11 renderer + Xvfb).
  `make test-boot` grabs the splash during boot, checks toolkit settings, Thunar/Firefox across a
  theme switch, and logs in through greetd on tty3 into TTY mode. Docs: `docs/TOOLKITS.md`,
  `docs/BOOT.md`, phase-7 section in DECISIONS.

**Gotchas learned (phase 7):**
- GTK only re-reads a theme when its name changes: flip the gsettings key away and back.
  libadwaita ignores themes; `~/.config/gtk-4.0/gtk.css` would freeze colors for all GTK 4 apps.
- qt6ct ignores itself (its own window is no Qt test) and watches only `~/.config/qt6ct/`, not
  `colors/` or `qss/`: change qt6ct.conf (written last) to trigger a restyle.
- The QEMU monitor socket takes one client at a time: share one connection in tests.
- Plymouth + deferred fbcon takeover = `systemd-vconsole-setup` racing Hyprland for tty1 (EIO,
  "degraded", no Terminus font). Fixed with `fbcon=nodefer` + `consolefont` hook (installer too).
- Plymouth restores the console palette it found when it quits: the palette service runs after
  `plymouth-quit-wait`. greetd sets no TERM: `nullgrid-login` exports `TERM=linux` on a VT.
- Manifest reload commands only expand `{target}` now (shell/awk braces pass through).
- pacman picks the first provider alphabetically: pin `tesseract-data-eng`, `ttf-dejavu`.
- Plymouth's script language: no reliable number->string formatting; spell names out in generated
  arrays. `plymouthd --no-daemon` + `plymouth show-splash` under Xvfb uses the X11 renderer.

**Phase 8 delivered:**
- Package `nullgrid-installer` (`tools/installer/nullgrid_install/`, Python/Textual): `nullgrid-install`
  (TUI; `--config FILE [--yes]` unattended, `--dry-run`, `--list-disks`, `--detect`) and
  `nullgrid-welcome` (first-run wizard: theme applied live, sound pack with samples, mode;
  `--theme/--sound/--mode` for scripts, `--status`). Modules: `hw` (lsblk disks, sysfs GPUs,
  `driver_plan`), `options` (keyboard table console keymap <-> XKB, locales, zones), `config`
  (`InstallConfig`, TOML, validation), `install` (`Installer` steps over a `System`; tests use a fake).
- Install = copy `/run/archiso/airootfs` (pristine squashfs) to the disk, kernel from
  `/usr/lib/modules/*/vmlinuz`, remove `LIVE_ONLY` files, userdel the live user. GPT: 1 GiB FAT32
  /boot (ESP + LegacyBIOSBootable) + ext4 / (optional LUKS2, `encrypt` hook, passphrase in the
  splash). Both systemd-boot (UEFI, + fallback path) and syslinux/extlinux (BIOS, gptmbr.bin).
  mkinitcpio `kms consolefont plymouth` (+`encrypt`), default+fallback preset, `quiet splash
  fbcon=nodefer`, serial console kept if the live boot had one. greetd + console palette enabled,
  root locked, wheel sudo with password, own pacman keyring, `/etc/nullgrid/installed` marker,
  `/etc/nullgrid/install-notes` (e.g. GPU drivers skipped offline), log copied to /var/log.
- GPU: Intel `vulkan-intel intel-media-driver`, AMD `vulkan-radeon`, NVIDIA >= Turing (dev id >=
  0x1e00) `nvidia-open nvidia-utils` (+`nvidia-prime` hybrid, modules in initramfs if NVIDIA drives
  the screen), older NVIDIA `vulkan-nouveau`; only network need. `nullgrid-session` sets NVIDIA env
  vars when NVIDIA is the boot GPU, and XKB_DEFAULT_* from `/etc/X11/xorg.conf.d/00-keyboard.conf`
  (Hyprland reads them via os.getenv; Sway config no longer hardcodes `us`).
- zsh: first console login of an installed system runs `nullgrid-welcome` before the session.
  Live ISO: start-menu entry (`/usr/local/share/applications/nullgrid-install.desktop`, live-only),
  dashboard launcher `install`, login hint. ISO adds `arch-install-scripts dosfstools`.
- `run-vm.sh --disk=FILE [--hd]`; `make test-install [ENCRYPT=1]` (`tests/install_smoke.py`):
  unattended install from the ISO, boots the disk UEFI (checks, greeter login, wizard -> TTY
  mode) and BIOS. `make test` = 246 (incl. `tests/nullgrid_install`). All packages 0.8.0
  (fonts/base unchanged). Docs: `docs/INSTALL.md`, phase-8 section in DECISIONS.

**Gotchas learned (phase 8):**
- `cp -a` onto a mounted FAT /boot fails (can't set owner/mode of the mount point): mount /boot
  after copying the system.
- Textual: Option prompts are markup (`[text]` vanishes; pass `Text`); a theme registered in
  `on_mount` may need `refresh_css()`; a second click on a Button within 0.2 s is ignored (tests
  use `button.press()`). Inputs/Buttons/Checkboxes default to half-block borders: override for the console.
- `tests/nullgrid_install/insttest.py` holds the shared helpers (several conftest.py exist).
- Every new file in `iso/airootfs` must be listed in `install.LIVE_ONLY` or `install.KEEP` (test).
- The live ISO runs `LANG=C.UTF-8`, which isn't in glibc's SUPPORTED list: default to en_US.UTF-8.
- Serial checks strip each line: no trailing spaces in expected regexes.

**Phase 9 delivered:**
- `nullgrid perf [--seconds N] [--top N] [--json]` (`nullgrid/perf.py`): PSS + CPU per component
  (compositor, shell, wallpaper, sound, audio, terminal, ...), start times, leaves itself out.
- `make perf` (`tests/perf_smoke.py`, `PERF_ARGS`): ISO in a 4 GB VM without 3D, Hyprland then
  Sway lite, 90 s settle + 60 s window -> `out/perf/report.{md,json}`; budget Hyprland < 750 MiB,
  lite < 700 MiB, shell/wallpaper/sound < 2% CPU. Result: Hyprland 718-738 MiB, lite 585-608 MiB (boot-to-boot variance), shell
  0.2%, compositor 2.1%; shell up 14.7 s after boot. User accepted 722 as meeting "~700" (VM =
  worst case, software rendering). Docs: `docs/PERFORMANCE.md`, phase-9 section in DECISIONS.
- Fixes: THP `madvise` (`nullgrid-base` tmpfiles, -150 MiB); NULLGRID_SOFTWARE_RENDER: widgets
  >= 2 s (`shell/Theme.qml`), no blur (generated Hyprland theme); kitty `auto_reload_config -1`;
  live autologin gettys `Type=simple`; `nullgrid-shell restart` kills both config paths.
  Boot test checks kitty config errors and no `__watch_conf__`. All packages 0.9.0 (fonts unchanged).

**Gotchas learned (phase 9):**
- getty@.service is `Type=idle`: it waits up to 5 s for other boot jobs (live: pacman-init).
- kitty `auto_reload_config` is a number (seconds; negative = off). A bad value doesn't fail:
  kitty opens a `kitten __show_error__` window.
- Repeated session restarts in one boot drift "memory used" upward: compare fresh boots only.
- PSS counts file-backed pages; "used" (MemTotal - MemAvailable) is anon + shmem + kernel. Check
  `Anonymous:` in smaps_rollup to see what really costs.
- `quickshell kill` takes `-c NAME` or `-p PATH`; an instance started from another config path
  isn't found by `-c`.
- For digging into a running VM: `tests/probe_vm.py` boots once and runs commands written to
  `out/probe/cmd-NN.sh` (output in `out-NN.txt`); usage in its docstring.

**Release 1.0.0 (2026-10-14):** `VERSION` file = single source (packages, tools, os-release;
`tests/nullgrid/test_versions.py`), ISO `nullgrid-<VERSION>-x86_64.iso`. GitHub release `v1.0.0`
with the ISO + SHA256SUMS; notes `docs/releases/v1.0.0.md`, `CHANGELOG.md`, procedure
`docs/RELEASING.md`. `gh` is in `~/.local/bin` (logged in as bitmattz). Release QA all PASS:
test, test-shell, test-boot, test-install, perf (Hyprland 718 MiB, lite 602 MiB).
Deferred by the owner: a signed `[nullgrid]` pacman repo for updates (design in DECISIONS.md).
Package check() tarballs need `VERSION` and `pkg/` (build-packages.sh).

**After 1.0.0 (unreleased): Wi-Fi + Bluetooth pickers in the bar.** `shell/Net.qml`, `Bt.qml`
(singletons: state/actions), `NetPicker.qml`, `BtPicker.qml`, `Popout.qml`, `PickerButton.qml`,
`PickerDemo.qml` (fakes when `NULLGRID_SHELL_DEMO=1`). Bar icon: left click = picker, right click
= radio. IPC: `openPicker/togglePicker/closePicker`, `wifi`, `bluetooth` (JSON), `wifiConnect NAME
PSK`, `btActivate ADDR`, `demoLog`; `nullgrid-shell wifi|bluetooth`. ISO: `bluez bluez-utils`
(bluetooth.service via bluetooth.target.wants + dbus-org.bluez alias, in install.KEEP), `dnsmasq`.
Boot test `wifi_tour`: mac80211_hwsim + `nmcli device wifi hotspot` on wlan1, the picker joins
from wlan0 (wrong password first). Gotchas: polkit only authorizes NetworkManager for processes
in the active desktop session (a shell restarted from serial gets "Not authorized"); Hyprland
Lua `hyprctl dispatch` takes Lua (`'hl.dsp...'`), not `exec cmd`; `connectWithPsk` on a saved
network updates its password (don't `forget()` first: it races); hwsim radios are "unavailable"
for ~1 s; NM hotspots need dnsmasq. Shipped as 1.1.0.

**Update repository (1.1.0, 2026-10-14):** signed `[nullgrid]` pacman repo = GitHub pre-release
`repo` (Server `https://github.com/bitmattz/nullgrid/releases/download/repo`). Key: ed25519, no
passphrase/expiry, fingerprint 3494FF826CBF4E4AB1E83049FD658A9D368049E7, private in
`~/.local/share/nullgrid-signing` (never in git; owner should back it up). `make sign-key`
(`build/signing-key.sh`, exports public key to `pkg/nullgrid-keyring/`), `make publish-repo`
(`make repo` -> `build/sign-repo.sh` in Docker -> `build/publish-repo.sh` with gh; replaces all
assets). `nullgrid-keyring` (date-versioned) adds `[nullgrid]` (SigLevel Required
DatabaseRequired) via its install script; on the ISO; installer populates `archlinux nullgrid`.
`nullgrid-core` ships `nullgrid-refresh.hook` (stamps /var/lib/nullgrid/updated; zsh runs
`nullgrid init` at next login when newer). `nullgrid update [--yes] [--no-system]
[--restart-shell]`. `nullgrid-desktop.install` enables bluetooth once when upgrading from <1.1.0.
`make test-upgrade [FROM=old.iso]` (`tests/upgrade_smoke.py`): installs out/v1.0.0 ISO, keyring,
pacman -Syu from out/publish served at 10.0.2.2:8080: PASS. Rule: only released versions go into
the repo (bump VERSION; tag vX.Y.Z; GitHub release page/ISO may come later). Docs: UPDATING.md,
RELEASING.md section 5. Gotchas: `echo x | sudo -S tee` writes the password (use sh -c); package
builds aren't reproducible (checksums change per build): publish the files you tested (run
build/publish-repo.sh directly), and docs verify the key fingerprint, not a package checksum.

**Next (after phase 9):** the Raspberry Pi SD-image builder (`docs/DECISIONS.md`, light hardware
strategy). Ideas not done: measure on a real GPU / with virgl; Xwayland on demand.

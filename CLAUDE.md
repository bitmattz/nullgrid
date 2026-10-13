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

### Status as of 2026-10-12: Phase 1 DONE, next is Phase 2

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

**Open items waiting on me:**
- Pick a logo concept in `docs/LOGO.md` (A "Null cell" is recommended) before phase 4 draws it.

**Next step, Phase 2 (theme engine + `nullgrid` CLI):** `tools/nullgrid/` Python package; the
`nullgrid.toml` schema with validation (incl. a `[performance] profile = full|lite`); Jinja templates in
`config/templates/`; render + hot-reload; `theme list|set|edit|reload`, `widget toggle`, `mode`,
`doctor`; presets `themes/crimson-hud|ice-protocol|toxic-grid.toml`; pytest snapshot tests;
package it as `pkg/nullgrid-core`; add it to the ISO; extend `make test-boot`.

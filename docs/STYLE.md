# NULLGRID visual style guide

Source of truth for the look. Theme presets (`themes/*.toml`, phase 2) must keep these rules;
only the palette changes between presets.

- **Colors (crimson-hud):** background `#1a0b0f`→`#2a0f15` gradient, surfaces `#24111a` at ~85% opacity, primary accent neon cyan `#5ef2f2`, secondary accent hot red `#ff3b4e`, border glow `#ff4d6d`, text `#e6f7f7`, dim text `#7a8a8f`, warning `#ffd166`.
- **Shapes:** chamfered (45° cut) corners on panels and frames, thin 1–2px lines, circular icon buttons, hatched/striped fills for active states, segmented bars.
- **Typography:** a condensed, technical UI font (open-licensed, e.g. Rajdhani, Oxanium, Chakra Petch, or Orbitron for display) and a clean mono font (JetBrains Mono / Iosevka) for the terminal. Verify licenses (OFL) before bundling.
- **Motion:** quick (120–220 ms), slightly mechanical easing; glitch/flicker only for rare events (boot, lock); no motion sickness — respect a `reduce_motion` flag.
- **Density:** small labels in uppercase, decorative serial numbers / coordinates, but readable — decoration must never cover content.
- **Linux console:** the console font (Terminus) has only these non-ASCII glyphs that matter
  here: `─ │ ┌ ┐ └ ┘ ├ ┤ ┬ ┴ ┼ █ ░ ▒ ■ ▲ ▼ ► ◄ ◆ · • › » ↑ ↓`. It has no half blocks,
  double lines or powerline/Nerd glyphs. Anything shown on a TTY uses only these, and only
  palette slots (0-15) as colors. Tests enforce both.
- **Screen layout:** the left edge belongs to the dock, the bottom to the status bar, and the
  bottom right to the HUD widgets. Wallpaper decor that carries text (logo plate, data blocks,
  keymap) stays out of those areas: the logo plate goes top right, data top left and bottom left.
  Circuit traces may run anywhere along the edges.

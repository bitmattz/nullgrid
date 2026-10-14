# GTK, Qt, icons and cursors

GUI apps get the NULLGRID look from the same `nullgrid.toml` as everything else. A theme switch
restyles them while they run, along with their icons and the mouse pointer.

```sh
nullgrid theme set toxic-grid     # Thunar, Firefox, Qt apps, icons and pointer follow
nullgrid toolkit apply            # regenerate icons/cursors if needed, write the GTK settings
nullgrid toolkit apply --force    # redo them even if they look up to date
```

## What ships

| | |
|---|---|
| GTK 3 / GTK 4 | the **NULLGRID** theme, generated per user into `~/.local/share/themes/NULLGRID/` |
| Qt 6 | qt6ct: Fusion style, the NULLGRID palette and a style sheet, icons and fonts (`~/.config/qt6ct/`) |
| Icons | the **NULLGRID** icon theme, original line icons generated in your colors (`~/.local/share/icons/NULLGRID/`) |
| Pointer | **NULLGRID** cursors, generated in your colors (same directory, `cursors/`) |
| Apps on the ISO | Firefox, Thunar (files), Ristretto (images), zathura (PDF) |

The GTK theme is [adw-gtk3](https://github.com/lassekongo83/adw-gtk3) (package
`adw-gtk-theme`) recolored with the palette, plus the NULLGRID details: square corners
(`corners = "round"` gives slight rounding), a neon line under header bars, hatched toggles and
selections, segmented progress bars, a glow on default buttons and focused text fields. Window
borders and glow come from Hyprland/Sway, so GTK draws no shadow of its own.

## How a theme switch reaches running apps

- **GTK** apps re-read a theme only when its name changes. `nullgrid toolkit apply --reload` (run
  by `nullgrid theme set`) switches the theme name to Adwaita and back, a quarter second apart.
- **Qt** apps restyle when qt6ct sees its config change. The session sets
  `QT_QPA_PLATFORMTHEME=qt6ct` for them.
- **Icons and the pointer** are regenerated when the colors change (under a second; pointers are
  cached per palette, so going back to a theme is instant). Hyprland and Sway load the new pointer
  at once.
- **zathura** re-reads its colors through its D-Bus interface. **Firefox** follows the GTK colors
  in its default theme.

GTK apps read the theme, icons, pointer, fonts and dark style from GSettings
(`org.gnome.desktop.interface`). `nullgrid toolkit apply` writes them from `[theme.fonts]` and
`[theme.style] cursor_size`; defaults for users who never ran it come with nullgrid-desktop.

## Limits

- **libadwaita apps** (most GNOME apps) ignore GTK themes by design. They get the dark style but
  keep their own colors. NULLGRID ships none of them.
- GTK 2 and Qt 5 apps aren't themed (none are installed; for Qt 5, install and set up `qt5ct` the
  same way).
- Firefox's web pages keep their own design; only the browser's frame follows GTK.

## Icons

Every icon is a line glyph in a frame, drawn by `tools/nullgrid/nullgrid/icons.py` from the
glyphs in `glyphs.py` (the same set the shell's dock and menus use):

- apps and categories: a circle with a HUD tick in the second accent,
- folders: a chamfered folder, with a glyph for Documents, Downloads, Music...,
- file types: a sheet with a cut corner,
- devices and trash: a chamfered plate.

About 240 icon names are covered (generic names like `utilities-terminal`, and the apps on the
ISO). Anything else comes from Adwaita (its symbolic icons, which GTK paints in the theme's text
color) and hicolor (apps' own icons). To change a drawing, edit `icons.py` and run
`nullgrid toolkit apply --force`.

## Cursors

25 shapes on a 32 px grid (`cursors.py`): an angular arrow, a hand, an I-beam, a reticle, resize
arrows, an animated ring for busy. Each is written at 24, 32 and 48 px plus your `cursor_size`.
All names apps ask for (CSS names, X11 names, the hashes Qt and Firefox use) are covered.

```toml
[theme.style]
cursor_size = 32
```

## Default apps

`/etc/xdg/hyprland-mimeapps.list` and `sway-mimeapps.list` (nullgrid-desktop) open folders in
Thunar, PDFs in zathura, images in Ristretto and web links in Firefox. Choices in
`~/.config/mimeapps.list` (for example from Thunar's "Open With") come first.

## Troubleshooting

- `nullgrid doctor` checks the GTK base theme, the icons and cursors, the GSettings values and
  the Qt setup.
- An app looks like plain Adwaita: it may be a libadwaita app (see Limits), or it started before
  the session's settings were in place; restart it.
- A Qt app ignores the theme: check `echo $QT_QPA_PLATFORMTHEME` in its environment (should be
  `qt6ct`).

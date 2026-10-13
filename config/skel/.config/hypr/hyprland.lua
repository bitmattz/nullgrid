-- Hyprland config of the NULLGRID desktop. This file is yours: add your settings at the end.
--
-- What's loaded, in order:
--   /usr/share/nullgrid/hypr/nullgrid.lua   defaults: input, layout, rules, autostart
--   nullgrid-theme.lua                      generated: colors, borders, glow, blur, animations
--   nullgrid-keys.lua                       generated: keybinds (`nullgrid keys` lists them)
-- The generated files follow ~/.config/nullgrid/nullgrid.toml; don't edit them, they're rewritten.
-- Docs: docs/DESKTOP.md. Hyprland's options: https://wiki.hypr.land/Configuring/Start/

local config = (os.getenv("XDG_CONFIG_HOME") or (os.getenv("HOME") .. "/.config")) .. "/hypr/"

local function load(path)
    local f = io.open(path)
    if not f then
        return {}
    end
    f:close()
    return dofile(path)
end

load("/usr/share/nullgrid/hypr/nullgrid.lua")
local ng = load(config .. "nullgrid-theme.lua")  -- the palette, e.g. ng.primary = "rgba(5ef2f2ff)"
load(config .. "nullgrid-keys.lua")

-- Terminal-first: open one at login (floating; the class picks the window rule).
hl.on("hyprland.start", function()
    hl.exec_cmd("kitty --class nullgrid-welcome")
end)

-- Your settings below. Examples:
-- hl.config({ input = { kb_layout = "de" } })
-- hl.bind("SUPER + W", hl.dsp.exec_cmd("firefox"))
-- hl.window_rule({ name = "mpv", match = { class = "^mpv$" }, float = true, border_color = ng.primary })

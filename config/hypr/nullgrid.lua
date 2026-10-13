-- NULLGRID Hyprland defaults: /usr/share/nullgrid/hypr/nullgrid.lua (nullgrid-desktop package).
-- ~/.config/hypr/hyprland.lua loads this first, so anything here can be overridden there.
-- The look (colors, borders, glow, blur, animations) and the keybinds are generated from
-- nullgrid.toml into ~/.config/hypr/nullgrid-{theme,keys}.lua.

hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "auto" })

hl.env("XCURSOR_SIZE", "24")
hl.env("HYPRCURSOR_SIZE", "24")
hl.env("XDG_CURRENT_DESKTOP", "Hyprland")
hl.env("XDG_SESSION_DESKTOP", "Hyprland")
hl.env("QT_QPA_PLATFORM", "wayland;xcb")

hl.config({
    general = { layout = "dwindle", resize_on_border = true },
    dwindle = { preserve_split = true },
    input = {
        kb_layout = "us",
        follow_mouse = 1,
        touchpad = { natural_scroll = false, tap_to_click = true, disable_while_typing = true },
    },
    misc = {
        force_default_wallpaper = 0,
        disable_hyprland_logo = true,
        disable_splash_rendering = true,
        focus_on_activate = true,
        allow_session_lock_restore = true,  -- a crashed lock screen can be started again
    },
    ecosystem = { no_update_news = true, no_donation_nag = true },
})

-- Without a GPU render node (e.g. a VM without 3D acceleration) the cursor plane doesn't work.
if os.getenv("NULLGRID_SOFTWARE_RENDER") == "1" then
    hl.config({ cursor = { no_hardware_cursors = true } })
end

-- The terminal opened at login floats left of center: the HUD decor (logo plate, keymap,
-- data blocks) stays visible around it. SUPER+V tiles it.
hl.window_rule({
    name = "nullgrid-welcome",
    match = { class = "^nullgrid-welcome$" },
    float = true,
    -- expressions, not percentages: "44% 58%" passes --verify-config but is silently ignored
    size = "monitor_w*0.44 monitor_h*0.58",
    move = "monitor_w*0.15 monitor_h*0.18",
})

-- NULLGRID's own popups open floating and centered.
hl.window_rule({
    name = "nullgrid-popups",
    match = { class = "^nullgrid-(keys|dash|btop)$" },
    float = true,
    size = "960 640",
    center = true,
})

-- Blur behind the launcher and the shell's bar, dock, menu and notifications.
hl.layer_rule({
    name = "nullgrid-blur",
    match = { namespace = "^(launcher|nullgrid-(bar|dock|menu|notifications))$" },
    blur = true,
    ignore_alpha = 0.2,
})

hl.on("hyprland.start", function()
    -- D-Bus activated services (notifications, portals) need to find this session.
    hl.exec_cmd("dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP HYPRLAND_INSTANCE_SIGNATURE")
    hl.exec_cmd("nullgrid wallpaper apply --quiet")
    hl.exec_cmd("nullgrid-shell")  -- bar, dock, HUD widgets, start menu, notifications
end)
-- A new screen gets a wallpaper rendered for its size.
hl.on("monitor.added", function()
    hl.exec_cmd("nullgrid wallpaper apply --quiet")
end)

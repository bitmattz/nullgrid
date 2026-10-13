-- NULLGRID colorscheme. Colors come from lua/nullgrid/palette.lua, which the theme engine
-- generates; each group also gets the matching palette slot for the Linux console.
package.loaded["nullgrid.palette"] = nil
local ok, p = pcall(require, "nullgrid.palette")
if not ok then
  vim.notify("nullgrid colorscheme: no palette yet, run `nullgrid theme reload`", vim.log.levels.WARN)
  return
end

vim.cmd("highlight clear")
vim.g.colors_name = "nullgrid"

local t, a = p.terminal, p.ansi
-- role name or terminal slot -> { gui color, cterm index }
local function c(x)
  if type(x) == "number" then return { t[x + 1], x } end
  return { p[x], a[x] or 0 }
end
local green, blue, magenta = c(2), c(4), c(5)

local function hl(group, fg, bg, extra)
  local spec = extra or {}
  if fg then spec.fg, spec.ctermfg = fg[1], fg[2] end
  if bg then spec.bg, spec.ctermbg = bg[1], bg[2] end
  vim.api.nvim_set_hl(0, group, spec)
end

-- With a translucent terminal, leave the background to the terminal.
local bg = nil
if not p.transparent then bg = { p.bg, nil } end
local text, dim, primary, secondary, glow, warning =
  c("text"), c("dim"), c("primary"), c("secondary"), c("glow"), c("warning")
local surface, bg_alt, sel = { p.surface, 0 }, { p.bg_alt, 0 }, { p.selection, 0 }

-- editor
hl("Normal", text, bg)
hl("NormalNC", text, bg)
hl("NormalFloat", text, surface)
hl("FloatBorder", primary, surface)
hl("FloatTitle", secondary, surface, { bold = true })
hl("Cursor", { p.bg, 0 }, primary)
hl("CursorLine", nil, bg_alt)
hl("CursorLineNr", primary, nil, { bold = true })
hl("LineNr", dim)
hl("SignColumn", dim)
hl("ColorColumn", nil, bg_alt)
hl("Visual", nil, sel)
hl("Search", { p.bg, 0 }, warning)
hl("IncSearch", { p.bg, 0 }, primary)
hl("CurSearch", { p.bg, 0 }, primary)
hl("MatchParen", secondary, nil, { bold = true, underline = true })
hl("StatusLine", text, surface)
hl("StatusLineNC", dim, surface)
hl("WinSeparator", { p.surface, 8 })
hl("TabLine", dim, surface)
hl("TabLineSel", { p.bg, 0 }, primary, { bold = true })
hl("TabLineFill", nil, bg_alt)
hl("Pmenu", text, surface)
hl("PmenuSel", { p.bg, 0 }, primary)
hl("PmenuSbar", nil, surface)
hl("PmenuThumb", nil, primary)
hl("Folded", dim, bg_alt)
hl("NonText", { p.surface, 8 })
hl("Whitespace", { p.surface, 8 })
hl("EndOfBuffer", { p.surface, 8 })
hl("Directory", primary)
hl("Title", secondary, nil, { bold = true })
hl("ErrorMsg", secondary, nil, { bold = true })
hl("WarningMsg", warning)
hl("MoreMsg", primary)
hl("Question", primary)
hl("ModeMsg", primary, nil, { bold = true })

-- syntax
hl("Comment", dim, nil, { italic = true })
hl("Constant", warning)
hl("String", green)
hl("Character", green)
hl("Number", warning)
hl("Boolean", warning, nil, { bold = true })
hl("Identifier", text)
hl("Function", primary)
hl("Statement", secondary)
hl("Keyword", secondary)
hl("Operator", glow)
hl("PreProc", magenta)
hl("Type", blue)
hl("Special", glow)
hl("Delimiter", dim)
hl("Todo", { p.bg, 0 }, warning, { bold = true })
hl("Error", secondary, nil, { undercurl = true })
hl("Underlined", primary, nil, { underline = true })

-- diagnostics, diffs, git
hl("DiagnosticError", secondary)
hl("DiagnosticWarn", warning)
hl("DiagnosticInfo", primary)
hl("DiagnosticHint", dim)
hl("DiagnosticUnderlineError", nil, nil, { undercurl = true, sp = p.secondary })
hl("DiagnosticUnderlineWarn", nil, nil, { undercurl = true, sp = p.warning })
hl("DiffAdd", green, bg_alt)
hl("DiffChange", warning, bg_alt)
hl("DiffDelete", secondary, bg_alt)
hl("DiffText", { p.bg, 0 }, warning)
hl("Added", green)
hl("Changed", warning)
hl("Removed", secondary)

-- :terminal uses the same 16 colors as kitty
for i = 0, 15 do
  vim.g["terminal_color_" .. i] = t[i + 1]
end

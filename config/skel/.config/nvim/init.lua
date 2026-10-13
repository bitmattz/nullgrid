-- NULLGRID neovim defaults: small, no plugin manager. Add your own below.
local o = vim.opt
o.number = true
o.relativenumber = true
o.cursorline = true
o.signcolumn = "yes"
o.mouse = "a"
o.ignorecase = true
o.smartcase = true
o.expandtab = true
o.shiftwidth = 4
o.tabstop = 4
o.undofile = true
o.scrolloff = 6
o.splitright = true
o.splitbelow = true
o.clipboard = "unnamedplus"
-- The Linux console has 16 colors: use the palette slots there, true color elsewhere.
o.termguicolors = vim.env.TERM ~= "linux"
vim.g.mapleader = " "

vim.cmd.colorscheme("nullgrid")

-- Restyle live when `nullgrid theme ...` rewrites the palette. The file is replaced
-- atomically, so watch its directory rather than the file.
local dir = vim.fn.stdpath("config") .. "/lua/nullgrid"
local watcher = vim.uv.new_fs_event()
if watcher and vim.uv.fs_stat(dir) then
  watcher:start(dir, {}, vim.schedule_wrap(function(err, name)
    if not err and name == "palette.lua" and vim.g.colors_name == "nullgrid" then
      vim.cmd.colorscheme("nullgrid")
    end
  end))
end

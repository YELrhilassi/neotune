-- lua/init.lua
-- Main initialization file for Spotify TUI config

-- Enable auto-play on startup
spotify_tui.set_auto_play(true)

require("theme")
require("audio")
require("keymaps")
require("commands")

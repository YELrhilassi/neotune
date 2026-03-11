-- lua/init.lua
-- Main initialization file for Spotify TUI config

-- Enable auto-play on startup
spotify_tui.set_auto_play(true)
spotify_tui.set_auto_select_device(true)

require("theme")
require("audio")
require("keymaps")
require("commands")
require("debug")
require("special_playlists")

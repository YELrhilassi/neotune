-- lua/init.lua
-- Main initialization file for NeoTune config

-- Enable auto-play on startup
neotune.set_auto_play(true)
neotune.set_auto_select_device(true)

require("theme")
require("audio")
require("keymaps")
require("commands")
require("debug")
require("special_playlists")

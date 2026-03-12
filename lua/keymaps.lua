-- lua/keymaps.lua
-- Neovim-style Key Mappings

-- Set the leader key
neotune.set_leader("space")

-- Toggle WhichKey popup visibility
neotune.set_which_key(true)

-- Global Navigation Keys
neotune.set_nav("k", "j", "h", "l", "U", "D")

-- Map leader actions
neotune.map("p", "play_pause", "Play/Pause")
neotune.map("n", "next_track", "Next Track")
neotune.map("b", "prev_track", "Previous Track")
neotune.map("x", "toggle_shuffle", "Toggle Shuffle")
neotune.map("y", "cycle_repeat", "Cycle Repeat")
neotune.map("e", "toggle_sidebar", "Toggle Sidebar")
neotune.map("t", "theme_selector", "Theme Selector")
neotune.map(":", "command_prompt", "Command Prompt")
neotune.map("/", "search_prompt", "Search Tracks/Playlists")
neotune.map("space", "search_prompt", "Telescope Search")
neotune.map("o", "show_device", "Output Device")
neotune.map("a", "show_audio", "Audio Backend")
neotune.map("r", "refresh", "Refresh Data")
neotune.map("R", "recommendations", "Start Track Radio")
neotune.map("D", "restart_daemon", "Restart Playback Daemon")
neotune.map("Q", "logout", "Logout (Clear Session)")

neotune.map("s", "fuzzy_search", "Fuzzy Search App Content")

-- lua/keymaps.lua
-- Neovim-style Key Mappings

-- Set the leader key
spotify_tui.set_leader("space")

-- Toggle WhichKey popup visibility
spotify_tui.set_which_key(true)

-- Global Navigation Keys
spotify_tui.set_nav("k", "j", "h", "l", "U", "D")

-- Map leader actions
spotify_tui.map("p", "play_pause", "Play/Pause")
spotify_tui.map("n", "next_track", "Next Track")
spotify_tui.map("b", "prev_track", "Previous Track")
spotify_tui.map("x", "toggle_shuffle", "Toggle Shuffle")
spotify_tui.map("y", "cycle_repeat", "Cycle Repeat")
spotify_tui.map("e", "toggle_sidebar", "Toggle Sidebar")
spotify_tui.map("t", "theme_selector", "Theme Selector")
spotify_tui.map(":", "command_prompt", "Command Prompt")
spotify_tui.map("/", "search_prompt", "Search Tracks/Playlists")
spotify_tui.map("space", "search_prompt", "Telescope Search")
spotify_tui.map("o", "show_device", "Output Device")
spotify_tui.map("a", "show_audio", "Audio Backend")
spotify_tui.map("r", "refresh", "Refresh Data")
spotify_tui.map("R", "recommendations", "Start Track Radio")
spotify_tui.map("D", "restart_daemon", "Restart Playback Daemon")
spotify_tui.map("Q", "logout", "Logout (Clear Session)")

spotify_tui.map("s", "fuzzy_search", "Fuzzy Search App Content")

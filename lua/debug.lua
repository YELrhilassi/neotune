-- lua/debug.lua
-- Debug and network tracking configuration
-- Uncomment and modify the settings below to enable debugging

--[[
neotune.set_debug({
    enabled = true,                    -- Enable debug logging
    network_tracking = true,           -- Track network requests
    performance_tracking = true,       -- Track performance metrics
    log_to_file = false,             -- Write logs to file (optional)
    log_file_path = "~/.config/neotune/debug.log",
    max_log_entries = 1000,          -- Max log entries in memory
    max_network_history = 100,       -- Max network requests to track
    log_level = "info",              -- Minimum log level: debug, info, warning, error
    auto_scroll = true,              -- Auto-scroll logs in the window
    show_timestamps = true,          -- Show timestamps in logs
    compact_mode = false             -- Compact log format
})
--]]

-- Default: disabled (uncomment above to enable)
-- Press Ctrl+L to open the debug window with tabs for:
--   - Logs: Application logs and messages
--   - Network: Tracked API requests with timing
--   - Performance: Performance metrics and statistics
--   - Player: Local player (librespot) logs
--   - Settings: Current debug configuration

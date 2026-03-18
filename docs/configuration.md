# Lua Configuration Guide

NeoTune leverages Lua for its configuration system, allowing users to define their own keybindings, themes, and audio settings in a format that should feel very familiar to Neovim users.

## Table of Contents

- [Config Directory Structure](#config-directory-structure)
- [Setup Instructions](#setup-instructions)
- [Global Settings](#global-settings)
- [Keybindings](#keybindings-keymapslua)
- [Audio Configuration](#audio-configuration-audi_lua)
- [Custom Commands](#custom-commands-commands_lua)
- [Theme Configuration](#theme-configuration-themelua)
- [Special Playlists](#special-playlists-special_playlists_lua)
- [Advanced Configuration](#advanced-configuration)
- [Troubleshooting](#troubleshooting)

## Config Directory Structure

By default, the application looks for configuration files in the `lua/` directory:

```bash
lua/
├── init.lua          # Entry point
├── keymaps.lua       # Keybindings and leader mappings
├── theme.lua         # User-defined UI themes
├── audio.lua         # Bitrate and playback backend setup
├── commands.lua      # Custom command aliases
└── special_playlists.lua  # Custom playlist definitions
```

### User Config Location

User configurations are stored in `~/.config/neotune/`:

```bash
~/.config/neotune/
├── init.lua          # User configuration (created automatically)
├── theme.lua         # User theme overrides
└── .credentials.yml  # Secure credential storage
```

## `init.lua`

Your `init.lua` is where you tie everything together. You can use the standard `require()` function to load other configuration modules:

```lua
-- lua/init.lua

-- Enable auto-play on startup (optional)
neotune.set_auto_play(true)

require("theme")
require("keymaps")
require("audio")
require("commands")
```

## Global Settings

| Function | Description |
| --- | --- |
| `neotune.set_leader(key)` | Sets the leader key (default: `space`) |
| `neotune.set_which_key(boolean)` | Toggles the WhichKey discovery popup |
| `neotune.set_auto_play(boolean)` | Automatically start playback on application launch |
| `neotune.set_theme(name)` | Sets the UI theme |

## Keybindings (`keymaps.lua`)

The application uses a "leader" system similar to Neovim. You first press a leader key (like `space`), followed by an action key.

### Setting the Leader Key

```lua
-- lua/keymaps.lua
neotune.set_leader("space") -- Use a string key name
```

### Mapping Actions

You can map specific actions to keys using `neotune.map(key, action, description)`:

```lua
-- lua/keymaps.lua
neotune.map("p", "play_pause", "Play / Pause")
neotune.map("n", "next_track", "Next Track")
neotune.map("b", "prev_track", "Previous Track")
neotune.map("space", "search_prompt", "Telescope Search")
neotune.map("Q", "logout", "Logout (Clear session)")
```

Additional actions available for mapping:
- `fuzzy_search`: Open the Fuzzy Finder for local Tracks/Playlists
- `toggle_shuffle`: Toggle playback shuffle
- `cycle_repeat`: Cycle through repeat modes
- `toggle_sidebar`: Toggle the visibility of the sidebar
- `theme_selector`: Open the visual theme selector
- `command_prompt`: Open the command bar (`:`)
- `search_prompt`: Open the Telescope global search bar (`/`)
- `show_device`: Open the device selector
- `show_audio`: Open the audio backend configuration
- `refresh`: Manually refresh all library data
- `logout`: Wipe all sessions and credentials

### Navigation Keys

You can customize the global navigation keys used to traverse lists and panels:

```lua
-- lua/keymaps.lua
-- Parameters: up, down, left, right, page_up, page_down
neotune.set_nav("k", "j", "h", "l", "U", "D")
```

## Audio Configuration (`audio.lua`)

Control the quality and backend of your high-quality DRM playback.

```lua
-- lua/audio.lua
-- Parameters: backend, device, bitrate
neotune.set_audio("pulseaudio", "default", "320")
```

**Bitrates**: "96", "160", "320" (Requires Spotify Premium).

## Custom Commands (`commands.lua`)

Register command aliases that can be typed directly into the command bar (`:`):

```lua
-- lua/commands.lua
neotune.command("logout", "logout", "Logout and clear all sessions")
neotune.command("next", "next_track", "Skip to next track")
```

## Theme Configuration (`theme.lua`)

Customize the visual appearance of NeoTune:

```lua
-- lua/theme.lua

-- Set the theme
neotune.set_theme("catppuccin")

-- Define custom theme variables
neotune.set_theme("custom", {
    primary = "#89b4fa",
    accent = "#f38ba8",
    background = "#1e1e2e",
    surface = "#313244",
    panel = "#45475a",
    success = "#a6e3a1",
    warning = "#fab387",
    error = "#f38ba8",
    text = "#cdd6f4",
    text_muted = "#6c7086",
    text_accent = "#89b4fa"
})
```

### Built-in Themes

- `default` - NeoTune default theme
- `catppuccin` - Catppuccin color scheme
- `gruvbox` - Gruvbox dark theme
- `tokyonight` - Tokyo Night theme
- `nord` - Nord color palette

## Special Playlists (`special_playlists.lua`)

Define custom playlists that appear in your sidebar:

```lua
-- lua/special_playlists.lua

-- Register a custom playlist
neotune.special_playlists.register({
    name = "My Favorites",
    uri = "spotify:playlist:your-playlist-id",
    icon = "❤️"
})

-- Register multiple playlists
local my_playlists = {
    { name = "Workout Mix", uri = "spotify:playlist:id1", icon = "💪" },
    { name = "Chill Vibes", uri = "spotify:playlist:id2", icon = "🌊" },
    { name = "Focus Mode", uri = "spotify:playlist:id3", icon = "🎯" }
}

for _, playlist in ipairs(my_playlists) do
    neotune.special_playlists.register(playlist)
end
```

## Advanced Configuration

### Complete Example (`init.lua`)

```lua
-- lua/init.lua - Complete user configuration

-- Global Settings
neotune.set_leader("space")              -- Set leader key
neotune.set_which_key(true)              -- Show WhichKey popup
neotune.set_auto_play(true)              -- Auto-play on startup
neotune.set_auto_select_device(true)     -- Auto-select local device

-- Load configuration modules
require("theme")      -- Theme settings
require("keymaps")    -- Keybindings
require("audio")      -- Audio configuration
require("commands")   -- Custom commands
require("special_playlists")  -- Custom playlists

-- Debug configuration (optional)
neotune.set_debug({
    enabled = true,
    log_level = "info",
    log_to_file = true,
    log_file_path = "~/.config/neotune/debug.log"
})
```

### Environment Variables

You can also configure NeoTune using environment variables:

```bash
# Set config directory
export NEOTUNE_CONFIG_DIR="~/.config/neotune"

# Set cache directory
export NEOTUNE_CACHE_DIR="~/.cache/neotune"

# Enable debug logging
export NEOTUNE_DEBUG=1
```

## Troubleshooting

### Configuration Not Loading

1. Check that `~/.config/neotune/init.lua` exists
2. Verify Lua syntax is correct
3. Check logs in `~/.cache/neotune/librespot.log`

### Keybindings Not Working

1. Ensure `neotune.set_leader()` is called before mappings
2. Check for conflicting key definitions
3. Restart the application after config changes

### Audio Issues

1. Verify backend is available: `pactl info` (for PulseAudio)
2. Check available backends in librespot log
3. Try different backend: `neotune.set_audio("rodio", "default", "320")`

### Getting Help

- Check the debug logs: Press `space` + `l` in the app
- View logs: `~/.cache/neotune/librespot.log`
- Open an issue on GitHub with logs attached

# Lua Configuration Guide

NeoTune leverages Lua for its configuration system, allowing users to define their own keybindings, themes, and audio settings in a format that should feel very familiar to Neovim users.

## Config Directory Structure

By default, the application looks for configuration files in the `lua/` directory:

```bash
lua/
├── init.lua      # Entry point
├── keymaps.lua   # Keybindings and leader mappings
├── theme.lua     # User-defined UI themes
├── audio.lua     # Bitrate and playback backend setup
└── commands.lua  # Custom command aliases
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
- `toggle_shuffle`: Toggle playback shuffle
- `cycle_repeat`: Cycle through repeat modes
- `toggle_sidebar`: Toggle the visibility of the sidebar
- `theme_selector`: Open the visual theme selector
- `command_prompt`: Open the command bar (`:`)
- `search_prompt`: Open the Telescope search bar (`/`)
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

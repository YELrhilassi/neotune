# Lua Configuration Guide

Spotify TUI leverages Lua for its configuration system, allowing users to define their own keybindings, themes, and audio settings in a format that should feel very familiar to Neovim users.

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
require("theme")
require("keymaps")
require("audio")
require("commands")
```

## Keybindings (`keymaps.lua`)

The application uses a "leader" system similar to Neovim. You first press a leader key (like `space`), followed by an action key.

### Setting the Leader Key

```lua
-- lua/keymaps.lua
spotify_tui.set_leader("space") -- Use a string key name
```

### Mapping Actions

You can map specific actions to keys using `spotify_tui.map(key, action, description)`:

```lua
-- lua/keymaps.lua
spotify_tui.map("p", "play_pause", "Play / Pause")
spotify_tui.map("n", "next_track", "Next Track")
spotify_tui.map("b", "prev_track", "Previous Track")
spotify_tui.map("x", "toggle_shuffle", "Toggle Shuffle")
```

The third argument (`description`) is used in the **WhichKey** popup to help you discover your mappings.

### Navigation Keys

You can customize the global navigation keys used to traverse lists and panels:

```lua
-- lua/keymaps.lua
-- Parameters: up, down, left, right, page_up, page_down
spotify_tui.set_nav("k", "j", "h", "l", "U", "D")
```

## Audio Configuration (`audio.lua`)

Control the quality and backend of your high-quality DRM playback.

```lua
-- lua/audio.lua
-- Parameters: backend, device, bitrate
spotify_tui.set_audio("pulseaudio", "default", "320")
```

**Bitrates**: "96", "160", "320" (Requires Spotify Premium).

## Themes (`theme.lua`)

Set your preferred UI theme:

```lua
-- lua/theme.lua
spotify_tui.set_theme("catppuccin")
```

Themes are defined in `styles/main.tcss`, and the `set_theme()` function helps the application select the appropriate classes to apply.

## Custom Commands (`commands.lua`)

Register command aliases that can be typed directly into the command bar (`:`):

```lua
-- lua/commands.lua
spotify_tui.command("vol+", "volume_up", "Increase volume")
spotify_tui.command("vol-", "volume_down", "Decrease volume")
```

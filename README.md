# Spotify TUI

A sleek, Neovim-inspired Spotify client for the terminal, built with Python and [Textual](https://textual.textualize.io/). 

## Gallery

| Main Player Interface | Telescope Search (Multi-modal) |
| --- | --- |
| ![Main UI](https://via.placeholder.com/400x250?text=Main+Player+UI) | ![Telescope Search](https://via.placeholder.com/400x250?text=Telescope+Search+Tabs) |
| *Sleek dashboard with Neovim status bar* | *Search with categorized preview panels* |

| Onboarding Setup | WhichKey Discovery |
| --- | --- |
| ![Setup Wizard](https://via.placeholder.com/400x250?text=Minimal+Setup+Wizard) | ![WhichKey Popup](https://via.placeholder.com/400x250?text=WhichKey+Popup) |
| *Terminal-silent configuration flow* | *Context-aware command suggestions* |

## Features

- **Neovim-style Workflow**: Uses a leader key (default: `space`) for actions, featuring `NORMAL`, `LEADER`, and `SEARCH` modes.
- **Interactive Setup**: No need for manual `.env` configuration. The app guides you through an internal setup and authorization wizard on your first launch.
- **Advanced Telescope Search**: A powerful, multi-modal search interface for Songs, Albums, and Playlists with interactive previews and direct playback.
- **Lua Configuration**: Fully customizable through Lua scripts. Define your own keymaps, themes, and commands.
- **WhichKey Popup**: A discoverable keybinding menu that adapts to your current context.
- **High-Quality DRM Playback**: Integrated `spotifyd` daemon support for premium 320kbps audio.
- **Minimalist Aesthetic**: Fast, modern flat terminal interface with full mouse support and customizable Catppuccin-based themes.

## Installation

### Prerequisites

- Python 3.10+
- A Spotify Premium account (required for DRM playback via the daemon)
- System clipboard tool (`xclip`, `wl-copy`, or `pbcopy`) for easy authorization.

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/spotify-tui.git
   cd spotify-tui
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Launch the application:
   ```bash
   python app.py
   ```
   On first launch, the app will guide you through the **Setup Wizard**. You will need your Spotify API [Client ID and Secret](https://developer.spotify.com/dashboard).

## Usage

### Modes
- **NORMAL**: Default mode for navigation.
- **LEADER**: Triggered by `space`. Waiting for a command.
- **SEARCH**: Active during Telescope search. Includes its own `INSERT` mode for typing.

### Keybindings

| Key | Action |
| --- | --- |
| `space` | **Leader Key** - Opens the action menu |
| `space` `space` | Open **Telescope Search** |
| `j` / `k` | Navigate down / up |
| `h` / `l` | Navigate between panels (Sidebar/Results/Preview) |
| `H` / `L` | Switch Category Tabs (in Telescope) |
| `i` / `a` | Enter **Insert Mode** in search bars |
| `enter` | Select / Play track |
| `esc` | Return to Normal mode / Close modals |

### Leader Actions (`space` + Key)

- `p`: Play / Pause
- `n`: Next track
- `b`: Previous track
- `t`: Theme selector
- `e`: Toggle sidebar
- `Q`: Logout (Wipe session and credentials)
- `:`: Open command prompt

## Configuration

The application is configured using Lua in the `lua/` directory.

- `lua/init.lua`: Main entry point (enable auto-play, set themes).
- `lua/keymaps.lua`: Define custom leader mappings and navigation keys.
- `lua/theme.lua`: Customize UI colors.

See [Configuration Documentation](docs/configuration.md) for full details.

## License

MIT

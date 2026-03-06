# Spotify TUI

A sleek, Neovim-inspired Spotify client for the terminal, built with Python and [Textual](https://textual.textualize.io/). 

![Spotify TUI Screenshot](https://via.placeholder.com/800x450?text=Spotify+TUI+Screenshot)

## Features

- **Neovim-style Workflow**: Uses a leader key (default: `space`) for actions, just like your favorite editor.
- **Lua Configuration**: Fully customizable through Lua scripts. Define your own keymaps, themes, and commands.
- **WhichKey Popup**: A discoverable keybinding menu that helps you find your mappings on the fly.
- **High-Quality DRM Playback**: Integrated `spotifyd` daemon support for 320kbps audio.
- **Responsive UI**: Fast, modern terminal interface with full mouse support and customizable themes.

## Installation

### Prerequisites

- Python 3.10+
- A Spotify Premium account (required for DRM playback via the daemon)
- `spotifyd` binary (included in `src/network/` or installable separately)

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
   The app will automatically guide you through the setup process on your first launch. You will need your Spotify API [Client ID and Secret](https://developer.spotify.com/dashboard).

## Usage

Start the application:
```bash
python app.py
```

### Keybindings

| Key | Action |
| --- | --- |
| `space` | **Leader Key** - Opens the action menu |
| `j` / `k` | Navigate down / up |
| `h` / `l` | Navigate between panels |
| `enter` | Select / Play track |
| `esc` | Close modals / Cancel leader mode |

### Leader Actions

After pressing `space`, you can use the following:
- `p`: Play / Pause
- `n`: Next track
- `b`: Previous track
- `t`: Theme selector
- `e`: Toggle sidebar
- `:`: Open command prompt

## Configuration

The application is configured using Lua. Files are located in the `lua/` directory:

- `lua/init.lua`: Main entry point.
- `lua/keymaps.lua`: Define your leader mappings and navigation keys.
- `lua/theme.lua`: Customize colors and UI styles.
- `lua/audio.lua`: Configure playback backends and bitrates.

See [Configuration Documentation](docs/configuration.md) for more details.

## License

MIT

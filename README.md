# Spotify TUI

A sleek, Neovim-inspired Spotify client for the terminal, built with Python and [Textual](https://textual.textualize.io/). 

## Features

- **Neovim-style Workflow**: Uses a leader key (default: `space`) for actions, featuring `NORMAL`, `LEADER`, and `SEARCH` modes.
- **Improved Browser Setup**: No more copy-pasting redirect URLs. Launch the app, visit `http://127.0.0.1:8080`, and the app handles the rest.
- **Direct Playback**: Built-in `librespot` support. The app automatically compiles and manages its own playback engine.
- **Advanced Telescope Search**: A powerful search interface for Tracks, Albums, and Playlists with interactive previews.
- **Lua Configuration**: Fully customizable through Lua scripts. Define your own keymaps and themes.

## Installation

### Prerequisites

- Python 3.10+
- Rust (only if you need to recompile the player from `librespot_src`)
- A Spotify Premium account

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/spotify-tui.git
   cd spotify-tui
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Launch the application:
   ```bash
   python app.py
   ```
   On first launch, the TUI will ask you to visit `http://127.0.0.1:8080` in your browser to complete the setup wizard.

## Usage

### Modes
- **NORMAL**: Default mode for navigation.
- **LEADER**: Triggered by `space`. Waiting for a command.
- **SEARCH**: Active during Telescope search.

### Keybindings

| Key | Action |
| --- | --- |
| `space` | **Leader Key** - Opens the action menu |
| `j` / `k` | Navigate down / up |
| `h` / `l` | Navigate between panels |
| `enter` | Select / Play track |
| `esc` | Return to Normal mode |

### Leader Actions (`space` + Key)

- `p`: Play / Pause
- `n`: Next track
- `b`: Previous track
- `t`: Theme selector
- `Q`: Logout (Wipe session and credentials)
- `:`: Open command prompt

## Configuration

The application is configured using Lua in the `lua/` directory. See [Configuration Documentation](docs/configuration.md) for full details.

## License

MIT

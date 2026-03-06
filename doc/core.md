# Core Architecture & State Management

## Overview
This document serves as the core reference for the Python-based Spotify TUI application architecture. It replaces the legacy Rust `spotify-tui` documentation, mapping its concepts to our Python/Textual implementation.

## 1. Application State (`src/state/app_state.py`)
- Acts as the single source of truth (`ApplicationState` class).
- Stores all dynamic data: user configs, playback context, library data, search results, and navigation history.
- Dispatches requests to the Network Layer and updates internal state without blocking the UI.

## 2. Network Layer (`src/network/spotify_network.py`)
- Wraps `spotipy` to handle all API communications.
- Manages authentication (OAuth2) and token refreshes.
- Performs asynchronous fetching and updates shared state safely.

## 3. Configuration & Auth (`src/config/`)
- `ClientConfiguration`: Manages `SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET`, and `SPOTIPY_REDIRECT_URI`.
- `UserPreferences`: Loads user-specific settings (themes, keybinds) from YAML/JSON.

## 4. Event Processing (`src/events/`)
- Intercepts raw inputs and normalizes them into standard actions (e.g., play, pause, next).
- Textual's native `Bindings` and `set_interval` handle the event loop and periodic "tick" updates for UI refresh.

## 5. UI Rendering (`src/ui/`)
- Built with `Textual`.
- Uses layout containers (`Horizontal`, `Vertical`) and widgets (`DataTable`, `ListView`, `Label`).
- Dynamically reflects `ApplicationState`.
- CSS is extracted to `styles/main.tcss`.

## 6. CLI (`src/cli/`)
- Built with `click` or `argparse`.
- Uses the `SpotifyNetwork` directly for headless execution (e.g., `python cli.py play --next`).

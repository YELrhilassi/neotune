# Core Architecture & State Management

## Overview

The Spotify TUI application is built around a centralized state and a reactive UI architecture. It aims to decouple the user interface from the complexities of the Spotify API and background playback daemons.

## 1. The Central Store (`src/state/store.py`)

The application uses a simple, centralized key-value store for shared state.

- **Purpose**: Acts as the single source of truth for the entire TUI.
- **Data Flow**: When data is fetched from the network, it is stored in the `Store`. UI components observe or query this store to update their display.
- **Managed Data**:
  - Current playback status (active track, progress, volume).
  - User library data (playlists, saved albums, recently played).
  - UI state (active view, search queries, notifications).

## 2. Network Interaction (`src/network/spotify_network.py`)

This layer encapsulates all communication with external services.

- **Spotify API**: Wraps `spotipy` for all web-based API calls (e.g., fetching tracks, searching).
- **Authentication**: Manages the OAuth2 flow, token caching, and automated refreshes.
- **Non-blocking**: API calls are handled safely so that intermittent network delays do not freeze the main UI loop.

## 3. Playback Daemon (`src/network/local_player.py`)

Unlike many other clients, Spotify TUI includes an integrated DRM playback daemon.

- **High Fidelity**: Leverages a `spotifyd` binary to support up to 320kbps audio.
- **Local Control**: Automatically starts, authenticates, and stops the daemon based on application lifecycle.
- **Integration**: The TUI communicates with the daemon via the Spotify Connect API, allowing for a seamless transition between local and remote playback.

## 4. Lua Configuration Bridge (`src/config/user_prefs.py`)

Configurations are not static but are evaluated at runtime using Lua.

- **`lupa` Integration**: Embeds a Lua runtime into the Python process.
- **Bridged API**: Exposes a `spotify_tui` global in Lua that allows users to register keymaps and settings that are instantly reflected in the Python state.

## 5. UI Rendering System (`src/ui/`)

The interface is built using the Textual framework.

- **Layouts**: Defined in `terminal_renderer.py`, partitioning the terminal into logical regions (Now Playing, Sidebar, Main Content, Status Bar).
- **Styling**: All visual appearance (colors, borders, spacing) is managed through `styles/main.tcss`.
- **Modals**: A dedicated modal system (`src/ui/modals/`) handles popups for device selection, audio configuration, and the WhichKey discovery tool.

## 6. Dependency Injection (`src/core/di.py`)

A minimal DI container simplifies the management of singletons across the application.

- **Decoupling**: Classes resolve their dependencies (like the `Store` or `SpotifyNetwork`) via the container rather than hard-coding imports or constructor arguments.
- **Testability**: Facilitates mocking or swapping out services for testing purposes.

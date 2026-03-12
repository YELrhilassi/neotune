# NeoTune Architecture Plan

This document outlines the high-level architecture for refactoring the NeoTune application into a robust, maintainable, and feature-rich system.

## 1. Application State Manager (`ApplicationState`)
- **Role:** The central source of truth for the application's current condition.
- **Responsibilities:**
  - Store dynamic data: current track, active device, loaded playlists, search results, and navigation history.
  - Coordinate with the Network Layer to fetch/update data from Spotify based on user actions.
  - Manage the UI navigation flow, allowing seamless transitions between views (e.g., playlists -> tracks -> artist info).

## 2. Network Interaction Layer (`SpotifyNetwork`)
- **Role:** Handles all communication with the external Spotify API.
- **Responsibilities:**
  - Abstract API calls (using `spotipy` under the hood).
  - Manage OAuth2 authentication, including token retrieval, caching, and automatic refreshing.
  - Perform actions like controlling playback (play, pause, skip, seek), querying the user's library, and searching.
  - Ensure API calls are non-blocking to keep the UI responsive, utilizing asynchronous operations where possible.

## 3. Configuration & User Authentication (`ClientConfiguration`, `UserPreferences`)
- **Role:** Manages application settings and local state.
- **Responsibilities:**
  - Load/save API credentials (Client ID, Secret, Redirect URI) and user preferences (keybinds, themes) from local YAML/JSON config files.
  - Facilitate the initial setup process if credentials are not found, potentially via an interactive terminal prompt.
  - Handle the localized web server callback for the OAuth2 authorization code grant flow.

## 4. Event Handling System (`EventProcessor`)
- **Role:** Manages internal timers and external user inputs.
- **Responsibilities:**
  - Intercept and normalize keyboard inputs into an internal action format (e.g., mapping 'space' to `Action.PLAY_PAUSE`).
  - Dispatch periodic "tick" events to trigger regular state updates (like refreshing the current playback position or polling the active device).
  - Decouple the UI rendering loop from raw input processing.

## 5. UI Rendering (`TerminalRenderer`)
- **Role:** Translates the application state into the visual terminal interface.
- **Responsibilities:**
  - Define the layout structure (Header, Sidebar, Main Content, Playback Footer).
  - Dynamically render lists, tables, and text based on the `ApplicationState`.
  - Apply user-defined color themes and adapt seamlessly to terminal resizing.
  - Provide visual feedback for selected items or active playback states.

## 6. Command Line Interface (CLI) (`CommandLineInterface`)
- **Role:** Exposes direct Spotify controls without launching the interactive TUI.
- **Responsibilities:**
  - Parse arguments (e.g., `app.py playback --next`).
  - Interface directly with the `SpotifyNetwork` layer to execute the command.
  - Output formatted text responses back to the terminal.

## Implementation Roadmap
1. Initialize structure and dependencies (`spotipy`, `pyyaml`, `textual`, `click`/`argparse`).
2. Implement Config classes and the Auth setup flow.
3. Build the Network Layer for robust Spotify communication.
4. Establish the central State Manager.
5. Create the Event system to handle normalized inputs and timers.
6. Assemble the Textual TUI to render the State.
7. Wrap the core functionality with a dedicated CLI argument parser.
8. Wire everything together and perform end-to-end testing.

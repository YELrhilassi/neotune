# Core Architecture & State Management

## Overview

The NeoTune application is built around a centralized state, a reactive UI architecture, and a modular logic layer driven by custom hooks. It decouples the user interface from the complexities of the Spotify API and background playback daemons.

## 1. Modular Logic Layer (Hooks)

Application logic is organized into focused, reusable **Hooks** in `src/hooks/`. This follows a functional approach, separating business logic from UI components.

- **`useSpotifySearch`**: Handles multi-category search and data normalization.
- **`usePlayTrack`**: Intelligently handles playback for Tracks, Albums, and Playlists using appropriate Spotify API parameters.
- **`useLogout`**: Manages the secure wiping of session tokens, daemon caches, and user credentials.
- **`useEnsureActiveDevice`**: Automates the detection and activation of playback devices on startup.

## 2. Centralized State Store (`src/state/store.py`)

A simple key-value store serves as the single source of truth.

- **Data Flow**: Hooks fetch and process data, then update the `Store`.
- **Reactivity**: UI components observe the `Store` (or are updated by the main loop) to reflect changes in playback, library data, or authentication status.

## 3. Composable UI Components (`src/ui/`)

The interface uses the Textual framework with a heavy emphasis on composition.

- **Telescope Architecture**: The search interface is broken into sub-components (`Header`, `Tabs`, `Results`, `Preview`) located in `src/ui/modals/telescope/`.
- **Status Bar**: A Neovim-inspired status line that dynamically reflects the current `NORMAL`, `LEADER`, or `SEARCH` mode.
- **Modals**: Specialized screens for authentication, device selection, and action confirmations.

## 4. Onboarding & Security

The app handles sensitive data through an integrated wizard.

- **Setup Wizard**: An internal UI flow that collects API credentials and secures them in `~/.config/neotune/client.yml` with `600` permissions.
- **Authorization Flow**: A "terminal-silent" process that manages Spotify OAuth entirely within the TUI and the user's browser.

## 5. Playback Daemon (`src/network/local_player.py`)

Integrates the `librespot` binary for high-quality playback.

- **Lifecycle Management**: Automatically started and stopped by the TUI.
- **Credential Hand-off**: Securely passes auth tokens to the daemon for a seamless "connect" experience.

## 6. Dependency Injection (`src/core/di.py`)

A minimal DI container simplifies singleton management (Network, Store, Prefs) across hooks and components, facilitating testability and clean imports.

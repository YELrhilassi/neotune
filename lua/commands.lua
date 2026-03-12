-- lua/commands.lua
-- Command Palette configurations

neotune.command("q", "quit", "Quit the application")
neotune.command("quit", "quit", "Quit the application")
neotune.command("exit", "quit", "Quit the application")

neotune.command("next", "next_track", "Skip to next track")
neotune.command("prev", "prev_track", "Go to previous track")
neotune.command("shuffle", "toggle_shuffle", "Toggle shuffle state")
neotune.command("repeat", "cycle_repeat", "Cycle repeat state")

neotune.command("logout", "logout", "Logout and clear all sessions")
neotune.command("health", "health", "Run system diagnostics")
neotune.command("theme", "theme_selector", "Open Theme Selector")

-- lua/commands.lua
-- Command Palette configurations

spotify_tui.command("q", "quit", "Quit the application")
spotify_tui.command("quit", "quit", "Quit the application")
spotify_tui.command("exit", "quit", "Quit the application")

spotify_tui.command("next", "next_track", "Skip to next track")
spotify_tui.command("prev", "prev_track", "Go to previous track")
spotify_tui.command("shuffle", "toggle_shuffle", "Toggle shuffle state")
spotify_tui.command("repeat", "cycle_repeat", "Cycle repeat state")

spotify_tui.command("theme", "theme_selector", "Open Theme Selector")

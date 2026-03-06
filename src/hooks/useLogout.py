import os
import shutil
from pathlib import Path
from src.core.di import Container
from src.network.local_player import LocalPlayer
from src.network.spotify_network import SpotifyNetwork

def useLogout(app):
    """
    Performs a full logout: stops the local player, cleans up caches, 
    and removes stored credentials.
    """
    try:
        # 1. Stop and cleanup local player
        player = Container.resolve(LocalPlayer)
        if player:
            player.stop()
            
        # 2. Clear spotifyd cache directory
        daemon_cache = Path.home() / ".cache" / "spotify_tui_daemon"
        if daemon_cache.exists():
            shutil.rmtree(daemon_cache)
            
        # 3. Clear spotipy token cache (local .cache file)
        # By default spotipy uses '.cache' in the current working directory
        token_cache = Path(".cache")
        if token_cache.exists():
            token_cache.unlink()
            
        # 4. Remove stored client credentials
        config_file = Path.home() / ".config" / "spotify-tui" / "client.yml"
        if config_file.exists():
            config_file.unlink()
            
        app.notify("Logged out successfully. Restart the app to re-configure.", severity="information")
        
        # 5. Exit the application
        app.exit()
        
    except Exception as e:
        app.notify(f"Logout failed: {e}", severity="error")

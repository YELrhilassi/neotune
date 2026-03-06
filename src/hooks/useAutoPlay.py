from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork
from src.config.user_prefs import UserPreferences

def useAutoPlay(app):
    """
    Triggers playback if auto_play is enabled in user preferences.
    """
    prefs = Container.resolve(UserPreferences)
    if not prefs.auto_play:
        return
        
    network = Container.resolve(SpotifyNetwork)
    try:
        playback = network.get_current_playback()
        # Only start if not already playing
        if not playback or not playback.get('is_playing'):
            network.toggle_play_pause()
            app.notify("Auto-playing...")
    except Exception:
        pass

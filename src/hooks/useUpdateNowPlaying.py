import time
from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork
from src.state.store import Store

# Local cache for last update time to prevent rapid-fire polling
_last_update_time = 0
_update_interval = 2.0  # Minimum seconds between API calls


def useUpdateNowPlaying(app, force=False):
    """
    Updates the 'Now Playing' information from the Spotify API with rate limiting.
    """
    global _last_update_time, _update_interval

    current_time = time.time()
    if not force and (current_time - _last_update_time < _update_interval):
        return

    try:
        network = Container.resolve(SpotifyNetwork)
        store = Container.resolve(Store)

        # Mark update attempted
        _last_update_time = current_time

        playback = network.get_current_playback()
        store.set("current_playback", playback)

        # Adjust next interval based on playback state
        if not playback or not playback.get("is_playing"):
            _update_interval = 5.0
        else:
            _update_interval = 2.0

    except Exception:
        pass

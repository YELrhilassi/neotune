from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork
from src.state.store import Store

def useUpdateNowPlaying(app):
    """
    Updates the 'Now Playing' information from the Spotify API.
    """
    try:
        network = Container.resolve(SpotifyNetwork)
        store = Container.resolve(Store)
        playback = network.get_current_playback()
        store.set("current_playback", playback)
    except Exception:
        pass

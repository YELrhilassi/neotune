from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork
from src.state.store import Store

def useRefreshData(app):
    """
    Refreshes playlist and library data from the Spotify API.
    """
    try:
        network = Container.resolve(SpotifyNetwork)
        store = Container.resolve(Store)
        store.set("playlists", network.get_playlists())
        store.set("featured_playlists", network.get_featured_playlists())
        store.set("recently_played", network.get_recently_played())
    except Exception as e:
        app.notify(f"Spotify API Error: {e}", severity="error")

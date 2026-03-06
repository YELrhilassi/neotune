from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork

def useFetchAlbumTracks(album_id: str):
    """
    Fetches the list of tracks for a given Spotify album ID.
    """
    network = Container.resolve(SpotifyNetwork)
    try:
        return network.get_album_tracks(album_id)
    except Exception:
        return []

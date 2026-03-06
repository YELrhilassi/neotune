from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork

def useFetchPlaylistTracks(playlist_id: str):
    """
    Fetches the list of tracks for a given Spotify playlist ID.
    """
    network = Container.resolve(SpotifyNetwork)
    try:
        items = network.get_playlist_tracks(playlist_id)
        # Playlist items are nested: {'track': {...}, 'added_at': ...}
        return [item['track'] for item in items if item.get('track')]
    except Exception:
        return []

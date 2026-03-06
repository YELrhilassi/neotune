from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork

def useRemoveTrack(track_uri: str, app):
    """
    Removes a track from the user's Liked Songs.
    """
    network = Container.resolve(SpotifyNetwork)
    try:
        track_id = track_uri.split(":")[-1]
        network.sp.current_user_saved_tracks_delete([track_id])
        app.notify("Removed from Liked Songs")
        return True
    except Exception as e:
        app.notify(f"Failed to remove track: {e}", severity="error")
        return False

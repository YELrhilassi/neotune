from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork

def useSaveTrack(track_uri: str, app):
    """
    Saves a track to the user's Liked Songs.
    """
    network = Container.resolve(SpotifyNetwork)
    try:
        track_id = track_uri.split(":")[-1]
        network.sp.current_user_saved_tracks_add([track_id])
        app.notify("Saved to Liked Songs")
        return True
    except Exception as e:
        app.notify(f"Failed to save track: {e}", severity="error")
        return False

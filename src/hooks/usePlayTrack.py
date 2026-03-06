from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork
from src.hooks.useGetActiveDevice import useGetActiveDevice

def usePlayTrack(uri: str, app):
    """
    Plays a track, album, or playlist on the active device.
    """
    network = Container.resolve(SpotifyNetwork)
    target_device_id = useGetActiveDevice()
    
    if not target_device_id:
        app.notify("No active Spotify devices!", severity="error")
        return False
        
    try:
        network.play_track(uri, device_id=target_device_id)
        app.notify("Playback started...")
        return True
    except Exception as e:
        app.notify(f"Playback error: {e}", severity="error")
        return False

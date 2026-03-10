from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork
from src.hooks.useGetActiveDevice import useGetActiveDevice

def usePlayTrack(uri: str | list, app, context_uri: str = None, offset_position: int = None):
    """
    Plays a track, album, or playlist on the active device.
    If uri is a list of track uris, they will all be queued.
    If context_uri is provided, it starts playback of the specific track within the context.
    """
    network = Container.resolve(SpotifyNetwork)
    target_device_id = useGetActiveDevice()
    
    if not target_device_id:
        app.notify("No active Spotify devices!", severity="error")
        return False
        
    try:
        network.play_track(uri, device_id=target_device_id, context_uri=context_uri, offset_position=offset_position)
        app.notify("Playback started...")
        return True
    except Exception as e:
        app.notify(f"Playback error: {e}", severity="error")
        return False

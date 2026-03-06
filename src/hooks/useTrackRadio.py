from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork
from src.hooks.useGetActiveDevice import useGetActiveDevice

def useTrackRadio(track_uri: str, app):
    """
    Starts a radio based on the given track URI.
    """
    network = Container.resolve(SpotifyNetwork)
    try:
        track_id = track_uri.split(":")[-1]
        res = network.sp.recommendations(seed_tracks=[track_id], limit=50)
        if not res or 'tracks' not in res or not res['tracks']:
            app.notify("No radio tracks found.", severity="warning")
            return False
            
        uris = [t['uri'] for t in res['tracks']]
        
        target_device_id = useGetActiveDevice()
        if target_device_id and uris:
            network.sp.start_playback(device_id=target_device_id, uris=uris)
            app.notify("Started Track Radio...")
            return True
        else:
            app.notify("No active Spotify devices!", severity="error")
    except Exception as e:
        app.notify(f"Failed to start radio: {repr(e)}", severity="error")
    return False

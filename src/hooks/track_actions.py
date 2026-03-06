from src.core.di import Container
from src.state.store import Store
from src.network.spotify_network import SpotifyNetwork

def _get_target_device_id():
    store = Container.resolve(Store)
    network = Container.resolve(SpotifyNetwork)
    
    try:
        devices_data = network.get_devices()
    except Exception:
        return None
        
    if not devices_data or not devices_data.get('devices'):
        return None
        
    devices = devices_data['devices']
    target_device_id = store.get("preferred_device_id")
    
    if not target_device_id:
        for device in devices:
            if device['name'] == "Spotify TUI Player":
                target_device_id = device['id']
                store.set("preferred_device_id", target_device_id)
                break
    
    if not target_device_id:
        for device in devices:
            if device['is_active']:
                target_device_id = device['id']
                break
                
    if not target_device_id and devices:
        target_device_id = devices[0]['id']
        
    return target_device_id

def play_track(track_uri: str, app):
    network = Container.resolve(SpotifyNetwork)
    target_device_id = _get_target_device_id()
    
    if not target_device_id:
        app.notify("No active Spotify devices!", severity="error")
        return False
        
    try:
        network.play_track(track_uri, device_id=target_device_id)
        app.notify("Playback started...")
        return True
    except Exception as e:
        app.notify(f"Playback error: {e}", severity="error")
        return False

def start_track_radio(track_uri: str, app):
    network = Container.resolve(SpotifyNetwork)
    try:
        track_id = track_uri.split(":")[-1]
        res = network.sp.recommendations(seed_tracks=[track_id], limit=50)
        if not res or 'tracks' not in res or not res['tracks']:
            app.notify("No radio tracks found.", severity="warning")
            return False
            
        uris = [t['uri'] for t in res['tracks']]
        
        target_device_id = _get_target_device_id()
        if target_device_id and uris:
            network.sp.start_playback(device_id=target_device_id, uris=uris)
            app.notify("Started Track Radio...")
            return True
        else:
            app.notify("No active Spotify devices!", severity="error")
    except Exception as e:
        app.notify(f"Failed to start radio: {repr(e)}", severity="error")
    return False

def save_track(track_uri: str, app):
    network = Container.resolve(SpotifyNetwork)
    try:
        track_id = track_uri.split(":")[-1]
        network.sp.current_user_saved_tracks_add([track_id])
        app.notify("Saved to Liked Songs")
        return True
    except Exception as e:
        app.notify(f"Failed to save track: {e}", severity="error")
        return False

def remove_saved_track(track_uri: str, app):
    network = Container.resolve(SpotifyNetwork)
    try:
        track_id = track_uri.split(":")[-1]
        network.sp.current_user_saved_tracks_delete([track_id])
        app.notify("Removed from Liked Songs")
        return True
    except Exception as e:
        app.notify(f"Failed to remove track: {e}", severity="error")
        return False

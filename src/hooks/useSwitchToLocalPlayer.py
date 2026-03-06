from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork
from src.state.store import Store

def useSwitchToLocalPlayer(app, force=False):
    """
    Switches playback to the local "Spotify TUI Player" or the first available device.
    """
    try:
        network = Container.resolve(SpotifyNetwork)
        store = Container.resolve(Store)
        devices_data = network.get_devices()
        
        if not devices_data or not devices_data.get('devices'):
            return
        
        is_active = any(d.get('is_active') for d in devices_data['devices'])
        if not force and is_active:
            return
            
        for device in devices_data['devices']:
            if device['name'] == "Spotify TUI Player":
                store.set("preferred_device_id", device['id'])
                store.set("preferred_device_name", device['name'])
                network.transfer_playback(device['id'], force_play=False)
                app.notify(f"Auto-switched to local output: {device['name']}")
                return

        if force and devices_data['devices']:
            first_device = devices_data['devices'][0]
            store.set("preferred_device_id", first_device['id'])
            store.set("preferred_device_name", first_device['name'])
            network.transfer_playback(first_device['id'], force_play=False)
            app.notify(f"Activated first available device: {first_device['name']}")
    except Exception:
        pass

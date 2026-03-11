"""Hook for updating currently playing track info."""

from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork
from src.state.store import Store


from src.state.feature_stores import PlaybackStore, DeviceStore, NetworkStore


def useUpdateNowPlaying(app, force=False):
    """
    Updates the 'Now Playing' information from the Spotify API.
    Rate limiting and locking are handled by the PlaybackService.
    """
    try:
        network = Container.resolve(SpotifyNetwork)
        store = Container.resolve(Store)
        playback_store = Container.resolve(PlaybackStore)
        device_store = Container.resolve(DeviceStore)
        network_store = Container.resolve(NetworkStore)

        # 1. Fetch playback state (debounced by service)
        # Note: PlaybackService now internally updates PlaybackStore and DeviceStore
        playback = network.get_current_playback(force=force)

        # 2. Update the legacy store for backward compatibility
        store.set("current_playback", playback)

        # 3. Periodically sync devices (even if nothing is playing)
        last_dev_sync = store.get("_last_device_sync") or 0
        import time

        now = time.time()

        if now - last_dev_sync > 10.0:
            devices_data = network.get_devices()
            devices = devices_data.get("devices", [])
            store.set("devices", devices)
            device_store.update(available=devices)
            store.set("_last_device_sync", now)

            # If nothing is playing, we can still try to find the active/preferred device in the list
            if not playback:
                active = next((d for d in devices if d.get("is_active")), None)
                if active:
                    device_store.update(preferred_name=active.get("name"))

    except Exception:
        # We rely on the base service dampening logic for api_connected status.
        pass

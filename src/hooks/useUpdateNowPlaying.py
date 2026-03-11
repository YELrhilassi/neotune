"""Hook for updating currently playing track info."""

from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork
from src.state.store import Store


def useUpdateNowPlaying(app, force=False):
    """
    Updates the 'Now Playing' information from the Spotify API.
    Rate limiting and locking are handled by the PlaybackService.
    """
    try:
        network = Container.resolve(SpotifyNetwork)
        store = Container.resolve(Store)

        # 1. Fetch playback state (debounced by service)
        playback = network.get_current_playback(force=force)
        
        # 2. Always update the store to handle transitions to/from None (nothing playing)
        current = store.get("current_playback")
        if current != playback:
            store.set("current_playback", playback)

        if playback is not None:
            # 3. Periodically sync devices too (every few heartbeats)

        # We'll use the store to track when we last did this
        last_dev_sync = store.get("_last_device_sync") or 0
        import time

        if time.time() - last_dev_sync > 10.0:
            devices = network.get_devices()
            store.set("devices", devices.get("devices", []))
            store.set("_last_device_sync", time.time())

    except Exception:
        store = Container.resolve(Store)
        store.set("api_connected", False)
        pass

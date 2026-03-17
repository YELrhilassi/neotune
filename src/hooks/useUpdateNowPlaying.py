"""Hook for updating currently playing track info."""

from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork
from src.state.store import Store


def useUpdateNowPlaying(app, force=False):
    """Updates the 'Now Playing' information from the Spotify API.
    Rate limiting and locking are handled by the PlaybackService.
    """
    try:
        network = Container.resolve(SpotifyNetwork)
        store = Store()  # Singleton

        # 1. Fetch playback state (debounced by service)
        # Note: PlaybackService now internally updates the store
        playback = network.get_current_playback(force=force)

        # 2. Update the store for backward compatibility
        store.set("current_playback", playback)

        # --- VIRTUAL QUEUE AUTO-SKIP CHECK ---
        if playback and playback.get("is_playing"):
            item = playback.get("item")
            if item:
                uri = item.get("uri")
                from src.state.virtual_queue import VirtualQueueManager
                vq = VirtualQueueManager()
                if uri and vq.is_skipped(uri):
                    # We are currently playing a track marked as skipped!
                    network.next_track()
                    # We unmark it so it doesn't get skipped if we try to play it manually again later?
                    # No, user wants it out of the queue. If it plays again later, it will be skipped again unless removed from skipped list.
                    # Wait, if we keep it in skipped list FOREVER, we can never play the track again.
                    # The skipped_uris is essentially a "Do Not Play" list.
                    # That is a bit aggressive. Maybe we should remove it from skipped list after we skip it?
                    # "skip when reached" -> usually means we discard it. Let's unmark it so they can play it later.
                    vq.unmark_skipped(uri)
                    return # Stop here, we will update on next poll
        # -------------------------------------


        # 3. Periodically sync devices (even if nothing is playing)
        last_dev_sync = store.get("_last_device_sync") or 0
        import time

        now = time.time()

        if now - last_dev_sync > 10.0:
            devices_data = network.get_devices()
            devices = devices_data.get("devices", [])
            store.update(devices=devices)
            store.set("_last_device_sync", now)

            # If nothing is playing, we can still try to find the active/preferred device in the list
            if not playback:
                active = next((d for d in devices if d.get("is_active")), None)
                if active:
                    store.set("preferred_device_name", active.get("name"))

    except Exception:
        # We rely on the base service dampening logic for api_connected status.
        pass

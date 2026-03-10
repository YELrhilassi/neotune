"""Hook for updating currently playing track info."""

from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork
from src.state.store import Store


def useUpdateNowPlaying(app, force=False):
    """
    Updates the 'Now Playing' information from the Spotify API.
    Rate limiting is managed by the PlaybackService.
    """
    try:
        network = Container.resolve(SpotifyNetwork)
        store = Container.resolve(Store)

        # This call is internally debounced by PlaybackService (TTL cache)
        playback = network.get_current_playback(force=force)

        if playback is not None:
            # Only update store if data actually changed to prevent reactive loops
            current = store.get("current_playback")
            if current != playback:
                store.set("current_playback", playback)

    except Exception:
        pass

from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork
from src.state.store import Store


def play_pause(app):
    """Toggle play/pause."""
    try:
        network = Container.resolve(SpotifyNetwork)
        network.toggle_play_pause()
        if app and hasattr(app, "update_now_playing"):
            import threading

            threading.Thread(target=lambda: app.update_now_playing(force=True), daemon=True).start()
    except Exception:
        pass


def next_track(app):
    """Skip to next track."""
    try:
        network = Container.resolve(SpotifyNetwork)
        network.next_track()
        if app and hasattr(app, "update_now_playing"):
            import threading

            threading.Thread(target=lambda: app.update_now_playing(force=True), daemon=True).start()
    except Exception:
        pass


def previous_track(app):
    """Go to previous track."""
    try:
        network = Container.resolve(SpotifyNetwork)
        network.prev_track()
        if app and hasattr(app, "update_now_playing"):
            import threading

            threading.Thread(target=lambda: app.update_now_playing(force=True), daemon=True).start()
    except Exception:
        pass


def toggle_shuffle(app):
    """Toggle shuffle state."""
    try:
        network = Container.resolve(SpotifyNetwork)
        network.toggle_shuffle()
        if app and hasattr(app, "update_now_playing"):
            import threading

            threading.Thread(target=lambda: app.update_now_playing(force=True), daemon=True).start()
    except Exception:
        pass


def cycle_repeat(app):
    """Cycle through repeat states: off -> context -> track -> off."""
    try:
        network = Container.resolve(SpotifyNetwork)
        network.cycle_repeat()
        if app and hasattr(app, "update_now_playing"):
            import threading

            threading.Thread(target=lambda: app.update_now_playing(force=True), daemon=True).start()
    except Exception:
        pass


def toggle_saved(track_uri: str, app):
    """Toggle saved state for a track."""
    try:
        network = Container.resolve(SpotifyNetwork)
        store = Store()
        playback = store.get("current_playback")

        if not playback or not playback.get("item"):
            return

        track_id = track_uri.split(":")[-1]

        # Check current state
        result = network.library.check_saved_tracks([track_id])
        is_saved = result[0] if result else False

        if is_saved:
            network.library.remove_saved_tracks([track_id])
        else:
            network.library.save_tracks([track_id])

    except Exception:
        pass

def add_to_queue(track_uri: str, app):
    """Add a track to the virtual and Spotify queue."""
    try:
        network = Container.resolve(SpotifyNetwork)
        # Call Spotify API
        network.add_to_queue(track_uri)
        # Also remove it from skipped uris if it was there
        from src.state.virtual_queue import VirtualQueueManager
        VirtualQueueManager().unmark_skipped(track_uri)

        if app and hasattr(app, "notify"):
            app.call_from_thread(app.notify, "Added to queue")
            
        # Refresh queue if visible
        store = Store()
        if store.get("queue_visible"):
            def _refresh_q():
                q = network.get_queue()
                store.set("queue", q)
            import threading
            threading.Thread(target=_refresh_q, daemon=True).start()
    except Exception:
        pass


def remove_from_queue(track_uri: str, app):
    """Mark a track as skipped in the virtual queue."""
    try:
        from src.state.virtual_queue import VirtualQueueManager
        VirtualQueueManager().mark_skipped(track_uri)

        if app and hasattr(app, "notify"):
            app.call_from_thread(app.notify, "Removed from queue")
        store = Store()
        if store.get("queue_visible"):
            def _refresh_q():
                network = Container.resolve(SpotifyNetwork)
                q = network.get_queue()
                store.set("queue", q)
            import threading
            threading.Thread(target=_refresh_q, daemon=True).start()
    except Exception:
        pass

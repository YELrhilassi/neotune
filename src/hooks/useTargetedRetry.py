from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork
from src.state.store import Store
from src.core.debug_logger import DebugLogger
import threading
import time
import random


def useTargetedRetry(app):
    """
    Intelligently retries only the missing pieces of data after a rate limit.
    Avoids a full app reload by targeting specific modules.
    Adds spacing and jitter between requests to avoid triggering new rate limits.
    """
    network = Container.resolve(SpotifyNetwork)
    store = Store()
    debug = DebugLogger()

    # 1. Check Sidebar (Playlists)
    missing_sidebar = not bool(store.get("playlists"))

    # 2. Check Discovery (Browse Metadata)
    missing_metadata = not bool(store.get("browse_metadata"))

    # 3. Check Track List (The currently active view)
    last_ctx = store.get("last_active_context")
    current_tracks = store.get("current_tracks") or []
    # If tracks is empty or just contains an "Empty" message
    missing_tracks = bool(last_ctx and (not current_tracks or len(current_tracks) <= 1))

    if not any([missing_sidebar, missing_metadata, missing_tracks]):
        return

    debug.info("Hooks", "Targeted retry triggered for missing data")

    # Set loading states
    current_loading = store.get("loading_states") or {}
    new_loading = {**current_loading}
    if missing_sidebar:
        new_loading["sidebar"] = True
    if missing_tracks:
        new_loading["track_list"] = True
    store.set("loading_states", new_loading)

    def _targeted_fetch():
        try:
            # Step 1: Sidebar
            if missing_sidebar:
                time.sleep(random.uniform(1.0, 3.0))  # Random jitter
                debug.debug("Hooks", "Retrying sidebar data fetch")
                playlists = network.get_playlists()
                if playlists:
                    app.call_from_thread(store.set, "playlists", playlists)

            # Step 2: Metadata
            if missing_metadata:
                time.sleep(random.uniform(2.0, 4.0))  # Space out from previous request
                debug.debug("Hooks", "Retrying browse metadata fetch")
                metadata = network.get_browse_metadata()
                if metadata:
                    app.call_from_thread(store.set, "browse_metadata", metadata)

            # Step 3: Track List
            if missing_tracks:
                time.sleep(random.uniform(2.0, 5.0))  # Space out heavily
                debug.debug("Hooks", f"Retrying tracks fetch for: {last_ctx}")
                tracks = []
                if last_ctx == "liked_songs":
                    tracks = network.get_liked_songs()
                elif last_ctx == "recently_played":
                    tracks = network.get_recently_played()
                    from src.core.activity_service import ActivityService

                    activity_svc = Container.resolve(ActivityService)
                    tracks = activity_svc.get_combined_history(tracks)
                else:
                    parts = last_ctx.split(":")
                    if len(parts) >= 3 and parts[1] == "playlist":
                        tracks = network.get_playlist_tracks(parts[2])

                if tracks:
                    if last_ctx.startswith("spotify:playlist:"):
                        app.call_from_thread(
                            store.set,
                            "pagination_state",
                            {
                                "type": "playlist",
                                "id": last_ctx.split(":")[2],
                                "offset": 50,
                                "limit": 50,
                                "has_more": len(tracks) == 50,
                                "loading": False,
                            },
                        )
                    else:
                        app.call_from_thread(store.set, "pagination_state", {})
                    app.call_from_thread(store.set, "current_tracks", tracks)

        except Exception as e:
            debug.error("Hooks", f"Targeted retry failed: {e}")
        finally:
            # Clear loading indicators
            app.call_from_thread(
                store.set, "loading_states", {"sidebar": False, "track_list": False, "app": False}
            )

    threading.Thread(target=_targeted_fetch, daemon=True).start()

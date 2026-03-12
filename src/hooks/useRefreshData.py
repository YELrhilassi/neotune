from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork
from src.state.store import Store
from src.core.debug_logger import DebugLogger
import threading
import time


def useRefreshData(app):
    """
    Refreshes all application data with precise loading state management.
    Ensures a single source of truth in the Store.
    """
    network = Container.resolve(SpotifyNetwork)
    store = Store()  # Singleton
    debug = DebugLogger()

    # Avoid concurrent refreshes
    if store.get("is_refreshing_data"):
        return

    store.set("is_refreshing_data", True)

    # Set loading only for pieces we don't have yet
    current_loading = store.get("loading_states") or {}
    new_loading = {**current_loading, "app": True}
    if not store.get("playlists"):
        new_loading["sidebar"] = True
    if not store.get("current_tracks"):
        new_loading["track_list"] = True

    store.set("loading_states", new_loading)
    debug.info("Hooks", "Starting full data refresh")

    def _background_refresh():
        try:
            # 1. User Profile
            profile = network.get_user_profile()
            if profile:
                app.call_from_thread(store.set, "user_profile", profile)

            # 2. User Playlists (Primary Source of Truth for Sidebar)
            playlists = network.get_playlists()
            if playlists:
                # This triggers _reactive_refresh in ContentTree
                app.call_from_thread(store.set, "playlists", playlists)

            # 3. Dynamic Browse Metadata (Discovery info)
            metadata = network.get_browse_metadata()
            if metadata and metadata.get("categories"):
                app.call_from_thread(store.set, "browse_metadata", metadata)

            # 4. History
            history = network.get_recently_played()
            if history:
                app.call_from_thread(store.set, "recently_played", history)

            # 5. Restore last context (Tracks list)
            last_ctx = store.get("last_active_context")
            if last_ctx:
                try:
                    tracks = []
                    if last_ctx == "liked_songs":
                        tracks = network.get_liked_songs()
                    elif last_ctx == "recently_played":
                        tracks = history if history else network.get_recently_played()
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
                except Exception:
                    pass

            debug.info("Hooks", "Primary data refresh complete")

        except Exception as e:
            debug.error("Hooks", f"Data refresh failed: {e}")
        finally:
            store.set("is_refreshing_data", False)
            # Clear all loading indicators at once to avoid UI flashing
            app.call_from_thread(
                store.set,
                "loading_states",
                {"sidebar": False, "track_list": False, "app": False},
            )

            # Start background prefetcher with a very long delay
            def start_prefetcher_daemon():
                import time

                time.sleep(60)  # Wait a full minute
                if not app.is_running:
                    return
                try:
                    from src.hooks.usePrefetcher import run_prefetcher

                    run_prefetcher(app, network, store)
                except Exception as ex:
                    debug.warning("Hooks", f"Prefetcher failed: {ex}")

            threading.Thread(target=start_prefetcher_daemon, daemon=True).start()

    threading.Thread(target=_background_refresh, daemon=True).start()

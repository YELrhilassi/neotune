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
    store.set("loading_states", {"sidebar": True, "track_list": True, "app": True})
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
                app.call_from_thread(store.set, "playlists", playlists)
            else:
                # Fallback: if we got nothing from API (likely rate limit),
                # but we already have data in the store from state.json, keep it.
                # If store is empty, try to check the cache explicitly.
                current_pls = store.get("playlists")
                if not current_pls:
                    from src.core.cache import CacheStore

                    cache = CacheStore(enable_disk=True)
                    # Try to reconstruct from individual cached pages
                    # This is complex, but get_playlists() should have done it via _safe_api_call.
                    pass

            # 3. Dynamic Browse Metadata
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
                    elif last_ctx == "spotify_playlists":
                        # We don't restore tracks for the "Spotify Playlists" leaf automatically
                        # since it's a dynamic table load.
                        pass
                    else:
                        parts = last_ctx.split(":")
                        if len(parts) >= 3 and parts[1] == "playlist":
                            tracks = network.get_playlist_tracks(parts[2])

                    if tracks:
                        app.call_from_thread(store.set, "current_tracks", tracks)
                except Exception:
                    pass

            debug.info("Hooks", "Primary data refresh complete")

        except Exception as e:
            debug.error("Hooks", f"Data refresh failed: {e}")
        finally:
            store.set("is_refreshing_data", False)

            # Clear all loading indicators at once to avoid UI flashing
            def _clear_loading():
                store.set("loading_states", {"sidebar": False, "track_list": False, "app": False})

            app.call_from_thread(_clear_loading)

            # Start background prefetcher with a long delay
            def start_prefetcher_daemon():
                import time

                time.sleep(30)  # Wait 30s before background indexing
                if not app.is_running:
                    return
                try:
                    from src.hooks.usePrefetcher import run_prefetcher

                    run_prefetcher(app, network, store)
                except Exception as ex:
                    debug.warning("Hooks", f"Prefetcher failed: {ex}")

            threading.Thread(target=start_prefetcher_daemon, daemon=True).start()

    threading.Thread(target=_background_refresh, daemon=True).start()

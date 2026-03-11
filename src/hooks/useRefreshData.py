from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork
from src.state.store import Store
from src.core.debug_logger import DebugLogger


from src.state.feature_stores import UIStore


def useRefreshData(app):
    """
    Refreshes all application data with precise loading state management.
    """
    network = Container.resolve(SpotifyNetwork)
    store = Container.resolve(Store)
    ui_store = Container.resolve(UIStore)
    debug = DebugLogger()

    # Start loading indicators
    loading = {"sidebar": True, "track_list": True, "app": False}
    store.set("loading_states", loading)
    ui_store.update(loading_states=loading)
    debug.info("Hooks", "Starting full data refresh")

    def _background_refresh():
        try:
            # 1. User Profile
            debug.debug("Hooks", "Fetching user profile")
            profile = network.get_user_profile()
            if profile:
                app.call_from_thread(store.set, "user_profile", profile)

            # 2. Basic Playlists
            debug.debug("Hooks", "Fetching user playlists")
            playlists = network.get_playlists()
            app.call_from_thread(store.set, "playlists", playlists)
            app.call_from_thread(ui_store.update, playlists=playlists)

            # 3. Dynamic Browse Metadata
            debug.debug("Hooks", "Fetching browse metadata")
            metadata = network.get_browse_metadata()
            app.call_from_thread(store.set, "browse_metadata", metadata)
            app.call_from_thread(ui_store.update, browse_metadata=metadata)

            # 4. History
            debug.debug("Hooks", "Fetching recently played")
            history = network.get_recently_played()
            app.call_from_thread(store.set, "recently_played", history)

            # Sidebar is now ready
            current_loading = ui_store.get()["loading_states"]
            new_loading = {**current_loading, "sidebar": False}
            app.call_from_thread(store.set, "loading_states", new_loading)
            app.call_from_thread(ui_store.update, loading_states=new_loading)

            # 5. Restore last context
            last_ctx = store.get("last_active_context")
            tracks = []
            if last_ctx:
                debug.debug("Hooks", f"Restoring last context: {last_ctx}")
                try:
                    if last_ctx == "liked_songs":
                        tracks = network.get_liked_songs()
                    elif last_ctx == "recently_played":
                        api_tracks = network.get_recently_played()
                        from src.core.activity_service import ActivityService

                        activity_svc = Container.resolve(ActivityService)
                        tracks = activity_svc.get_combined_history(api_tracks)
                    else:
                        parts = last_ctx.split(":")
                        tracks = network.get_playlist_tracks(parts[2]) if len(parts) >= 3 else []

                    app.call_from_thread(store.set, "current_tracks", tracks)
                    app.call_from_thread(ui_store.update, current_tracks=tracks)
                except Exception:
                    pass

            # Track list is now ready
            current_loading = ui_store.get()["loading_states"]
            final_loading = {**current_loading, "track_list": False}
            app.call_from_thread(store.set, "loading_states", final_loading)
            app.call_from_thread(ui_store.update, loading_states=final_loading)
            debug.info("Hooks", "Data refresh completed successfully")

        except Exception as e:
            debug.error("Hooks", f"Refresh failed: {e}")
            app.call_from_thread(app.notify, f"Refresh failed: {e}", severity="error")
            # Ensure loading state is cleared even on error
            cleared_loading = {"sidebar": False, "track_list": False, "app": False}
            app.call_from_thread(store.set, "loading_states", cleared_loading)
            app.call_from_thread(ui_store.update, loading_states=cleared_loading)

    import threading

    threading.Thread(target=_background_refresh, daemon=True).start()

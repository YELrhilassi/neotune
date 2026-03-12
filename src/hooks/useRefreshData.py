from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork
from src.state.store import Store
from src.core.debug_logger import DebugLogger


def useRefreshData(app):
    """
    Refreshes all application data with precise loading state management.
    """
    network = Container.resolve(SpotifyNetwork)
    store = Store()  # Singleton
    debug = DebugLogger()

    # Start loading indicators
    loading = {"sidebar": True, "track_list": True, "app": False}
    store.set("loading_states", loading)
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

            # 3. Dynamic Browse Metadata
            debug.debug("Hooks", "Fetching browse metadata")
            metadata = network.get_browse_metadata()
            app.call_from_thread(store.set, "browse_metadata", metadata)


            # 4. Prefetch Spotify Playlists for fuzzy finder
            debug.debug("Hooks", "Prefetching Spotify playlists")
            cache_key = "all_user_playlists_spotify"
            cached_obj = store.get(cache_key)
            import time
            if not (cached_obj and isinstance(cached_obj, dict) and time.time() - cached_obj.get("time", 0) < 86400):
                all_playlists = []
                offset = 0
                while True:
                    result = network.discovery.get_user_playlists("spotify", limit=50, offset=offset, fetch_details=False)
                    items = result.get("items", [])
                    if not items: break
                    all_playlists.extend(items)
                    if offset + 50 >= result.get("total", 0): break
                    offset += 50
                app.call_from_thread(store.set, cache_key, {"time": time.time(), "data": all_playlists}, persist=True)




            # Start a separate daemon thread to prefetch tracks inside all known playlists slowly
            def _prefetch_all_playlist_tracks():
                tracks_cache_key = "all_prefetched_tracks"
                cached_tracks_obj = store.get(tracks_cache_key)
                if cached_tracks_obj and isinstance(cached_tracks_obj, dict) and time.time() - cached_tracks_obj.get("time", 0) < 43200:
                    return # Already prefetched within 12 hours
                
                all_tracks = []
                count = 0
                
                # 1. Prefetch Liked Songs first
                try:
                    liked_offset = 0
                    while True:
                        liked_songs = network.get_liked_songs(limit=50, offset=liked_offset)
                        if not liked_songs: break
                        for item in liked_songs:
                            if not item or not isinstance(item, dict): continue
                            t = item.get("track")
                            if not t or not isinstance(t, dict): continue
                            all_tracks.append({
                                "id": t.get("id"),
                                "uri": t.get("uri"),
                                "name": t.get("name", "Unknown"),
                                "artists": [a.get("name") for a in t.get("artists", [])],
                                "type": "track",
                                "source": "core",
                                "context_name": "Liked Songs",
                                "context_uri": "spotify:collection:tracks"
                            })
                        
                        if len(liked_songs) < 50: break
                        liked_offset += 50
                        time.sleep(0.5)

                    # Save initial liked songs batch
                    app.call_from_thread(store.set, tracks_cache_key, {"time": time.time(), "data": all_tracks}, persist=True)
                except Exception as e:
                    debug.warning("Hooks", f"Failed to prefetch Liked Songs: {e}")

                # 2. Gather all playlists
                target_playlists = []
                user_pls = store.get("playlists") or []
                for p in user_pls:
                    if p and isinstance(p, dict): target_playlists.append((p.get("id"), p.get("name"), "personal"))
                
                # Just prefetch personal playlists first, then sp_obj to prioritize user data
                sp_obj = store.get(cache_key)
                if sp_obj and isinstance(sp_obj, dict):
                    for p in sp_obj.get("data", []):
                        if p and isinstance(p, dict): target_playlists.append((p.get("id"), p.get("name"), "spotify"))
                
                for pid, pname, source in target_playlists:
                    if not pid: continue
                    try:
                        pl_offset = 0
                        while True:
                            pl_tracks = network.library.get_playlist_tracks(pid, limit=100, offset=pl_offset) 
                            if not pl_tracks: break
                            
                            for item in pl_tracks:
                                if not item or not isinstance(item, dict): continue
                                t = item.get("track")
                                if not t or not isinstance(t, dict): continue
                                
                                all_tracks.append({
                                    "id": t.get("id"),
                                    "uri": t.get("uri"),
                                    "name": t.get("name", "Unknown"),
                                    "artists": [a.get("name") for a in t.get("artists", [])],
                                    "type": "track",
                                    "source": source,
                                    "context_name": pname,
                                    "context_uri": f"spotify:playlist:{pid}"
                                })
                                
                            if len(pl_tracks) < 100: break
                            pl_offset += 100
                            time.sleep(0.2)
                            
                        count += 1
                        # Save incrementally every 5 playlists so the user can search immediately
                        if count % 5 == 0:
                            app.call_from_thread(store.set, tracks_cache_key, {"time": time.time(), "data": all_tracks}, persist=True)
                            
                        time.sleep(0.5)
                    except Exception as e:
                        debug.warning("Hooks", f"Failed to prefetch tracks for {pname}: {e}")
                        
                # Final save
                app.call_from_thread(store.set, tracks_cache_key, {"time": time.time(), "data": all_tracks}, persist=True)




            import threading
            threading.Thread(target=_prefetch_all_playlist_tracks, daemon=True).start()

            # 5. History
            debug.debug("Hooks", "Fetching recently played")
            history = network.get_recently_played()
            app.call_from_thread(store.set, "recently_played", history)

            # Sidebar is now ready
            current_loading = store.get("loading_states") or {}
            new_loading = {**current_loading, "sidebar": False}
            app.call_from_thread(store.set, "loading_states", new_loading)

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
                except Exception:
                    pass

            # Track list is now ready
            current_loading = store.get("loading_states") or {}
            final_loading = {**current_loading, "track_list": False}
            app.call_from_thread(store.set, "loading_states", final_loading)
            debug.info("Hooks", "Data refresh completed successfully")

        except Exception as e:
            debug.error("Hooks", f"Refresh failed: {e}")
            app.call_from_thread(app.notify, f"Refresh failed: {e}", severity="error")
            # Ensure loading state is cleared even on error
            cleared_loading = {"sidebar": False, "track_list": False, "app": False}
            app.call_from_thread(store.set, "loading_states", cleared_loading)

    import threading

    threading.Thread(target=_background_refresh, daemon=True).start()

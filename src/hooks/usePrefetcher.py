import time
from src.core.debug_logger import DebugLogger
from src.network.base import SpotifyServiceBase
from src.core.cache import CacheStore


def run_prefetcher(app, network, store):
    """
    Background prefetcher that builds a local index for fuzzy search.
    Designed to be extremely gentle on the Spotify API and system resources.
    """
    debug = DebugLogger()
    cache = CacheStore(enable_disk=True)
    debug.info("Prefetcher", "Starting background prefetcher (throttle mode)")

    if getattr(app, "_exit", False) or not app.is_running:
        return

    def wait_if_rate_limited():
        while SpotifyServiceBase.is_rate_limited():
            if getattr(app, "_exit", False) or not app.is_running:
                return False
            time.sleep(10)
        return True

    # 1. Prefetch Spotify official playlists metadata
    cache_key = "prefetch:spotify_playlists"
    cached_data = cache.get(cache_key)

    if not cached_data or time.time() - cached_data.get("time", 0) > 86400:
        debug.info("Prefetcher", "Indexing Spotify official playlists...")
        all_playlists = []
        offset = 0
        while True:
            if not wait_if_rate_limited():
                return
            if getattr(app, "_exit", False) or not app.is_running:
                return

            result = network.discovery.get_user_playlists(
                "spotify", limit=50, offset=offset, fetch_details=False
            )

            if not result or not result.get("items"):
                break

            items = result.get("items", [])
            all_playlists.extend(items)

            # Update store for immediate (non-persistent) use in fuzzy finder
            app.call_from_thread(store.set, "all_user_playlists_spotify", {"data": all_playlists})

            if offset + 50 >= result.get("total", 0):
                break
            offset += 50
            time.sleep(5)  # Very gentle

        if all_playlists:
            cache.set(cache_key, {"time": time.time(), "data": all_playlists}, ttl=86400)
    else:
        # Load from cache into memory store
        app.call_from_thread(store.set, "all_user_playlists_spotify", cached_data)

    # 2. Index all tracks inside playlists
    _prefetch_all_playlist_tracks(app, network, store, cache, wait_if_rate_limited)


def _prefetch_all_playlist_tracks(app, network, store, cache, wait_func):
    debug = DebugLogger()
    tracks_cache_key = "prefetch:all_tracks"
    cached_tracks = cache.get(tracks_cache_key)

    if cached_tracks and time.time() - cached_tracks.get("time", 0) < 43200:
        # Load into memory store
        app.call_from_thread(store.set, "all_prefetched_tracks", cached_tracks)
        return

    debug.info("Prefetcher", "Indexing tracks inside playlists (background)...")
    all_tracks = []

    # 1. Liked Songs
    try:
        liked_offset = 0
        while True:
            if not wait_func():
                return
            if getattr(app, "_exit", False) or not app.is_running:
                return

            liked_songs = network.get_liked_songs(limit=50, offset=liked_offset)
            if not liked_songs:
                break

            for item in liked_songs:
                if not item or not isinstance(item, dict):
                    continue
                t = item.get("track")
                if not t or not isinstance(t, dict):
                    continue
                all_tracks.append(
                    {
                        "id": t.get("id"),
                        "uri": t.get("uri"),
                        "name": t.get("name", "Unknown"),
                        "artists": [a.get("name") for a in t.get("artists", []) if a],
                        "type": "track",
                        "source": "core",
                        "context_name": "Liked Songs",
                        "context_uri": "spotify:collection:tracks",
                    }
                )

            if len(liked_songs) < 50:
                break
            liked_offset += 50
            time.sleep(10.0)

        # Periodic memory store update (non-persistent)
        app.call_from_thread(store.set, "all_prefetched_tracks", {"data": all_tracks})
    except Exception:
        pass

    # 2. Playlists
    target_playlists = []
    user_pls = store.get("playlists") or []
    for p in user_pls:
        if p and isinstance(p, dict):
            target_playlists.append((p.get("id"), p.get("name"), "personal"))

    sp_data = store.get("all_user_playlists_spotify")
    if sp_data and isinstance(sp_data, dict):
        for p in sp_data.get("data", []):
            if p and isinstance(p, dict):
                target_playlists.append((p.get("id"), p.get("name"), "spotify"))

    count = 0
    for pid, pname, source in target_playlists:
        if not wait_func():
            return
        if getattr(app, "_exit", False) or not app.is_running:
            break
        if not pid:
            continue

        try:
            # Index first 100 tracks
            pl_tracks = network.library.get_playlist_tracks(pid, limit=100, offset=0)
            if not pl_tracks:
                time.sleep(5)
                continue

            for item in pl_tracks:
                if not item or not isinstance(item, dict):
                    continue
                t = item.get("track")
                if not t or not isinstance(t, dict):
                    continue

                all_tracks.append(
                    {
                        "id": t.get("id"),
                        "uri": t.get("uri"),
                        "name": t.get("name", "Unknown"),
                        "artists": [a.get("name") for a in t.get("artists", []) if a],
                        "type": "track",
                        "source": source,
                        "context_name": pname,
                        "context_uri": f"spotify:playlist:{pid}",
                    }
                )

            count += 1
            if count % 10 == 0:
                app.call_from_thread(store.set, "all_prefetched_tracks", {"data": all_tracks})

            time.sleep(10.0)
        except Exception:
            time.sleep(15)

    if not getattr(app, "_exit", False) and app.is_running:
        # Save to disk cache and update memory store
        final_data = {"time": time.time(), "data": all_tracks}
        cache.set(tracks_cache_key, final_data, ttl=43200)
        app.call_from_thread(store.set, "all_prefetched_tracks", final_data)
        debug.info("Prefetcher", f"Background indexing complete ({len(all_tracks)} tracks)")

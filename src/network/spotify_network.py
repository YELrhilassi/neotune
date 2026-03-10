import spotipy
from spotipy.oauth2 import SpotifyOAuth
from src.config.client_config import ClientConfiguration
from typing import Optional, List, Dict, Any


class SpotifyNetwork:
    _auth_manager: Optional[SpotifyOAuth] = (
        None  # Keep auth_manager as a class-level variable to maintain token state
    )

    def __init__(self, config: ClientConfiguration):
        self.config = config
        self.sp: Optional[spotipy.Spotify] = None
        self.setup_auth()

    def setup_auth(self):
        if not self.config.is_valid():
            return

        scope = "user-read-playback-state,user-modify-playback-state,playlist-read-private,user-read-currently-playing,user-library-read,user-read-recently-played"
        if not SpotifyNetwork._auth_manager:
            SpotifyNetwork._auth_manager = SpotifyOAuth(
                client_id=self.config.client_id,
                client_secret=self.config.client_secret,
                redirect_uri=self.config.redirect_uri,
                scope=scope,
                open_browser=False,
            )

        mgr = SpotifyNetwork._auth_manager
        if self.sp is None and mgr:
            token_info = mgr.get_cached_token()
            if token_info:
                self.sp = spotipy.Spotify(auth_manager=mgr)
            else:
                self.sp = spotipy.Spotify()  # Unauthenticated instance

    def get_auth_url(self) -> str:
        if not SpotifyNetwork._auth_manager:
            self.setup_auth()
        mgr = SpotifyNetwork._auth_manager
        if mgr:
            return mgr.get_authorize_url()
        return ""

    def complete_login(self, response_url: str) -> bool:
        if not SpotifyNetwork._auth_manager:
            self.setup_auth()

        mgr = SpotifyNetwork._auth_manager
        if not mgr:
            return False

        # Extract code from URL and get token
        code = mgr.parse_response_code(response_url)
        token = mgr.get_access_token(code, as_dict=False)
        if token:
            self.sp = spotipy.Spotify(auth_manager=mgr)
            return True
        return False

    def is_authenticated(self) -> bool:
        mgr = SpotifyNetwork._auth_manager
        if not mgr:
            return False

        token_info = mgr.get_cached_token()
        if not token_info:
            return False

        if mgr.is_token_expired(token_info):
            try:
                # Attempt silent refresh
                token_info = mgr.refresh_access_token(token_info["refresh_token"])
            except Exception:
                return False

        if not token_info:
            return False

        if not self.sp or not getattr(self.sp, "auth_manager", None):
            self.sp = spotipy.Spotify(auth_manager=mgr)

        return True

    def reauthenticate(self):
        # Force a re-authentication by clearing the cached token
        SpotifyNetwork._auth_manager = None
        self.setup_auth()

    def get_access_token(self) -> Optional[str]:
        mgr = SpotifyNetwork._auth_manager
        if not mgr:
            return None
        token_info = mgr.get_cached_token()
        if token_info:
            return token_info.get("access_token")
        return None

    def get_user_profile(self) -> Optional[Dict[str, Any]]:
        sp = self.sp
        if not sp:
            return None
        try:
            return sp.current_user()
        except Exception:
            return None

    def get_liked_songs(self, limit=50) -> List[Dict[str, Any]]:
        sp = self.sp
        if not sp:
            return []
        try:
            results = sp.current_user_saved_tracks(limit=limit)
            return results.get("items", []) if results else []
        except Exception:
            return []

    def get_browse_metadata(self) -> Dict[str, Any]:
        """
        Fetches metadata for all available browse categories and featured items.
        Handles regional 404s by providing safe fallbacks.
        """
        sp = self.sp
        if not sp:
            return {}

        metadata = {
            "categories": [],
            "featured_message": "Recommended",
            "featured_playlists": [],
            "user_profile": None,
        }

        try:
            # 1. User Profile for personalization
            profile = self.get_user_profile()
            metadata["user_profile"] = profile
            country = profile.get("country") if profile else None

            # 2. Fetch available categories
            try:
                categories_data = sp.categories(country=country, limit=50)
                if categories_data:
                    metadata["categories"] = categories_data.get("categories", {}).get(
                        "items", []
                    )
            except Exception:
                pass

            # 3. Fetch featured playlists (Handle 404 gracefully)
            try:
                featured = sp.featured_playlists(country=country, limit=20)
                if featured:
                    metadata["featured_message"] = featured.get("message", "Featured")
                    metadata["featured_playlists"] = featured.get("playlists", {}).get(
                        "items", []
                    )
            except Exception:
                # Fallback: Search for "Featured" playlists if the endpoint is disabled
                try:
                    search_res = sp.search(q="Featured", type="playlist", limit=10)
                    if search_res and search_res.get("playlists"):
                        metadata["featured_playlists"] = search_res["playlists"].get(
                            "items", []
                        )
                except Exception:
                    pass

        except Exception:
            pass

        return metadata

    def get_playlists_by_category(
        self, category_id: str, limit=50
    ) -> List[Dict[str, Any]]:
        """
        Fetches playlists for a category. Uses a multi-stage fallback since browse
        endpoints (category_playlists) are highly unstable and regionalized.
        """
        sp = self.sp
        if not sp:
            return []

        profile = self.get_user_profile()
        country = profile.get("country") if profile else None

        # 1. Attempt standard browse endpoint (Try WITH and WITHOUT country)
        try:
            results = sp.category_playlists(category_id, country=country, limit=limit)
            if results and results.get("playlists"):
                items = results["playlists"].get("items", [])
                if items:
                    return [i for i in items if i]
        except Exception:
            try:
                results = sp.category_playlists(category_id, limit=limit)
                if results and results.get("playlists"):
                    items = results["playlists"].get("items", [])
                    if items:
                        return [i for i in items if i]
            except Exception:
                pass

        # 2. Specialized Search Fallback (The most robust way for "Sections")
        # We try to map certain category IDs to high-quality search queries
        query_map = {
            "made-for-you": "Mix owner:spotify",
            "top_mixes": "Top Mix owner:spotify",
            "discover": "Discover owner:spotify",
            "0JQ5DAqbMKFHOzu9Kzcc9M": "Mix owner:spotify",  # Made For You
            "0JQ5DAt0tbjZptfcdMSKl3": "Mix owner:spotify",  # Made For You (Alternate ID)
        }

        query = query_map.get(category_id, category_id)
        if "owner:spotify" not in query and category_id not in [
            "pop",
            "rock",
            "charts",
        ]:
            # For general categories, search for spotify-owned playlists to match "Official" feel
            query = f"{query} owner:spotify"

        try:
            res = sp.search(q=query, type="playlist", limit=limit)
            if res and res.get("playlists"):
                items = res["playlists"].get("items", [])
                if items:
                    return [i for i in items if i]
        except Exception:
            pass

        return []

        # 1. Get metadata for name-based search if category_id is a slug
        # But first, try to find the category name from our store or cache if possible?
        # Actually, let's try the direct ID first.

        try:
            profile = self.get_user_profile()
            country = profile.get("country") if profile else None

            # Try category_playlists (highly likely to 404 based on tests)
            results = sp.category_playlists(category_id, country=country, limit=limit)
            if results and results.get("playlists"):
                items = results["playlists"].get("items", [])
                if items:
                    return [i for i in items if i]
        except Exception:
            pass

        # 2. Search Fallback (The most reliable way now)
        try:
            # We try searching for the category ID as a query
            # Often the ID is descriptive (e.g. 'rock', 'pop')
            query = category_id
            # If it's a long hex ID, we might want to use the category name,
            # but we don't have it here. However, search often works on the slug.
            res = sp.search(q=query, type="playlist", limit=limit)
            if res and res.get("playlists"):
                items = res["playlists"].get("items", [])
                if items:
                    return [i for i in items if i]
        except Exception:
            pass

        return []

        # 1. Fetch user profile for country code (essential for browse endpoints)
        profile = self.get_user_profile()
        country = profile.get("country") if profile else None

        try:
            # 2. Try official category playlists endpoint
            results = sp.category_playlists(category_id, country=country, limit=limit)
            if results and results.get("playlists"):
                items = results["playlists"].get("items", [])
                if items:
                    return [i for i in items if i]  # Filter out None entries
        except Exception:
            pass

        # 3. Fallback: Search for playlists with the category name/ID
        try:
            # If it's a known ID format like 0JQ5D..., it might not search well by name.
            # But usually these are mapped to categories.
            # We'll try a generic search.
            res = sp.search(q=category_id, type="playlist", limit=limit)
            if res and res.get("playlists"):
                items = res["playlists"].get("items", [])
                if items:
                    return [i for i in items if i]
        except Exception:
            pass

        return []

        try:
            # 1. Fetch using standard browse endpoint
            profile = self.get_user_profile()
            country = profile.get("country") if profile else None

            results = sp.category_playlists(category_id, country=country, limit=limit)
            if results and "playlists" in results:
                return results["playlists"].get("items", [])
            return []
        except spotipy.exceptions.SpotifyException as e:
            # If 404 or other error, fallback to search.
            # Many IDs returned by categories list are not valid for category_playlists in all regions.
            if e.http_status in [404, 400]:
                try:
                    # Try searching for the category ID as a tag or query
                    search_res = sp.search(
                        q=f"playlist:{category_id}", type="playlist", limit=limit
                    )
                    if not search_res or not search_res.get("playlists"):
                        search_res = sp.search(
                            q=category_id, type="playlist", limit=limit
                        )

                    if search_res and "playlists" in search_res:
                        return search_res["playlists"].get("items", [])
                except Exception:
                    pass
            return []
        except Exception:
            return []

    def get_playlists(self, limit=50) -> List[Dict[str, Any]]:
        sp = self.sp
        if not sp:
            return []
        try:
            results = sp.current_user_playlists(limit=limit)
            return results.get("items", []) if results else []
        except Exception:
            return []

    def get_playlist_tracks(self, playlist_id: str, limit=50) -> List[Dict[str, Any]]:
        sp = self.sp
        if not sp:
            return []
        try:
            results = sp.playlist_items(playlist_id, limit=limit)
            return results.get("items", []) if results else []
        except Exception:
            return []

    def get_album_tracks(self, album_id: str, limit=50) -> List[Dict[str, Any]]:
        sp = self.sp
        if not sp:
            return []
        try:
            results = sp.album_tracks(album_id, limit=limit)
            return results.get("items", []) if results else []
        except Exception:
            return []

    def get_featured_playlists(self, limit=20) -> List[Dict[str, Any]]:
        sp = self.sp
        if not sp:
            return []
        try:
            results = sp.featured_playlists(limit=limit)
            return results.get("playlists", {}).get("items", []) if results else []
        except Exception:
            return []

    def get_recently_played(self, limit=50) -> List[Dict[str, Any]]:
        sp = self.sp
        if not sp:
            return []
        try:
            results = sp.current_user_recently_played(limit=limit)
            return results.get("items", []) if results else []
        except Exception:
            return []

    def search(
        self, query: str, qtype="track,playlist,album", limit=50
    ) -> List[Dict[str, Any]]:
        sp = self.sp
        if not sp:
            return []
        try:
            results = sp.search(q=query, type=qtype, limit=limit)
            if not results:
                return []

            items = []
            if "track" in qtype and results.get("tracks"):
                for t in results.get("tracks", {}).get("items", []):
                    items.append({"_qtype": "track", "data": t})
            if "album" in qtype and results.get("albums"):
                for a in results.get("albums", {}).get("items", []):
                    items.append({"_qtype": "album", "data": a})
            if "playlist" in qtype and results.get("playlists"):
                for p in results.get("playlists", {}).get("items", []):
                    items.append({"_qtype": "playlist", "data": p})
            return items
        except Exception:
            return []

    def get_current_playback(self) -> Optional[Dict[str, Any]]:
        sp = self.sp
        if not sp:
            return None
        try:
            return sp.current_playback()
        except Exception:
            return None

    def get_devices(self) -> Optional[Dict[str, Any]]:
        sp = self.sp
        if not sp:
            return None
        try:
            return sp.devices()
        except Exception:
            return None

    def _get_fallback_device_id(self) -> Optional[str]:
        import time

        # Try a few times to give the local player time to register with Spotify's servers
        for _ in range(5):
            devices_data = self.get_devices()
            if devices_data and devices_data.get("devices"):
                devices = devices_data["devices"]
                # 1. Look for our specific TUI player
                for d in devices:
                    if d.get("name") == "Spotify TUI Player":
                        return d.get("id")

                # 2. Look for ANY active device
                for d in devices:
                    if d.get("is_active"):
                        return d.get("id")

                # 3. Fallback to the first available device
                return devices[0].get("id")
            time.sleep(1.5)  # Increased sleep to allow librespot to handshaking
        return None

    def play_track(
        self, track_uri, device_id=None, context_uri=None, offset_position=None
    ):
        sp = self.sp
        if not sp:
            return

        params = {}
        if device_id:
            params["device_id"] = device_id

        if context_uri:
            params["context_uri"] = context_uri
            if offset_position is not None:
                params["offset"] = {"position": int(offset_position)}
            elif track_uri:
                # Only use uri offset if it's a single track string
                if isinstance(track_uri, str) and ":track:" in track_uri:
                    params["offset"] = {"uri": track_uri}
                elif (
                    isinstance(track_uri, list)
                    and track_uri
                    and ":track:" in track_uri[0]
                ):
                    params["offset"] = {"uri": track_uri[0]}
        elif isinstance(track_uri, list) and track_uri:
            params["uris"] = track_uri
            if offset_position is not None:
                params["offset"] = {"position": int(offset_position)}
        elif isinstance(track_uri, str) and ":track:" in track_uri:
            params["uris"] = [track_uri]
        elif isinstance(track_uri, str):
            params["context_uri"] = track_uri

        try:
            sp.start_playback(**params)
        except spotipy.exceptions.SpotifyException as e:
            if e.http_status == 404 and "No active device" in str(e):
                dev_id = self._get_fallback_device_id()
                if dev_id:
                    params["device_id"] = dev_id
                    sp.start_playback(**params)
                    return
            raise e

    def transfer_playback(self, device_id: str, force_play=True):
        sp = self.sp
        if not sp:
            return
        try:
            sp.transfer_playback(device_id=device_id, force_play=force_play)
        except Exception:
            pass

    def toggle_play_pause(self) -> bool:
        sp = self.sp
        if not sp:
            return False
        playback = self.get_current_playback()
        try:
            if playback and playback.get("is_playing"):
                sp.pause_playback()
                return False
            else:
                sp.start_playback()
                return True
        except spotipy.exceptions.SpotifyException as e:
            if e.http_status == 404 and "No active device" in str(e):
                dev_id = self._get_fallback_device_id()
                if dev_id:
                    sp.start_playback(device_id=dev_id)
                    return True
            raise e

    def toggle_shuffle(self) -> bool:
        sp = self.sp
        if not sp:
            return False
        playback = self.get_current_playback()
        if playback:
            current_shuffle = playback.get("shuffle_state", False)
            try:
                sp.shuffle(state=not current_shuffle)
                return not current_shuffle
            except spotipy.exceptions.SpotifyException as e:
                if e.http_status == 404 and "No active device" in str(e):
                    dev_id = self._get_fallback_device_id()
                    if dev_id:
                        sp.shuffle(state=not current_shuffle, device_id=dev_id)
                        return not current_shuffle
                raise e
        return False

    def cycle_repeat(self) -> str:
        sp = self.sp
        if not sp:
            return "off"
        playback = self.get_current_playback()
        if playback:
            states = ["off", "context", "track"]
            current = playback.get("repeat_state", "off")
            try:
                next_idx = (states.index(current) + 1) % len(states)
            except ValueError:
                next_idx = 0

            try:
                sp.repeat(state=states[next_idx])
                return states[next_idx]
            except spotipy.exceptions.SpotifyException as e:
                if e.http_status == 404 and "No active device" in str(e):
                    dev_id = self._get_fallback_device_id()
                    if dev_id:
                        sp.repeat(state=states[next_idx], device_id=dev_id)
                        return states[next_idx]
                raise e
        return "off"

    def next_track(self):
        sp = self.sp
        if not sp:
            return
        try:
            sp.next_track()
        except spotipy.exceptions.SpotifyException as e:
            if e.http_status == 404 and "No active device" in str(e):
                dev_id = self._get_fallback_device_id()
                if dev_id:
                    sp.next_track(device_id=dev_id)
                    return
            raise e

    def prev_track(self):
        sp = self.sp
        if not sp:
            return
        try:
            sp.previous_track()
        except spotipy.exceptions.SpotifyException as e:
            if e.http_status == 404 and "No active device" in str(e):
                dev_id = self._get_fallback_device_id()
                if dev_id:
                    sp.previous_track(device_id=dev_id)
                    return
            raise e

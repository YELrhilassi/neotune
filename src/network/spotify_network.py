"""Spotify API network layer with authentication and playback control."""

import uuid
from typing import Optional, List, Dict, Any
import time
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException
from src.core.logging_config import get_logger
from src.core.debug_logger import DebugLogger
from src.core.cache import CacheStore
from src.core.constants import (
    SpotifyScopes,
    PlayerSettings,
    ServerSettings,
    CategoryMappings,
)

logger = get_logger("spotify_network")


class SpotifyNetwork:
    """Handles all Spotify API interactions including authentication and playback."""

    def __init__(self, config):
        """Initialize SpotifyNetwork with configuration.

        Args:
            config: ClientConfiguration instance with credentials
        """
        self.config = config
        self._auth_manager: Optional[SpotifyOAuth] = None
        self.sp: Optional[spotipy.Spotify] = None
        self._debug = DebugLogger()
        self._cache = CacheStore()
        self._setup_auth()

    def _setup_auth(self) -> None:
        """Initialize authentication manager."""
        if not self.config.is_valid():
            logger.warning("Cannot setup auth: invalid configuration")
            return

        if self._auth_manager is None:
            self._auth_manager = SpotifyOAuth(
                client_id=self.config.client_id,
                client_secret=self.config.client_secret,
                redirect_uri=self.config.redirect_uri,
                scope=",".join(SpotifyScopes.SCOPES),
                open_browser=False,
            )

        if self.sp is None and self._auth_manager:
            token_info = self._auth_manager.get_cached_token()
            if token_info:
                self.sp = spotipy.Spotify(auth_manager=self._auth_manager)
            else:
                self.sp = spotipy.Spotify()

    def get_auth_url(self) -> str:
        """Generate OAuth authorization URL.

        Returns:
            Authorization URL string
        """
        if self._auth_manager is None:
            self._setup_auth()

        if self._auth_manager:
            return self._auth_manager.get_authorize_url()
        return ""

    def complete_login(self, response_url: str) -> bool:
        """Complete OAuth flow with response URL.

        Args:
            response_url: Full callback URL with authorization code

        Returns:
            True if authentication successful, False otherwise
        """
        if self._auth_manager is None:
            self._setup_auth()

        if not self._auth_manager:
            logger.error("Cannot complete login: auth manager not initialized")
            return False

        try:
            code = self._auth_manager.parse_response_code(response_url)
            token = self._auth_manager.get_access_token(code, as_dict=False)
            if token:
                self.sp = spotipy.Spotify(auth_manager=self._auth_manager)
                self._debug.info("SpotifyNetwork", "Login completed successfully")
                logger.info("Login completed successfully")
                return True
        except Exception as e:
            logger.error(f"Failed to complete login: {e}")

        return False

    def is_authenticated(self) -> bool:
        """Check if user is authenticated and token is valid.

        Returns:
            True if authenticated with valid token
        """
        if self._auth_manager is None:
            return False

        token_info = self._auth_manager.get_cached_token()
        if not token_info:
            return False

        if self._auth_manager.is_token_expired(token_info):
            try:
                self._auth_manager.refresh_access_token(token_info["refresh_token"])
            except Exception as e:
                logger.error(f"Token refresh failed: {e}")
                return False

        if not self.sp or not getattr(self.sp, "auth_manager", None):
            self.sp = spotipy.Spotify(auth_manager=self._auth_manager)

        return True

    def reauthenticate(self) -> None:
        """Force re-authentication by clearing cached token."""
        self._auth_manager = None
        self._setup_auth()
        self._debug.info("SpotifyNetwork", "Re-authentication initiated")
        logger.info("Re-authentication initiated")

    def get_access_token(self) -> Optional[str]:
        """Get current access token.

        Returns:
            Access token string or None if not authenticated
        """
        if self._auth_manager is None:
            return None

        token_info = self._auth_manager.get_cached_token()
        if token_info:
            return token_info.get("access_token")
        return None

    def _get_fallback_device_id(self) -> Optional[str]:
        """Find suitable playback device with fallback logic.

        Returns:
            Device ID string or None if no device available
        """
        for attempt in range(5):
            devices_data = self.get_devices()
            if devices_data and devices_data.get("devices"):
                devices = devices_data["devices"]

                # Priority 1: Look for our specific player
                for device in devices:
                    if device.get("name") == PlayerSettings.DEVICE_NAME:
                        return device.get("id")

                # Priority 2: Look for any active device
                for device in devices:
                    if device.get("is_active"):
                        return device.get("id")

                # Priority 3: Use first available device
                return devices[0].get("id")

            time.sleep(1.5)

        logger.warning("No fallback device found after retries")
        return None

    def _execute_with_fallback(self, operation: callable, *args, **kwargs) -> Any:
        """Execute Spotify operation with automatic device fallback.

        Args:
            operation: Spotify method to call
            *args: Positional arguments for operation
            **kwargs: Keyword arguments for operation

        Returns:
            Result of operation or None on failure
        """
        try:
            return operation(*args, **kwargs)
        except SpotifyException as e:
            if e.http_status == 404 and "No active device" in str(e):
                device_id = self._get_fallback_device_id()
                if device_id:
                    kwargs["device_id"] = device_id
                    return operation(*args, **kwargs)
            raise

    def _safe_api_call(
        self,
        func: callable,
        *args,
        default_return: Any = None,
        track_name: Optional[str] = None,
        cache_ttl: Optional[int] = None,
        **kwargs,
    ) -> Any:
        """Execute API call with error handling, network tracking, and optional caching.

        Args:
            func: API function to call
            *args: Positional arguments
            default_return: Value to return on failure
            track_name: Optional name for network tracking
            cache_ttl: Optional TTL in seconds for caching the result
            **kwargs: Keyword arguments

        Returns:
            API response or empty default on failure
        """
        if not self.sp:
            return default_return

        endpoint = track_name or func.__name__

        # 1. Check Cache
        if cache_ttl is not None:
            cache_key = f"api:{endpoint}:{args}:{kwargs}"
            cached_val = self._cache.get(cache_key)
            if cached_val is not None:
                self._debug.debug("SpotifyNetwork", f"Cache hit: {endpoint}")
                return cached_val

        # 2. Prepare for Tracking
        request_id = str(uuid.uuid4())[:8]
        self._debug.network_start(request_id, "API", endpoint, dict(kwargs) if kwargs else None)
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000

            # 3. Track success
            self._debug.network_end(request_id, status_code=200)
            self._debug.track_performance(endpoint, duration_ms)

            # 4. Save to Cache
            if cache_ttl is not None:
                cache_key = f"api:{endpoint}:{args}:{kwargs}"
                self._cache.set(cache_key, result, ttl=cache_ttl)

            return result
        except SpotifyException as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.warning(f"Spotify API error: {e}")

            # Track error
            self._debug.network_end(
                request_id, error=str(e), status_code=getattr(e, "http_status", None)
            )
            self._debug.track_performance(endpoint, duration_ms)

            return default_return
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Unexpected error in API call: {e}")

            # Track error
            self._debug.network_end(request_id, error=str(e))
            self._debug.track_performance(endpoint, duration_ms)

            return default_return

    # User Profile Methods
    def get_user_profile(self) -> Optional[Dict[str, Any]]:
        """Fetch current user profile.

        Returns:
            User profile dictionary or None
        """
        return self._safe_api_call(self.sp.current_user, cache_ttl=3600)

    def get_liked_songs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch user's saved tracks.

        Args:
            limit: Maximum number of tracks to fetch

        Returns:
            List of saved track items
        """
        result = self._safe_api_call(
            self.sp.current_user_saved_tracks, limit=limit, default_return={}, cache_ttl=60
        )
        return result.get("items", []) if result else []

    # Browse Methods
    def get_browse_metadata(self) -> Dict[str, Any]:
        """Fetch browse categories and featured playlists.

        Returns:
            Dictionary with categories, featured playlists, and user profile
        """
        metadata = {
            "categories": [],
            "featured_message": "Recommended",
            "featured_playlists": [],
            "user_profile": None,
        }

        if not self.sp:
            return metadata

        try:
            profile = self.get_user_profile()
            metadata["user_profile"] = profile
            country = profile.get("country") if profile else None

            # Fetch categories
            try:
                categories_data = self._safe_api_call(
                    self.sp.categories, country=country, limit=50, track_name="categories"
                )
                if categories_data:
                    metadata["categories"] = categories_data.get("categories", {}).get("items", [])
            except Exception as e:
                logger.debug(f"Categories fetch failed: {e}")

            # Fetch featured playlists
            try:
                featured = self._safe_api_call(
                    self.sp.featured_playlists,
                    country=country,
                    limit=20,
                    track_name="featured_playlists",
                )
                if featured:
                    metadata["featured_message"] = featured.get("message", "Featured")
                    metadata["featured_playlists"] = featured.get("playlists", {}).get("items", [])
            except Exception:
                # Fallback to search
                try:
                    search_res = self._safe_api_call(
                        self.sp.search, q="Featured", type="playlist", limit=10, track_name="search"
                    )
                    if search_res and search_res.get("playlists"):
                        metadata["featured_playlists"] = search_res["playlists"].get("items", [])
                except Exception as e:
                    logger.debug(f"Featured search fallback failed: {e}")

        except Exception as e:
            logger.error(f"Error fetching browse metadata: {e}")

        return metadata

    def get_playlists_by_category(self, category_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch playlists for a browse category with multi-stage fallback.

        Args:
            category_id: Category identifier
            limit: Maximum number of playlists to fetch

        Returns:
            List of playlist dictionaries
        """
        if not self.sp:
            return []

        profile = self.get_user_profile()
        country = profile.get("country") if profile else None

        # Attempt 1: Try official category_playlists endpoint
        try:
            results = self._safe_api_call(
                self.sp.category_playlists,
                category_id,
                country=country,
                limit=limit,
                track_name="category_playlists",
            )
            if results and results.get("playlists"):
                items = results["playlists"].get("items", [])
                if items:
                    return [item for item in items if item]
        except Exception:
            pass

        # Attempt 2: Try without country parameter
        try:
            results = self._safe_api_call(
                self.sp.category_playlists,
                category_id,
                limit=limit,
                track_name="category_playlists_no_country",
            )
            if results and results.get("playlists"):
                items = results["playlists"].get("items", [])
                if items:
                    return [item for item in items if item]
        except Exception:
            pass

        # Attempt 3: Search fallback with query mapping
        query = CategoryMappings.QUERY_MAP.get(category_id, category_id)
        if "owner:spotify" not in query and category_id not in ["pop", "rock", "charts"]:
            query = f"{query} owner:spotify"

        try:
            res = self._safe_api_call(
                self.sp.search, q=query, type="playlist", limit=limit, track_name="category_search"
            )
            if res and res.get("playlists"):
                items = res["playlists"].get("items", [])
                if items:
                    return [item for item in items if item]
        except Exception as e:
            logger.warning(f"Search fallback failed for category {category_id}: {e}")

        return []

    def get_playlists(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch user's playlists.

        Args:
            limit: Maximum number of playlists to fetch

        Returns:
            List of playlist dictionaries
        """
        result = self._safe_api_call(
            self.sp.current_user_playlists, limit=limit, default_return={}, cache_ttl=300
        )
        return result.get("items", []) if result else []

    def get_playlist_tracks(self, playlist_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch tracks from a playlist.

        Args:
            playlist_id: Playlist identifier
            limit: Maximum number of tracks to fetch

        Returns:
            List of track items
        """
        result = self._safe_api_call(
            self.sp.playlist_items, playlist_id, limit=limit, default_return={}, cache_ttl=60
        )
        return result.get("items", []) if result else []

    def get_album_tracks(self, album_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch tracks from an album.

        Args:
            album_id: Album identifier
            limit: Maximum number of tracks to fetch

        Returns:
            List of track dictionaries
        """
        result = self._safe_api_call(
            self.sp.album_tracks, album_id, limit=limit, default_return={}, cache_ttl=3600
        )
        return result.get("items", []) if result else []

    def get_featured_playlists(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch featured playlists.

        Args:
            limit: Maximum number of playlists to fetch

        Returns:
            List of playlist dictionaries
        """
        result = self._safe_api_call(self.sp.featured_playlists, limit=limit, default_return={})
        if result:
            return result.get("playlists", {}).get("items", [])
        return []

    def get_recently_played(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch recently played tracks.

        Args:
            limit: Maximum number of tracks to fetch

        Returns:
            List of recently played items
        """
        result = self._safe_api_call(
            self.sp.current_user_recently_played, limit=limit, default_return={}
        )
        return result.get("items", []) if result else []

    def search(
        self, query: str, qtype: str = "track,playlist,album", limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Search Spotify catalog.

        Args:
            query: Search query string
            qtype: Comma-separated list of types to search
            limit: Maximum number of results per type

        Returns:
            List of search results with _qtype markers
        """
        result = self._safe_api_call(
            self.sp.search, q=query, type=qtype, limit=limit, default_return={}
        )

        if not result:
            return []

        items = []
        if "track" in qtype and result.get("tracks"):
            for track in result["tracks"].get("items", []):
                items.append({"_qtype": "track", "data": track})

        if "album" in qtype and result.get("albums"):
            for album in result["albums"].get("items", []):
                items.append({"_qtype": "album", "data": album})

        if "playlist" in qtype and result.get("playlists"):
            for playlist in result["playlists"].get("items", []):
                items.append({"_qtype": "playlist", "data": playlist})

        return items

    # Playback Control Methods
    def get_current_playback(self) -> Optional[Dict[str, Any]]:
        """Fetch current playback state.

        Returns:
            Playback state dictionary or None
        """
        return self._safe_api_call(self.sp.current_playback)

    def get_devices(self) -> Optional[Dict[str, Any]]:
        """Fetch available devices.

        Returns:
            Devices response dictionary or None
        """
        return self._safe_api_call(self.sp.devices)

    def play_track(
        self,
        track_uri: Any,
        device_id: Optional[str] = None,
        context_uri: Optional[str] = None,
        offset_position: Optional[int] = None,
    ) -> None:
        """Start playback of track(s).

        Args:
            track_uri: Track URI string or list of URIs
            device_id: Optional device ID to play on
            context_uri: Optional context URI (album/playlist)
            offset_position: Optional offset position in context
        """
        if not self.sp:
            return

        params = {}
        if device_id:
            params["device_id"] = device_id
        if context_uri:
            params["context_uri"] = context_uri
        if offset_position is not None:
            params["offset"] = {"position": int(offset_position)}

        # Handle different track_uri types
        if isinstance(track_uri, str) and ":track:" in track_uri:
            params["uris"] = [track_uri]
            params["offset"] = {"uri": track_uri}
        elif isinstance(track_uri, list) and track_uri:
            params["uris"] = track_uri
            if ":track:" in track_uri[0]:
                params["offset"] = {"uri": track_uri[0]}
        elif isinstance(track_uri, str):
            params["context_uri"] = track_uri

        # Tracked playback execution
        self._safe_api_call(self.sp.start_playback, track_name="play_track", **params)

    def transfer_playback(self, device_id: str, force_play: bool = True) -> None:
        """Transfer playback to a device.

        Args:
            device_id: Device ID to transfer to
            force_play: Whether to force playback after transfer
        """
        self._safe_api_call(
            self.sp.transfer_playback,
            device_id=device_id,
            force_play=force_play,
            track_name="transfer_playback",
        )

    def toggle_play_pause(self) -> bool:
        """Toggle between play and pause.

        Returns:
            True if now playing, False if paused
        """
        playback = self.get_current_playback()
        if playback and playback.get("is_playing"):
            self._safe_api_call(self.sp.pause_playback, track_name="pause_playback")
            return False
        else:
            self._safe_api_call(
                self._execute_with_fallback,
                self.sp.start_playback,
                track_name="play_playback",
            )
            return True

    def toggle_shuffle(self) -> bool:
        """Toggle shuffle state.

        Returns:
            True if shuffle is now on, False otherwise
        """
        playback = self.get_current_playback()
        if playback:
            current_shuffle = playback.get("shuffle_state", False)
            self._safe_api_call(
                self._execute_with_fallback,
                self.sp.shuffle,
                state=not current_shuffle,
                track_name="toggle_shuffle",
            )
            return not current_shuffle
        return False

    def cycle_repeat(self) -> str:
        """Cycle through repeat states.

        Returns:
            New repeat state string ("off", "context", or "track")
        """
        states = ["off", "context", "track"]
        playback = self.get_current_playback()

        if playback:
            current = playback.get("repeat_state", "off")
            try:
                next_idx = (states.index(current) + 1) % len(states)
            except ValueError:
                next_idx = 0

            self._safe_api_call(
                self._execute_with_fallback,
                self.sp.repeat,
                state=states[next_idx],
                track_name="cycle_repeat",
            )
            return states[next_idx]

        return "off"

    def next_track(self) -> None:
        """Skip to next track."""
        self._safe_api_call(
            self._execute_with_fallback, self.sp.next_track, track_name="next_track"
        )

    def prev_track(self) -> None:
        """Go to previous track."""
        self._safe_api_call(
            self._execute_with_fallback, self.sp.previous_track, track_name="prev_track"
        )
